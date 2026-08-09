from __future__ import annotations

import json
from pathlib import Path

from personal_assistant import desktop_connection


def test_publish_writes_versioned_connection_atomically(tmp_path: Path) -> None:
    target = tmp_path / "desktop-connection.json"

    result = desktop_connection.publish(
        base_url="http://127.0.0.1:8004/",
        token="secret-token",
        path=target,
    )

    assert result == target
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "version": 1,
        "base_url": "http://127.0.0.1:8004",
        "token": "secret-token",
    }
    assert not target.with_suffix(".tmp").exists()


def test_default_path_stays_in_current_user_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("PA_DESKTOP_CONNECTION_FILE", raising=False)

    assert desktop_connection.connection_path() == (
        tmp_path / "PersonalAssistant" / "desktop-connection.json"
    )


def test_explicit_connection_path_override(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "shared" / "connection.json"
    monkeypatch.setenv("PA_DESKTOP_CONNECTION_FILE", str(target))

    assert desktop_connection.connection_path() == target
