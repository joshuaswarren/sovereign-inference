# SPDX-License-Identifier: AGPL-3.0-or-later
"""`sin share` — expose this node's local model as a discoverable SIP provider.

Turns a running Sovereign Inference Node into a first-class SIP-AI provider in
one step: it fronts the node's runtime adapter with a real provider gateway
(auth, model allowlist, context/token caps, rate limits, signed receipts, and
optional payment), advertises a signed ``sovereign-node`` provider manifest that
carries the node's public URL, and (optionally) announces that manifest to a
:class:`~sip_discovery.Directory` so other people's routers can find it.

The :func:`build_share` builder is pure composition and fully testable; only the
final ``serve`` (uvicorn) in :func:`cmd_share` touches the network.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sip_discovery import Directory
from sip_gateway import create_app
from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest

DEFAULT_RUNTIME = "ollama"
DEFAULT_PORT = 8090
DEFAULT_HOST = "127.0.0.1"


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True, slots=True)
class ShareConfig:
    """Operator-chosen sharing settings: what to serve, the caps, and the price.

    The caps (``max_output_tokens``, ``max_input_chars``, ``rate_limit_per_minute``)
    are the opt-in safety envelope; ``require_payment`` + ``pic_issuers`` gate the
    node behind PIC payment. ``advertised_url`` is the public URL announced to the
    directory; it defaults to ``http://{host}:{port}``.
    """

    model: str
    runtime: str = DEFAULT_RUNTIME
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    advertised_url: str | None = None
    token: str | None = None
    # opt-in safety envelope
    max_output_tokens: int = 512
    max_input_chars: int = 100_000
    rate_limit_per_minute: int | None = 60
    logging_policy: str = "no_prompt_logging"
    max_context: int = 4096
    # pricing / payment
    pricing_unit: str = "usdc"
    input_per_1m: float = 0.0
    output_per_1m: float = 0.0
    require_payment: bool = False
    pic_issuers: tuple[str, ...] = field(default_factory=tuple)

    def public_url(self) -> str:
        return self.advertised_url or f"http://{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class ShareResult:
    """A configured share: the gateway app, its signed manifest, and its URL."""

    app: Any
    manifest: dict[str, Any]
    base_url: str


def build_share(
    config: ShareConfig,
    *,
    keypair: KeyPair,
    adapter: Any,
    now: Callable[[], datetime] = _utc_now,
) -> ShareResult:
    """Build the signed manifest + the configured provider-gateway app for a share.

    ``adapter`` is a SIN runtime adapter (e.g. from ``sin_node.get_adapter``)
    pointed at the locally running model; its ``chat`` is what the gateway calls.
    """
    base_url = config.public_url()
    manifest = sign_provider_manifest(
        build_provider_manifest(
            provider_pubkey=keypair.public_key_str,
            models=[config.model],
            runtime_adapters=[adapter.name],
            pricing_unit=config.pricing_unit,
            input_per_1m=config.input_per_1m,
            output_per_1m=config.output_per_1m,
            node_type="sovereign-node",
            max_context=config.max_context,
            logging_policy=config.logging_policy,
            manifest_uri=base_url,
            published_at=now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
        keypair,
    )
    app = create_app(
        adapter=adapter,
        keypair=keypair,
        allowed_models=[config.model],
        token=config.token,
        max_output_tokens=config.max_output_tokens,
        max_input_chars=config.max_input_chars,
        rate_limit_per_minute=config.rate_limit_per_minute,
        logging_policy=config.logging_policy,
        price_units=config.pricing_unit,
        input_per_1m=str(config.input_per_1m),
        output_per_1m=str(config.output_per_1m),
        provider_manifest=manifest,
        require_payment=config.require_payment,
        pic_issuers=list(config.pic_issuers),
    )
    return ShareResult(app=app, manifest=manifest, base_url=base_url)


def announce_to_directory(directory: Directory, result: ShareResult) -> str:
    """Announce a share's signed manifest to ``directory``; return its reference."""
    return directory.announce(result.manifest, base_url=result.base_url)
