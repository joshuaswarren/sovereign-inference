# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for SSRF hardening of the relay forward path (issue #25)."""

from __future__ import annotations

import socket
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from sip_protocol import KeyPair, build_provider_manifest, sign_provider_manifest
from sip_relay import create_relay_app
from sip_relay.ssrf import PinnedTransport, SsrfRefused, resolve_host


def _fake_getaddrinfo(host: str, port: int, *args: Any, **kwargs: Any):
    # rebind.test resolves to an RFC1918 address; pub.test to a public one.
    mapping = {
        "rebind.test": "10.0.0.5",
        "pub.test": "93.184.216.34",
    }
    if host not in mapping:
        raise socket.gaierror(socket.EAI_NONAME, "test mapping miss")
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (mapping[host], port))]


class TestLiteralNormalization:
    """Non-dotted IP literal spellings must be recognized and blocked."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://2130706433/",  # decimal 127.0.0.1
            "http://017700000001/",  # octal 127.0.0.1
            "http://0x7f000001/",  # hex 127.0.0.1
            "http://0x7f.1/",  # mixed hex
            "http://[64:ff9b::7f00:1]/",  # NAT64-embedded IPv4
            "http://[::ffff:127.0.0.1]/",  # IPv4-mapped IPv6
            "http://[::1]/",
            "http://127.0.0.1/",
            "http://169.254.169.254/",
        ],
    )
    def test_dangerous_literals_rejected(self, url: str) -> None:
        from sip_relay.app import _is_safe_forward_url

        assert _is_safe_forward_url(url) is False, url


class TestResolveOnce:
    """Hostname resolution happens here, once, and every answer is checked."""

    def test_private_resolution_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
        with pytest.raises(SsrfRefused):
            resolve_host("rebind.test", 80)

    def test_public_resolution_pinned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
        assert resolve_host("pub.test", 80) == "93.184.216.34"

    def test_mixed_resolution_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Any private answer means refusal, even if a public one is present too.
        def mixed(host: str, port: int, *a: Any, **k: Any):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port)),
            ]

        monkeypatch.setattr(socket, "getaddrinfo", mixed)
        with pytest.raises(SsrfRefused):
            resolve_host("pub.test", 80)


class TestPinnedTransport:
    """The connection goes to the address that was checked, not re-resolved."""

    def test_url_rewritten_and_sni_kept(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
        seen: dict[str, Any] = {}

        real_handle = httpx.HTTPTransport.handle_request

        def spy(self: Any, request: httpx.Request) -> Any:
            seen["url"] = str(request.url)
            seen["sni"] = request.extensions.get("sni_hostname")
            seen["host_header"] = request.headers.get("host")
            seen["real"] = real_handle
            raise httpx.ConnectError("stop before connecting anywhere")

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", spy)
        transport = PinnedTransport("http://pub.test")
        request = httpx.Request("GET", "http://pub.test/v1/chat/completions")
        with pytest.raises(httpx.ConnectError):
            transport.handle_request(request)
        assert seen["url"].startswith("http://93.184.216.34/")
        assert seen["sni"] == "pub.test"
        assert seen["host_header"] == "pub.test"

    def test_rebind_refused_before_connect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
        transport = PinnedTransport("http://rebind.test")
        request = httpx.Request("GET", "http://rebind.test/")
        with pytest.raises(SsrfRefused):
            transport.handle_request(request)


class TestUnwrap:
    """The NAT64 unwrap really unwraps (fails on the old dead-code branch)."""

    def test_nat64_unwraps_to_embedded_ipv4(self) -> None:
        from sip_relay.ssrf import _unwrap_ipv4

        assert _unwrap_ipv4(_ip("64:ff9b::102:304")) == _ip("1.2.3.4")  # type: ignore[arg-type]

    def test_mapped_unwraps(self) -> None:
        from sip_relay.ssrf import _unwrap_ipv4

        assert _unwrap_ipv4(_ip("::ffff:127.0.0.1")) == _ip("127.0.0.1")  # type: ignore[arg-type]

    def test_plain_ipv6_not_unwrapped(self) -> None:
        from sip_relay.ssrf import _unwrap_ipv4

        assert _unwrap_ipv4(_ip("2606:2800:220:1:248:1893:25c8:1946")) is None  # type: ignore[arg-type]


class TestRedirects:
    """The production factory never follows redirects, and a rebinding target
    gets a clean 400, not a 500."""

    def test_default_factory_does_not_follow_redirects(self) -> None:
        from sip_relay.app import default_client_factory

        client = default_client_factory("http://pub.test")
        assert client.follow_redirects is False

    def test_refused_target_returns_400(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
        kp = KeyPair.generate()
        manifest = sign_provider_manifest(
            build_provider_manifest(
                provider_pubkey=kp.public_key_str,
                models=["qwen-coder-7b"],
                runtime_adapters=["llama.cpp"],
                pricing_unit="test",
                published_at="2026-06-30T00:00:00Z",
                manifest_uri="http://rebind.test",
            ),
            kp,
        )
        app = create_relay_app()  # real default_client_factory, real pinning
        client = TestClient(app, raise_server_exceptions=True)
        target = {"base_url": "http://rebind.test", "manifest": manifest}
        resp = client.post("/sip/v1/relay", json={"target": target, "completion": {}})
        assert resp.status_code == 400
        assert "non-public" in resp.json()["error"]


def _ip(text: str) -> Any:
    import ipaddress

    return ipaddress.ip_address(text)
