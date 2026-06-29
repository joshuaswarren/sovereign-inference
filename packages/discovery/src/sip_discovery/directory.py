# SPDX-License-Identifier: Apache-2.0
"""Provider directories: announce signed manifests, discover verified providers.

A :class:`Directory` is a place a node publishes its signed provider manifest and
a router reads it back. Discovery always **verifies the manifest signature**
before surfacing a provider and de-duplicates by provider public key, keeping the
freshest ``published_at`` — so a stale or forged entry can't be routed to.

Two implementations ship:

* :class:`FileDirectory` — a shared JSON file keyed by provider public key
  (offline, deterministic; for a LAN, a synced folder, or tests).
* :class:`ArweaveDirectory` — announce by anchoring the manifest with discovery
  tags; discover by querying those tags. The query (GraphQL) boundary is injected
  so it is fully unit-testable offline.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

from sip_arweave import Anchor, AnchorError
from sip_protocol.canonical import canonical_json
from sip_protocol.manifests import verify_provider_manifest

from .errors import DiscoveryError

# A discovery query maps a tag filter to the anchor URIs of matching manifests.
DiscoveryQuery = Callable[[dict[str, str]], list[str]]

_APP_TAG = "SIP-AI"
_TYPE_TAG = "provider-manifest"


@dataclass(frozen=True, slots=True)
class DiscoveredProvider:
    """A verified provider found in a directory: where to reach it + its manifest."""

    base_url: str
    manifest: dict[str, Any]

    @property
    def provider_pubkey(self) -> str:
        return str(self.manifest["provider_pubkey"])

    @property
    def models(self) -> list[str]:
        return list(self.manifest.get("models", []))

    @property
    def published_at(self) -> str:
        return str(self.manifest.get("published_at", ""))

    def serves(self, model: str) -> bool:
        return model in self.models


@runtime_checkable
class Directory(Protocol):
    """Somewhere providers announce signed manifests and routers discover them."""

    def announce(self, manifest: dict[str, Any], *, base_url: str | None = None) -> str:
        """Publish a signed manifest; return a reference (path key or anchor URI)."""
        ...

    def discover(self, *, model: str | None = None) -> list[DiscoveredProvider]:
        """Return verified providers, optionally filtered to those serving ``model``."""
        ...


def _signed_endpoint(manifest: dict[str, Any], base_url: str | None) -> str:
    """The endpoint a router may route to — always the *signed* ``manifest_uri``.

    The routed endpoint must be covered by the manifest signature; otherwise a
    directory writer could pair a victim's valid manifest with an attacker's URL.
    An explicit ``base_url`` is allowed only as an assertion that it matches the
    signed ``manifest_uri`` — a mismatch is refused.
    """
    uri = manifest.get("manifest_uri")
    if not isinstance(uri, str) or not uri:
        raise DiscoveryError(
            "cannot announce a provider whose manifest has no manifest_uri; "
            "a discoverable manifest must advertise where to reach the node"
        )
    if base_url is not None and base_url != uri:
        raise DiscoveryError(
            "explicit base_url does not match the signed manifest_uri; refusing to "
            "announce an endpoint the manifest signature does not cover"
        )
    return uri


def _require_verified(manifest: dict[str, Any]) -> None:
    if not verify_provider_manifest(manifest):
        raise DiscoveryError("refusing to announce an invalid or unsigned provider manifest")


def _filter_and_dedupe(providers: list[DiscoveredProvider], *, model: str | None) -> list[DiscoveredProvider]:
    """Keep the freshest entry per provider key, optionally filtered by model."""
    freshest: dict[str, DiscoveredProvider] = {}
    for provider in providers:
        if model is not None and not provider.serves(model):
            continue
        existing = freshest.get(provider.provider_pubkey)
        if existing is None or provider.published_at > existing.published_at:
            freshest[provider.provider_pubkey] = provider
    return list(freshest.values())


class FileDirectory:
    """A shared JSON directory keyed by provider public key."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def announce(self, manifest: dict[str, Any], *, base_url: str | None = None) -> str:
        _require_verified(manifest)
        _signed_endpoint(manifest, base_url)  # validate the signed endpoint
        pubkey = str(manifest["provider_pubkey"])
        entries = self._load_raw()
        # Store only the signed manifest — the endpoint is derived from its signed
        # manifest_uri on discover, so no unsigned field can redirect routing.
        entries[pubkey] = {"manifest": manifest}
        self._write_raw(entries)
        return pubkey

    def discover(self, *, model: str | None = None) -> list[DiscoveredProvider]:
        providers: list[DiscoveredProvider] = []
        for entry in self._load_raw().values():
            if not isinstance(entry, dict):
                continue
            manifest = entry.get("manifest")
            if not isinstance(manifest, dict):
                continue
            if not verify_provider_manifest(manifest):
                continue  # skip a tampered or forged on-disk entry
            uri = manifest.get("manifest_uri")
            if not isinstance(uri, str) or not uri:
                continue
            providers.append(DiscoveredProvider(base_url=uri, manifest=manifest))
        return _filter_and_dedupe(providers, model=model)

    # -- storage --------------------------------------------------------------

    def _load_raw(self) -> dict[str, Any]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_raw(self, entries: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(entries, handle, indent=2, sort_keys=True)
            Path(tmp).replace(self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


class ArweaveDirectory:
    """A directory backed by Arweave: announce anchors a manifest with discovery
    tags; discover queries those tags and resolves the manifests back."""

    def __init__(self, anchor: Anchor, *, query: DiscoveryQuery | None = None) -> None:
        self._anchor = anchor
        self._query = query

    def announce(self, manifest: dict[str, Any], *, base_url: str | None = None) -> str:
        _require_verified(manifest)
        _signed_endpoint(manifest, base_url)  # validate the signed endpoint
        tags = {
            "App-Name": _APP_TAG,
            "Type": _TYPE_TAG,
            "Provider": str(manifest["provider_pubkey"]),
            "Models": ",".join(str(m) for m in manifest.get("models", [])),
        }
        return self._anchor.put(canonical_json(manifest), content_type="application/json", tags=tags)

    def discover(self, *, model: str | None = None) -> list[DiscoveredProvider]:
        if self._query is None:
            raise DiscoveryError(
                "ArweaveDirectory has no query configured; pass query=... "
                "(e.g. arweave_discovery_query(gateway)) to discover providers"
            )
        uris = self._query({"App-Name": _APP_TAG, "Type": _TYPE_TAG})
        providers: list[DiscoveredProvider] = []
        for uri in uris:
            manifest = self._resolve(uri)
            if manifest is None or not verify_provider_manifest(manifest):
                continue
            base = manifest.get("manifest_uri")
            if not isinstance(base, str) or not base:
                continue
            providers.append(DiscoveredProvider(base_url=base, manifest=manifest))
        return _filter_and_dedupe(providers, model=model)

    def _resolve(self, uri: str) -> dict[str, Any] | None:
        try:
            raw = self._anchor.get(uri)
            value = json.loads(raw)
        except (AnchorError, OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None


_ARWEAVE_GATEWAY = "https://arweave.net"
_GRAPHQL_TIMEOUT_S = 30.0


def arweave_discovery_query(
    *, gateway: str = _ARWEAVE_GATEWAY, client: httpx.Client | None = None, page_size: int = 100
) -> DiscoveryQuery:
    """Build a real Arweave discovery query backed by the gateway's GraphQL API.

    Returns a callable that, given a tag filter, returns the ``ar://`` URIs of
    matching transactions (newest first). Injected into :class:`ArweaveDirectory`
    so discovery is offline-testable; this is the production wiring.
    """
    base = gateway.rstrip("/")

    def query(tags: dict[str, str]) -> list[str]:
        tag_filter = [{"name": name, "values": [value]} for name, value in tags.items()]
        gql_query = (
            "query($tags:[TagFilter!]){transactions(tags:$tags,first:"
            + str(page_size)
            + ",sort:HEIGHT_DESC){edges{node{id}}}}"
        )
        gql = {"query": gql_query, "variables": {"tags": tag_filter}}
        owns = client is None
        http = client or httpx.Client(timeout=_GRAPHQL_TIMEOUT_S)
        try:
            response = http.post(f"{base}/graphql", json=gql)
            response.raise_for_status()
            edges = response.json().get("data", {}).get("transactions", {}).get("edges", [])
        except (httpx.HTTPError, ValueError):
            return []
        finally:
            if owns:
                http.close()
        return [f"ar://{edge['node']['id']}" for edge in edges if isinstance(edge, dict)]

    return query
