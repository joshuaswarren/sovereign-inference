# SPDX-License-Identifier: Apache-2.0
"""Anchors: pluggable durable storage for SIP-AI provenance.

An :class:`Anchor` stores opaque bytes and returns a URI that resolves them
back. Two implementations ship here:

* :class:`LocalAnchor` — content-addressed files under a directory, ``local://``
  URIs. Offline, deterministic; used by tests, demos, and air-gapped nodes.
* :class:`ArweaveAnchor` — permanent storage on Arweave, ``ar://`` URIs.
  Resolution is plain HTTP against a gateway; submission goes through an
  injected ``submitter`` (the real one signs a transaction with the
  ``arweave-python-client`` optional dependency), so the anchor is fully
  unit-testable without a wallet or the network.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from .errors import AnchorError

# A submitter signs+posts an Arweave transaction and returns its tx id.
TxSubmitter = Callable[[bytes, str, dict[str, str]], str]


@runtime_checkable
class Anchor(Protocol):
    """Durable storage that stores bytes and resolves them back by URI."""

    scheme: str

    def put(self, data: bytes, *, content_type: str = ..., tags: dict[str, str] | None = ...) -> str:
        """Store ``data`` and return a URI that resolves it."""
        ...

    def get(self, uri: str) -> bytes:
        """Resolve a URI produced by :meth:`put` back to bytes."""
        ...


_DEFAULT_GATEWAY = "https://arweave.net"
_HTTP_TIMEOUT_S = 30.0


def _split_uri(uri: str, expected_scheme: str) -> str:
    scheme, sep, rest = uri.partition("://")
    if not sep or scheme != expected_scheme:
        raise AnchorError(f"expected a {expected_scheme}:// URI, got {uri!r}")
    if not rest:
        raise AnchorError(f"empty {expected_scheme}:// URI")
    return rest


class LocalAnchor:
    """Content-addressed file storage. URIs are ``local://<sha256-hex>``."""

    scheme = "local"

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> str:
        """Store ``data`` and return its ``local://`` URI (idempotent by content)."""
        digest = hashlib.sha256(data).hexdigest()
        path = self._root / digest
        if not path.exists():
            path.write_bytes(data)
        return f"local://{digest}"

    def get(self, uri: str) -> bytes:
        """Resolve a ``local://`` URI back to bytes."""
        digest = _split_uri(uri, self.scheme)
        path = self._root / digest
        try:
            return path.read_bytes()
        except OSError as exc:
            raise AnchorError(f"no local object for {uri!r}") from exc


class ArweaveAnchor:
    """Permanent storage on Arweave. URIs are ``ar://<tx-id>``.

    ``get`` resolves over HTTP against ``gateway``. ``put`` delegates to
    ``submitter``; without one configured it raises, because anchoring to
    Arweave requires a funded, signing wallet that the core does not assume.
    """

    scheme = "ar"

    def __init__(
        self,
        *,
        gateway: str = _DEFAULT_GATEWAY,
        client: httpx.Client | None = None,
        submitter: TxSubmitter | None = None,
    ) -> None:
        self._gateway = gateway.rstrip("/")
        self._client = client
        self._submitter = submitter

    def put(
        self,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> str:
        """Sign+post ``data`` via the configured submitter; return its ``ar://`` URI."""
        if self._submitter is None:
            raise AnchorError(
                "ArweaveAnchor has no submitter configured; pass submitter=... "
                "(e.g. arweave_submitter(wallet_path)) to publish to Arweave"
            )
        tx_id = self._submitter(data, content_type, dict(tags or {}))
        return f"ar://{tx_id}"

    def get(self, uri: str) -> bytes:
        """Resolve an ``ar://`` URI to bytes via the Arweave gateway."""
        tx_id = _split_uri(uri, self.scheme)
        owns = self._client is None
        client = self._client or httpx.Client(timeout=_HTTP_TIMEOUT_S)
        try:
            response = client.get(f"{self._gateway}/{tx_id}")
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise AnchorError(f"failed to resolve {uri!r} from {self._gateway}") from exc
        finally:
            if owns:
                client.close()


def arweave_submitter(wallet_path: str, *, gateway: str = _DEFAULT_GATEWAY) -> TxSubmitter:
    """Build a real Arweave submitter backed by ``arweave-python-client``.

    Imported lazily so the package has no hard dependency on a wallet library;
    install the ``live`` extra to use it. The returned callable signs a data
    transaction (with the given content-type and tags) and posts it, returning
    the transaction id.
    """

    def submit(data: bytes, content_type: str, tags: dict[str, str]) -> str:
        try:
            from arweave import Transaction, Wallet  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise AnchorError(
                "arweave-python-client is not installed; `pip install sip-arweave[live]` to publish to Arweave"
            ) from exc

        wallet = Wallet(wallet_path)
        transaction = Transaction(wallet, data=data)
        transaction.add_tag("Content-Type", content_type)
        for name, value in tags.items():
            transaction.add_tag(name, value)
        transaction.sign()
        transaction.send()
        return str(transaction.id)

    return submit
