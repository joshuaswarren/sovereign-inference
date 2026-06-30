# SPDX-License-Identifier: AGPL-3.0-or-later
"""Use a model running on *this* machine as a verified SIP provider.

The "as simple as Ollama" path: detect a local runtime (Ollama / llama.cpp),
then front the chosen model with the real provider gateway **in-process**, so the
router reaches it through :func:`sip_router.in_process_client` (no loopback
socket, no background server, no port to race on) — and every local answer still
carries a signed, verified receipt.

Boundaries are injectable: tests pass fake adapters and the network-free
``MockAdapter``; the desktop bundle passes real :class:`OllamaAdapter` /
:class:`LlamaCppAdapter` instances.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sip_gateway import create_app
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest

from .sources import trusted_provider_entry

# The local model is fronted in-process; this URI is the routing identity bound
# into the signed manifest, never actually dialed over a socket.
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 11434

# Runtimes the desktop app knows how to detect, in priority order.
_DEFAULT_RUNTIMES = (
    ("sip_runtime_ollama", "OllamaAdapter"),
    ("sip_runtime_llamacpp", "LlamaCppAdapter"),
)


class _DetectableAdapter(Protocol):
    name: str

    def is_available(self) -> bool: ...
    def list_models(self) -> list[str]: ...


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    """A detected local runtime: whether it is up and which models it has."""

    name: str
    available: bool
    models: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalProvider:
    """A locally fronted model: the gateway app plus its trusted routing entry."""

    entry: Any  # sip_router.ProviderEntry
    app: Any  # the in-process provider-gateway FastAPI app
    runtime: str
    model: str


def default_adapters() -> list[Any]:
    """Instantiate the known runtime adapters, skipping any that aren't installed."""
    adapters: list[Any] = []
    for module_name, class_name in _DEFAULT_RUNTIMES:
        try:
            module = importlib.import_module(module_name)
            adapters.append(getattr(module, class_name)())
        except Exception:  # an uninstalled or unconstructable adapter is simply absent
            continue
    return adapters


def detect_runtimes(*, adapters: list[Any] | None = None) -> list[RuntimeStatus]:
    """Report each local runtime's availability and installed models.

    A runtime that raises while probing (e.g. its daemon is down) is reported as
    unavailable rather than crashing detection.
    """
    candidates = adapters if adapters is not None else default_adapters()
    statuses: list[RuntimeStatus] = []
    for adapter in candidates:
        try:
            available = bool(adapter.is_available())
            models = tuple(adapter.list_models()) if available else ()
        except Exception:
            available, models = False, ()
        statuses.append(RuntimeStatus(name=adapter.name, available=available, models=models))
    return statuses


def front_local_model(
    model: str,
    *,
    adapter: Any,
    keypair: KeyPair | None = None,
    advertised_host: str = LOCAL_HOST,
    advertised_port: int = LOCAL_PORT,
    now: datetime | None = None,
) -> LocalProvider:
    """Front ``model`` (served by ``adapter``) as an in-process verified provider."""
    keypair = keypair or KeyPair.generate()
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    uri = f"http://{advertised_host}:{advertised_port}"
    manifest = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=keypair.public_key_str,
            models=[model],
            runtime_adapters=[adapter.name],
            pricing_unit="test",  # a locally-hosted model is free (0/0); 'test' is the free unit
            node_type="sovereign-node",
            manifest_uri=uri,
            published_at=stamp,
        ),
        keypair,
    )
    app = create_app(adapter=adapter, keypair=keypair, allowed_models=[model], provider_manifest=manifest)
    # The loopback URI is a trusted in-process identity, so skip the public-URL guard.
    entry = trusted_provider_entry(manifest, require_safe_url=False)
    return LocalProvider(entry=entry, app=app, runtime=adapter.name, model=model)
