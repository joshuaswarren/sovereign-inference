# SPDX-License-Identifier: Apache-2.0
"""Akash :class:`~sip_compute.ComputeProvider` implementation.

The provider drives the ``provider-services`` CLI through the Akash deployment
lifecycle: create the deployment, read the returned ``dseq``, pick the cheapest
bid, create a lease, push the manifest, then poll ``lease-status`` for the
ingress URI. Every external boundary (the CLI runner, the ``sleep`` between
polls) is injected, so the whole multi-step lifecycle is unit-testable offline.
A live deploy needs ``provider-services`` on PATH plus a funded, configured key.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from sip_compute import (
    ComputeError,
    Deployment,
    DeploymentStatus,
    InferenceSpec,
    register_provider,
)

from .sdl import build_sdl

CliRunner = Callable[[Sequence[str]], str]
Sleep = Callable[[float], None]

_DEFAULT_CLI = "provider-services"
_DEFAULT_POLL_INTERVAL_S = 6.0
_DEFAULT_MAX_POLLS = 120
_CLI_TIMEOUT_S = 180


def _default_run(argv: Sequence[str]) -> str:
    result = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT_S,
        check=True,
    )
    return result.stdout


def _parse_json(out: str, *, context: str) -> dict[str, Any]:
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComputeError(f"akash {context} returned non-JSON output: {out[:200]!r}") from exc
    if not isinstance(data, dict):
        raise ComputeError(f"akash {context} returned an unexpected JSON shape: {type(data).__name__}")
    return data


def _as_int(value: object) -> int:
    """Coerce a possibly-malformed CLI value to int, defaulting to 0."""
    if isinstance(value, int):  # also covers bool
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _require_tx_ok(parsed: dict[str, Any], context: str) -> None:
    """Reject a Cosmos-SDK tx that exited 0 but failed on-chain (non-zero ``code``).

    ``provider-services`` is Cosmos-based: a ``tx`` command can exit 0 while the
    transaction is rejected on-chain (insufficient funds, sequence mismatch,
    lease already exists). Such a failure surfaces only as ``code != 0`` plus a
    ``raw_log`` in the JSON body, so a silent success here would mislead callers.
    """
    code = _as_int(parsed.get("code", 0))
    if code != 0:
        raw_log = parsed.get("raw_log", "")
        raise ComputeError(f"akash {context} failed on-chain: code={code} raw_log={raw_log!r}")


def _iter_attributes(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten Cosmos-SDK tx events (under ``logs`` or top-level ``events``)."""
    attributes: list[dict[str, Any]] = []
    event_groups: list[Any] = []
    for log in data.get("logs") or []:
        if isinstance(log, dict):
            event_groups.extend(log.get("events") or [])
    event_groups.extend(data.get("events") or [])
    for event in event_groups:
        if isinstance(event, dict):
            for attr in event.get("attributes") or []:
                if isinstance(attr, dict):
                    attributes.append(attr)
    return attributes


def _extract_dseq(data: dict[str, Any]) -> str | None:
    if isinstance(data.get("dseq"), str | int):
        return str(data["dseq"])
    for attr in _iter_attributes(data):
        if attr.get("key") == "dseq" and attr.get("value"):
            return str(attr["value"])
    return None


def _pick_cheapest_bid(data: dict[str, Any]) -> str | None:
    """Return the provider address of the cheapest open bid."""
    bids = data.get("bids")
    if not isinstance(bids, list) or not bids:
        return None
    best_provider: str | None = None
    best_price: float | None = None
    for entry in bids:
        bid = entry.get("bid", entry) if isinstance(entry, dict) else {}
        provider = (((bid.get("bid_id") or {}).get("provider")) if isinstance(bid, dict) else None) or None
        price_raw = ((bid.get("price") or {}).get("amount")) if isinstance(bid, dict) else None
        if not provider:
            continue
        try:
            price = float(price_raw) if price_raw is not None else float("inf")
        except (TypeError, ValueError):
            price = float("inf")
        if best_price is None or price < best_price:
            best_price, best_provider = price, str(provider)
    return best_provider


def _extract_uri(data: dict[str, Any]) -> str | None:
    """Return the first ingress URI (https-normalized) from a lease-status doc."""
    services = data.get("services")
    if not isinstance(services, dict):
        return None
    for service in services.values():
        if not isinstance(service, dict):
            continue
        for uri in service.get("uris") or []:
            if isinstance(uri, str) and uri:
                return uri if "://" in uri else f"https://{uri}"
    return None


def _service_available(data: dict[str, Any]) -> bool:
    services = data.get("services")
    if not isinstance(services, dict):
        return False
    return any(isinstance(service, dict) and _as_int(service.get("available")) >= 1 for service in services.values())


class AkashProvider:
    """Provision and manage a SIP inference endpoint on the Akash marketplace."""

    name = "akash"

    def __init__(
        self,
        *,
        wallet: str,
        owner: str,
        run: CliRunner = _default_run,
        cli: str = _DEFAULT_CLI,
        gseq: int = 1,
        oseq: int = 1,
        chain_args: Sequence[str] | None = None,
        sleep: Sleep = lambda _seconds: None,
        poll_interval: float = _DEFAULT_POLL_INTERVAL_S,
        max_polls: int = _DEFAULT_MAX_POLLS,
    ) -> None:
        self._wallet = wallet
        self._owner = owner
        self._run = run
        self._cli = cli
        self._gseq = gseq
        self._oseq = oseq
        self._chain = list(chain_args or [])
        self._sleep = sleep
        self._poll_interval = poll_interval
        self._max_polls = max_polls

    # -- ComputeProvider protocol --------------------------------------------

    def deploy(self, spec: InferenceSpec) -> Deployment:
        """Run create -> bid -> lease -> manifest and return the lease handle."""
        sdl = build_sdl(spec)
        # mkstemp hands back the path before any write, so the file is always
        # cleaned up even if serialization or any CLI call raises.
        fd, sdl_path = tempfile.mkstemp(suffix=".yaml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(sdl, handle)

            created = _parse_json(
                self._run(
                    [self._cli, "tx", "deployment", "create", sdl_path, "--from", self._wallet, *self._tx_args()]
                ),
                context="deployment create",
            )
            _require_tx_ok(created, "deployment create")
            dseq = _extract_dseq(created)
            if dseq is None:
                raise ComputeError(f"akash deployment create did not return a dseq: {created!r}")

            bids = _parse_json(
                self._run(
                    [
                        self._cli,
                        "query",
                        "market",
                        "bid",
                        "list",
                        "--owner",
                        self._owner,
                        "--dseq",
                        dseq,
                        *self._query_args(),
                    ]
                ),
                context="bid list",
            )
            provider_addr = _pick_cheapest_bid(bids)
            if provider_addr is None:
                raise ComputeError(f"no Akash bids for deployment dseq={dseq}")

            lease = _parse_json(
                self._run(
                    [
                        self._cli,
                        "tx",
                        "market",
                        "lease",
                        "create",
                        *self._lease_id_args(dseq, provider_addr),
                        "--from",
                        self._wallet,
                        *self._tx_args(),
                    ]
                ),
                context="lease create",
            )
            _require_tx_ok(lease, "lease create")
            self._run(
                [
                    self._cli,
                    "send-manifest",
                    sdl_path,
                    "--dseq",
                    dseq,
                    "--provider",
                    provider_addr,
                    "--from",
                    self._wallet,
                    *self._chain,
                ]
            )
        finally:
            Path(sdl_path).unlink(missing_ok=True)

        return Deployment(
            provider=self.name,
            id=dseq,
            model=spec.model,
            status=DeploymentStatus.DEPLOYING,
            pricing_unit=spec.pricing_unit,
            input_per_1m=spec.input_per_1m,
            output_per_1m=spec.output_per_1m,
            raw={
                "owner": self._owner,
                "dseq": dseq,
                "provider": provider_addr,
                "gseq": self._gseq,
                "oseq": self._oseq,
            },
        )

    def status(self, deployment: Deployment) -> Deployment:
        """Refresh a deployment by polling its lease status for an ingress URI."""
        owner, dseq, provider_addr = self._lease_coordinates(deployment)
        data = _parse_json(
            self._run(
                [
                    self._cli,
                    "lease-status",
                    "--owner",
                    owner,
                    "--dseq",
                    dseq,
                    "--gseq",
                    str(self._gseq),
                    "--oseq",
                    str(self._oseq),
                    "--provider",
                    provider_addr,
                    *self._query_args(),
                ]
            ),
            context="lease-status",
        )
        uri = _extract_uri(data)
        ready = bool(uri) and _service_available(data)
        return replace(
            deployment,
            status=DeploymentStatus.RUNNING if ready else DeploymentStatus.DEPLOYING,
            endpoint=uri if ready else deployment.endpoint,
            raw={**deployment.raw, "lease_status": data},
        )

    def await_ready(self, deployment: Deployment) -> Deployment:
        """Poll lease status until the ingress is ready or the poll cap is hit."""
        current = self.status(deployment)
        polls = 0
        while not current.is_ready and not current.status.is_terminal and polls < self._max_polls:
            self._sleep(self._poll_interval)
            current = self.status(current)
            polls += 1
        return current

    def teardown(self, deployment: Deployment) -> None:
        """Close the Akash deployment, ending billing and releasing the lease."""
        owner, dseq, _provider = self._lease_coordinates(deployment)
        try:
            self._run(
                [
                    self._cli,
                    "tx",
                    "deployment",
                    "close",
                    "--owner",
                    owner,
                    "--dseq",
                    dseq,
                    "--from",
                    self._wallet,
                    *self._tx_args(),
                ]
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise ComputeError(f"failed to close akash deployment dseq={dseq}") from exc

    # -- helpers --------------------------------------------------------------

    def _lease_coordinates(self, deployment: Deployment) -> tuple[str, str, str]:
        raw = deployment.raw
        owner = raw.get("owner")
        dseq = raw.get("dseq")
        provider_addr = raw.get("provider")
        if not (owner and dseq and provider_addr):
            raise ComputeError(
                f"deployment {deployment.id!r} is missing Akash lease coordinates "
                "(owner/dseq/provider); was it produced by AkashProvider.deploy?"
            )
        return str(owner), str(dseq), str(provider_addr)

    def _lease_id_args(self, dseq: str, provider_addr: str) -> list[str]:
        return [
            "--owner",
            self._owner,
            "--dseq",
            dseq,
            "--gseq",
            str(self._gseq),
            "--oseq",
            str(self._oseq),
            "--provider",
            provider_addr,
        ]

    def _tx_args(self) -> list[str]:
        return ["-o", "json", "-y", *self._chain]

    def _query_args(self) -> list[str]:
        return ["-o", "json", *self._chain]


register_provider("akash", AkashProvider)
