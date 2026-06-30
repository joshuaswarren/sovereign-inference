# SPDX-License-Identifier: AGPL-3.0-or-later
"""Turn untrusted provider input into trusted routing entries.

This is the security boundary the desktop admin API sits on. A provider is only
routed to when:

1. its manifest carries a **valid signature** for its ``provider_pubkey``
   (:func:`sip_protocol.verify_provider_manifest`), and
2. the routing target is the **signed** ``manifest_uri`` — never an
   attacker-supplied ``base_url`` (mirrors discovery's ``_signed_endpoint``), and
3. for a remote provider, that endpoint is a **safe public address** — no SSRF
   pivot to loopback, private, link-local, or cloud-metadata ranges.

:func:`merge_provider` additionally refuses to let a *different key* hijack an
endpoint already pinned to one key (a trust-on-first-use guard), and
:func:`build_registry` assembles a live :class:`ProviderRegistry` from a saved
config, dropping (and reporting) anything that fails these checks rather than
silently trusting it.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from urllib.parse import urlsplit

from sip_discovery import Directory, FileDirectory, HttpDirectory
from sip_protocol import verify_provider_manifest
from sip_router import ProviderEntry, ProviderRegistry

from .config import AppConfig

_BLOCKED_HOSTNAMES = {"localhost", "metadata", "metadata.google.internal"}


class UntrustedProvider(ValueError):
    """Raised when a provider manifest cannot be trusted to route to."""


def is_safe_remote_url(url: str) -> bool:
    """True only for ``http(s)`` URLs to a non-internal host.

    Rejects loopback/private/link-local/reserved/metadata addresses (SSRF) and
    any non-HTTP scheme. A bare public hostname is allowed at this layer (DNS
    rebinding is a deeper, separately-noted concern).
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    lowered = host.lower()
    if lowered in _BLOCKED_HOSTNAMES or lowered.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # a non-literal public hostname
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def trusted_provider_entry(
    manifest: dict[str, object],
    *,
    base_url: str | None = None,
    require_safe_url: bool = True,
) -> ProviderEntry:
    """Verify ``manifest`` and bind it to its signed ``manifest_uri``.

    ``base_url``, if given, is treated as an *assertion* that must equal the
    signed ``manifest_uri`` — a mismatch is refused. The returned entry always
    routes to the signed URI. ``require_safe_url=False`` permits a loopback URI
    for the in-process local-use gateway (whose endpoint is never dialed over a
    socket).
    """
    if not verify_provider_manifest(manifest):
        raise UntrustedProvider("provider manifest signature is invalid")
    uri = manifest.get("manifest_uri")
    if not isinstance(uri, str) or not uri:
        raise UntrustedProvider("provider manifest has no manifest_uri to route to")
    if base_url is not None and base_url != uri:
        raise UntrustedProvider(
            f"base_url {base_url!r} does not match the signed manifest_uri {uri!r}; refusing to route"
        )
    if require_safe_url and not is_safe_remote_url(uri):
        raise UntrustedProvider(f"manifest_uri {uri!r} is not a safe public endpoint")
    return ProviderEntry(base_url=uri, manifest=manifest)


def _pubkey(entry: ProviderEntry) -> str:
    return str(entry.manifest["provider_pubkey"])


def merge_provider(existing: tuple[ProviderEntry, ...], new: ProviderEntry) -> tuple[ProviderEntry, ...]:
    """Add ``new`` to ``existing``, de-duplicating by key and pinning endpoints.

    Re-adding the same key refreshes its entry. A different key claiming an
    endpoint already pinned to another key is refused (trust-on-first-use), so a
    stolen/rotated key cannot silently take over a known provider URL.
    """
    new_key = _pubkey(new)
    for entry in existing:
        if entry.base_url == new.base_url and _pubkey(entry) != new_key:
            raise UntrustedProvider(
                f"endpoint {new.base_url!r} is already pinned to a different provider key; refusing to replace it"
            )
    kept = tuple(e for e in existing if _pubkey(e) != new_key)
    return (*kept, new)


def _default_directory_for(spec: str) -> Directory:
    """Resolve a directory spec: an ``http(s)`` URL → hosted, else a local file."""
    if spec.startswith(("http://", "https://")):
        return HttpDirectory(spec)
    return FileDirectory(spec)


def build_registry(
    config: AppConfig,
    *,
    directory_for: Callable[[str], Directory] | None = None,
) -> tuple[ProviderRegistry, list[str]]:
    """Build a verified :class:`ProviderRegistry` from ``config``.

    Returns the registry plus a list of human-readable warnings for every source
    that was dropped (bad signature, URL mismatch, unreachable directory) — the
    caller surfaces these in onboarding rather than failing the whole startup.
    """
    resolve = directory_for or _default_directory_for
    registry = ProviderRegistry()
    warnings: list[str] = []
    pinned: tuple[ProviderEntry, ...] = ()

    def _try_add(manifest: dict[str, object], *, base_url: str | None, require_safe_url: bool, label: str) -> None:
        nonlocal pinned
        try:
            entry = trusted_provider_entry(manifest, base_url=base_url, require_safe_url=require_safe_url)
            pinned = merge_provider(pinned, entry)
        except UntrustedProvider as exc:
            warnings.append(f"dropped {label}: {exc}")

    for entry in config.providers:
        _try_add(entry.manifest, base_url=entry.base_url, require_safe_url=True, label=f"provider {entry.base_url}")

    for spec in config.directories:
        try:
            discovered = resolve(spec).discover()
        except Exception as exc:  # any directory/transport failure is a warning, not a crash
            warnings.append(f"directory {spec!r} unreachable: {exc}")
            continue
        for provider in discovered:
            _try_add(
                provider.manifest,
                base_url=provider.base_url,
                require_safe_url=True,
                label=f"directory provider {provider.base_url}",
            )

    for entry in pinned:
        registry.add(entry)
    return registry, warnings
