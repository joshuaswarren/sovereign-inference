# SPDX-License-Identifier: Apache-2.0
"""Turn a provisioned :class:`Deployment` into a signed SIP-AI provider manifest.

An external-compute node is, from the router's point of view, just another
provider: it advertises a signed ``sip-ai.provider_manifest.v1`` with
``node_type = "external-adapter"`` whose ``manifest_uri`` is the deployment's
reachable endpoint. The signing key is the provider's own key pair, exactly as
with a local Sovereign Inference Node.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sip_protocol.manifests import sign_provider_manifest
from sip_protocol.signing import KeyPair

from .errors import ComputeError
from .spec import Deployment

_DEFAULT_PRIVACY_MODES = ["direct"]


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def provider_manifest_for(
    deployment: Deployment,
    *,
    keypair: KeyPair,
    models: list[str] | None = None,
    input_per_1m: float | None = None,
    output_per_1m: float | None = None,
    pricing_unit: str | None = None,
    max_context: int = 4096,
    max_concurrency: int | None = None,
    logging_policy: str = "no_prompt_logging",
    privacy_modes: list[str] | None = None,
    published_at: str | None = None,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    """Build and sign a provider manifest advertising ``deployment``'s endpoint.

    Pricing defaults to the deployment's stamped price (which an adapter copies
    from the provisioning :class:`InferenceSpec`), so the advertised manifest
    price is structurally tied to what the node was deployed to charge. Explicit
    ``pricing_unit``/``input_per_1m``/``output_per_1m`` override it.

    Raises :class:`ComputeError` if the deployment has no endpoint yet — an
    unreachable node must not be advertised.
    """
    if not deployment.endpoint:
        raise ComputeError(f"deployment {deployment.id!r} has no endpoint to advertise yet")

    unit = pricing_unit if pricing_unit is not None else (deployment.pricing_unit or "usdc")
    in_price = input_per_1m if input_per_1m is not None else (deployment.input_per_1m or 0.0)
    out_price = output_per_1m if output_per_1m is not None else (deployment.output_per_1m or 0.0)

    stamp = published_at or now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest: dict[str, Any] = {
        "schema": "sip-ai.provider_manifest.v1",
        "provider_pubkey": keypair.public_key_str,
        "node_type": "external-adapter",
        "models": list(models) if models is not None else [deployment.model],
        "runtime_adapters": [deployment.provider],
        "pricing": {
            "unit": unit,
            "input_per_1m": in_price,
            "output_per_1m": out_price,
        },
        "max_context": max_context,
        "logging_policy": logging_policy,
        "privacy_modes": list(privacy_modes) if privacy_modes is not None else list(_DEFAULT_PRIVACY_MODES),
        "manifest_uri": deployment.endpoint,
        "published_at": stamp,
    }
    if max_concurrency is not None:
        manifest["max_concurrency"] = max_concurrency
    return sign_provider_manifest(manifest, keypair)
