"""Publish the PA-owned connection contract consumed by the desktop overlay."""
from __future__ import annotations

import json
import os
from pathlib import Path


def connection_path() -> Path:
    override = os.environ.get("PA_DESKTOP_CONNECTION_FILE")
    if override:
        return Path(override).expanduser()
    local_data = os.environ.get("LOCALAPPDATA")
    if local_data:
        root = Path(local_data)
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "PersonalAssistant" / "desktop-connection.json"


def publish(*, base_url: str, token: str, path: Path | None = None) -> Path:
    target = path or connection_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "base_url": str(base_url).rstrip("/"),
        "token": str(token),
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(target)
    return target


def publish_for_server(*, host: str, port: int, token: str) -> Path:
    public_host = "127.0.0.1" if host in {"0.0.0.0", "::", "[::]"} else host
    base_url = os.environ.get("PA_DESKTOP_BASE_URL") or f"http://{public_host}:{port}"
    return publish(base_url=base_url, token=token)
