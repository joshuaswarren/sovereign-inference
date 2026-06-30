# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for the in-process ASGI client transport (in-process provider routing)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from sip_router import in_process_client


def _echo_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    @app.post("/echo")
    async def echo(body: dict[str, Any]) -> dict[str, Any]:
        return {"got": body}

    return app


def test_in_process_client_drives_an_asgi_app_without_a_socket() -> None:
    client = in_process_client(_echo_app(), "http://in-process")
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": "ok"}


def test_in_process_client_supports_post_bodies() -> None:
    client = in_process_client(_echo_app(), "http://in-process")
    resp = client.post("/echo", json={"hello": "world"})
    assert resp.status_code == 200
    assert resp.json() == {"got": {"hello": "world"}}


def test_in_process_client_composes_when_one_app_calls_another() -> None:
    # The transport runs each request in its own thread/event loop, so an outer
    # app can call an inner app through another in-process client without an
    # "event loop already running" error (the relay-into-provider case).
    inner = _echo_app()
    outer = FastAPI()

    @outer.get("/proxy")
    def proxy() -> dict[str, Any]:
        client = in_process_client(inner, "http://inner")
        return {"inner": client.get("/ping").json()}

    client = in_process_client(outer, "http://outer")
    resp = client.get("/proxy")
    assert resp.status_code == 200
    assert resp.json() == {"inner": {"pong": "ok"}}
