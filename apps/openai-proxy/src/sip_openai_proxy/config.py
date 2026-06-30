# SPDX-License-Identifier: AGPL-3.0-or-later
"""Persisted onboarding/runtime configuration for the desktop app server.

The desktop app needs to remember, across restarts, *where inference comes from*:
the providers and discovery directories the user added during onboarding, an
optional local API key, the bearer token presented to gateways, whether the
first-run flow is complete, and which local model (if any) to re-front on boot.

This module is pure data + atomic file persistence — no network, no servers — so
it is fully unit-testable. Turning a config into a live routing registry lives in
:mod:`sip_openai_proxy.server`, which owns the discovery/serving boundaries.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sip_router import ProviderEntry

CONFIG_VERSION = 1
_CONFIG_FILE = "config.json"


@dataclass(frozen=True, slots=True)
class LocalUse:
    """The local model the user chose to front as a provider, for restore-on-boot."""

    runtime: str
    model: str

    def to_json(self) -> dict[str, Any]:
        return {"runtime": self.runtime, "model": self.model}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> LocalUse:
        return cls(runtime=str(data["runtime"]), model=str(data["model"]))


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Everything the desktop app persists about its inference sources."""

    providers: tuple[ProviderEntry, ...] = ()
    directories: tuple[str, ...] = ()
    api_key: str | None = None
    token: str | None = None
    onboarding_complete: bool = False
    local_use: LocalUse | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "version": CONFIG_VERSION,
            "providers": [{"base_url": e.base_url, "manifest": e.manifest} for e in self.providers],
            "directories": list(self.directories),
            "api_key": self.api_key,
            "token": self.token,
            "onboarding_complete": self.onboarding_complete,
            "local_use": self.local_use.to_json() if self.local_use else None,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> AppConfig:
        providers = tuple(
            ProviderEntry(base_url=str(p["base_url"]), manifest=dict(p["manifest"]))
            for p in data.get("providers", [])
        )
        local_use_raw = data.get("local_use")
        return cls(
            providers=providers,
            directories=tuple(str(d) for d in data.get("directories", [])),
            api_key=data.get("api_key"),
            token=data.get("token"),
            onboarding_complete=bool(data.get("onboarding_complete", False)),
            local_use=LocalUse.from_json(local_use_raw) if local_use_raw else None,
        )


def config_path(config_dir: str | Path) -> Path:
    """The path to ``config.json`` inside ``config_dir`` (the OS app-data dir)."""
    return Path(config_dir) / _CONFIG_FILE


def load_config(config_dir: str | Path) -> AppConfig:
    """Load the config from ``config_dir``; a missing file yields the default.

    A present-but-unparseable config raises :class:`ValueError` rather than
    silently discarding the user's setup — the caller decides how to recover.
    """
    path = config_path(config_dir)
    if not path.is_file():
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"config at {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"config at {path} must be a JSON object")
    try:
        return AppConfig.from_json(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"config at {path} is malformed: {exc}") from exc


def save_config(config_dir: str | Path, config: AppConfig) -> None:
    """Atomically write ``config`` to ``config_dir`` (creating parents).

    Writes to a temp file in the same directory and ``os.replace``s it into
    place, so a crash mid-write never leaves a half-written config.
    """
    directory = Path(config_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = config_path(directory)
    payload = json.dumps(config.to_json(), indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        Path(tmp_name).replace(path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
