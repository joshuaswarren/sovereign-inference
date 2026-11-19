# SPDX-License-Identifier: AGPL-3.0-or-later
"""SSRF guards for the relay forward path.

DNS names are resolved here, once, and every resolved address is checked
against non-public ranges. The connection is then pinned to the checked
address (no second resolution), and redirects are never followed. See #25.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx


class SsrfRefused(Exception):
    """Raised when a target address fails the SSRF check."""


def _normalize_host(host: str) -> str:
    """Expand decimal/octal/hex IP-literal spellings to canonical dotted form.

    OS resolvers accept ``2130706433``, ``0x7f.1`` or ``0177.0.0.1`` for
    127.0.0.1, so those must be recognized before the private-range check.
    """
    try:
        if "." not in host and host.lower().startswith("0x"):
            return str(ipaddress.IPv4Address(int(host, 16)))
        if len(host) > 1 and host.startswith("0") and set(host) <= set("01234567"):
            return str(ipaddress.IPv4Address(int(host, 8)))
        if host.isdigit():
            return str(ipaddress.IPv4Address(int(host)))
        parts = host.split(".")
        if len(parts) > 1 and any(
            p.lower().startswith("0x") or (p.startswith("0") and len(p) > 1 and p != "0") for p in parts
        ):
            ints = [
                int(p, 16) if p.lower().startswith("0x") else int(p, 8 if p.startswith("0") and len(p) > 1 else 10)
                for p in parts
            ]
            ints += [0] * (4 - len(ints))  # "127.1" means 127.0.0.1
            return str(ipaddress.IPv4Address(bytes(ints)))
    except (ValueError, IndexError):
        pass
    return host


def _unwrap_ipv4(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 target hidden inside an IPv6 literal, if any.

    Covers IPv4-mapped (::ffff:0:0/96) and NAT64 (64:ff9b::/96) well-known
    prefixes; anything else (6to4 2002::/16 and friends) is left alone and
    judged as plain IPv6.
    """
    if isinstance(ip, ipaddress.IPv4Address):
        return ip
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in ipaddress.IPv6Network("64:ff9b::/96"):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def _is_dangerous_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    target = _unwrap_ipv4(ip) or ip
    return bool(
        target.is_private
        or target.is_loopback
        or target.is_link_local
        or target.is_reserved
        or target.is_multicast
        or target.is_unspecified
    )


def host_ip_or_none(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse ``host`` as an IP literal (any spelling), else None."""
    try:
        return ipaddress.ip_address(_normalize_host(host))
    except ValueError:
        return None


def resolve_host(host: str, port: int) -> str:
    """Resolve once; refuse unless every answer is a public address.

    Returns the address the caller must connect to (no re-resolution later).
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SsrfRefused(f"cannot resolve {host}: {exc}") from exc
    if not infos:
        raise SsrfRefused(f"no addresses for {host}")
    addresses = [str(info[4][0]) for info in infos]
    for addr in addresses:
        parsed = host_ip_or_none(addr)
        if parsed is None or _is_dangerous_ip(parsed):
            raise SsrfRefused(f"{host} resolves to a non-public address ({addr})")
    return addresses[0]


class PinnedTransport(httpx.HTTPTransport):
    """Transport that connects to the resolved-checked address, once.

    The request URL host is rewritten to the checked address; the original
    hostname is kept as the Host header and TLS SNI, so virtual hosting and
    certificate verification still target the intended provider.
    """

    def __init__(self, base_url: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        split = urlsplit(base_url)
        self._host = split.hostname or ""
        self._port = split.port or (443 if split.scheme == "https" else 80)
        self._resolved: str | None = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._resolved is None:
            self._resolved = resolve_host(self._host, self._port)
        host = self._host
        port = self._port
        url = request.url.copy_with(host=self._resolved, port=port)
        headers = request.headers.copy()
        headers["host"] = host if port in (80, 443) else f"{host}:{port}"
        pinned = httpx.Request(
            request.method,
            url,
            headers=headers,
            content=request.content,
            extensions={**request.extensions, "sni_hostname": host},
        )
        return super().handle_request(pinned)


# cache-buster 1
