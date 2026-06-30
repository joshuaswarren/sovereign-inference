# SPDX-License-Identifier: AGPL-3.0-or-later
"""Route to an in-process provider app without opening a socket.

A SIP provider is normally reached over HTTP, but for a *locally fronted* model
the provider gateway lives in the same process as the router. Spinning up a real
``uvicorn`` server on a loopback port just to call ourselves invites a whole
class of bugs (startup races, port collisions, leaked threads on reconfigure).

Instead, :class:`ThreadedASGITransport` lets an ordinary :class:`httpx.Client`
drive an ASGI app directly. Each request runs via ``asyncio.run`` inside a fresh
worker thread, so it composes even when one ASGI app calls another (e.g. a relay
forwarding into a provider) without an "event loop is already running" error.

``SovereignClient(client_factory=...)`` takes exactly this ``(base_url) -> Client``
shape, so an in-process gateway becomes a routing target with no special casing —
and reconfiguring is an atomic swap of the app object, never a server restart.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

import httpx


class ThreadedASGITransport(httpx.BaseTransport):
    """Drive an ASGI app via ``asyncio.run`` inside a worker thread.

    A worker thread has no running event loop, so this composes safely even when
    one ASGI app forwards into another — unlike a bare ``asyncio.run`` on the
    calling thread (which raises if a loop is already running).
    """

    def __init__(self, app: Any) -> None:
        self._async = httpx.ASGITransport(app=app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        async def _go() -> tuple[int, list[tuple[bytes, bytes]], bytes]:
            response = await self._async.handle_async_request(request)
            body = await response.aread()
            await response.aclose()
            return response.status_code, list(response.headers.raw), body

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            status, headers, body = pool.submit(lambda: asyncio.run(_go())).result()
        return httpx.Response(status_code=status, headers=headers, content=body, request=request)

    def close(self) -> None:
        """No persistent resources to release."""


def in_process_client(app: Any, base_url: str) -> httpx.Client:
    """A real ``httpx.Client`` that drives ``app`` directly, with no socket."""
    return httpx.Client(transport=ThreadedASGITransport(app), base_url=base_url)
