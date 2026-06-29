# SPDX-License-Identifier: Apache-2.0
"""Nosana :class:`~sip_compute.ComputeProvider` implementation.

The provider drives the ``nosana`` CLI: ``job post`` to provision, ``job get``
to poll, ``job stop`` to tear down. Every external boundary is injected — the
CLI runner and the ``sleep`` used while polling — so the full lifecycle is
unit-testable offline. A live deploy needs the ``nosana`` CLI on PATH and a
funded wallet configured for it.
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

from sip_compute import (
    ComputeError,
    Deployment,
    DeploymentStatus,
    InferenceSpec,
    register_provider,
)

from .job import build_job_definition

CliRunner = Callable[[Sequence[str]], str]
Sleep = Callable[[float], None]

# Nosana job states -> our provider-agnostic lifecycle. Tolerant of casing.
_STATE_MAP = {
    "queued": DeploymentStatus.PENDING,
    "pending": DeploymentStatus.PENDING,
    "starting": DeploymentStatus.DEPLOYING,
    "running": DeploymentStatus.RUNNING,
    "completed": DeploymentStatus.CLOSED,
    "stopped": DeploymentStatus.CLOSED,
    "failed": DeploymentStatus.FAILED,
}

# Keys a Nosana CLI payload may use for the job id and the exposed service URL.
_JOB_ID_KEYS = ("job", "address", "id", "job_address")
_SERVICE_URL_KEYS = ("serviceUrl", "service_url", "url", "exposed")

_DEFAULT_CLI = "nosana"
_DEFAULT_POLL_INTERVAL_S = 5.0
_DEFAULT_MAX_POLLS = 120
_CLI_TIMEOUT_S = 120


def _default_run(argv: Sequence[str]) -> str:
    """Run a CLI command and return its stdout (raising on non-zero exit)."""
    result = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT_S,
        check=True,
    )
    return result.stdout


def _parse_json(out: str) -> dict[str, Any]:
    try:
        data = json.loads(out)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComputeError(f"nosana CLI returned non-JSON output: {out[:200]!r}") from exc
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        raise ComputeError(f"nosana CLI returned an unexpected JSON shape: {type(data).__name__}")
    return data


def _first(data: dict[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _map_state(raw: object) -> DeploymentStatus | None:
    if not isinstance(raw, str):
        return None
    return _STATE_MAP.get(raw.strip().lower())


class NosanaProvider:
    """Provision and manage a SIP inference endpoint on the Nosana network."""

    name = "nosana"

    def __init__(
        self,
        *,
        market: str,
        run: CliRunner = _default_run,
        cli: str = _DEFAULT_CLI,
        sleep: Sleep = lambda _seconds: None,
        poll_interval: float = _DEFAULT_POLL_INTERVAL_S,
        max_polls: int = _DEFAULT_MAX_POLLS,
        timeout: int = 3600,
    ) -> None:
        self._market = market
        self._run = run
        self._cli = cli
        self._sleep = sleep
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._timeout = timeout

    # -- ComputeProvider protocol --------------------------------------------

    def deploy(self, spec: InferenceSpec) -> Deployment:
        """Post the job to the configured market and return its handle."""
        job = build_job_definition(spec)
        # mkstemp hands back the path before any write, so the file is always
        # cleaned up even if serialization or the CLI call raises.
        fd, job_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(job, handle)
            out = self._run(
                [
                    self._cli,
                    "job",
                    "post",
                    "--file",
                    job_path,
                    "--market",
                    self._market,
                    "--timeout",
                    str(self._timeout),
                    "--format",
                    "json",
                ]
            )
        finally:
            Path(job_path).unlink(missing_ok=True)

        data = _parse_json(out)
        job_id = _first(data, _JOB_ID_KEYS)
        if job_id is None:
            raise ComputeError(f"nosana job post did not return a job id: {data!r}")
        return Deployment(
            provider=self.name,
            id=job_id,
            model=spec.model,
            status=_map_state(data.get("state")) or DeploymentStatus.PENDING,
            endpoint=_first(data, _SERVICE_URL_KEYS),
            pricing_unit=spec.pricing_unit,
            input_per_1m=spec.input_per_1m,
            output_per_1m=spec.output_per_1m,
            raw=data,
        )

    def status(self, deployment: Deployment) -> Deployment:
        """Refresh a deployment by querying ``nosana job get``."""
        out = self._run([self._cli, "job", "get", deployment.id, "--format", "json"])
        data = _parse_json(out)
        return replace(
            deployment,
            status=_map_state(data.get("state")) or deployment.status,
            endpoint=_first(data, _SERVICE_URL_KEYS) or deployment.endpoint,
            raw=data,
        )

    def await_ready(self, deployment: Deployment) -> Deployment:
        """Poll until the deployment is ready, terminal, or the poll cap is hit."""
        current = self.status(deployment)
        polls = 0
        while not current.is_ready and not current.status.is_terminal and polls < self._max_polls:
            self._sleep(self._poll_interval)
            current = self.status(current)
            polls += 1
        return current

    def teardown(self, deployment: Deployment) -> None:
        """Stop the Nosana job, releasing its GPU."""
        try:
            self._run([self._cli, "job", "stop", deployment.id])
        except (subprocess.SubprocessError, OSError) as exc:
            raise ComputeError(f"failed to stop nosana job {deployment.id!r}") from exc


register_provider("nosana", NosanaProvider)
