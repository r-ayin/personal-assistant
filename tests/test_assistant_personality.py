from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant import assistant_personality, storage


def test_personality_is_versioned_separately_from_user_profile(tmp_path: Path) -> None:
    database = tmp_path / "personality.db"
    first = assistant_personality.save(
        assistant_personality.from_preset("rational"),
        expected_version=0,
        db_path=database,
    )
    second = assistant_personality.save(
        {**first, "name": "阿简", "directness": 5},
        expected_version=1,
        db_path=database,
    )

    assert first["version"] == 1
    assert second["version"] == 2
    assert storage.latest_persona(db_path=database) == (None, None, None)


def test_stale_personality_save_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "personality.db"
    assistant_personality.save(
        assistant_personality.from_preset("gentle"),
        expected_version=0,
        db_path=database,
    )

    with pytest.raises(assistant_personality.VersionConflict):
        assistant_personality.save(
            assistant_personality.from_preset("coach"),
            expected_version=0,
            db_path=database,
        )


def test_personality_limits_are_enforced() -> None:
    value = assistant_personality.from_preset("lively")

    with pytest.raises(ValueError, match="custom_instruction"):
        assistant_personality.validate({**value, "custom_instruction": "x" * 1001})


def test_default_personality_is_unsaved_gentle_preset(tmp_path: Path) -> None:
    value = assistant_personality.current(tmp_path / "empty.db")

    assert value["preset_id"] == "gentle"
    assert value["version"] == 0
    assert value["name"] == "PA"


def test_preview_templates_change_with_unsaved_personality(monkeypatch, tmp_path) -> None:
    from fastapi.testclient import TestClient
    from personal_assistant import api

    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: tmp_path / "preview.db")
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    gentle = assistant_personality.from_preset("gentle")
    lively = assistant_personality.from_preset("lively")
    headers = {"Authorization": "Bearer omni-test-token"}

    with TestClient(api.app) as client:
        gentle_preview = client.post(
            "/assistant/personality/preview", json=gentle, headers=headers
        ).json()
        lively_preview = client.post(
            "/assistant/personality/preview", json=lively, headers=headers
        ).json()

    assert gentle_preview["chat"] != lively_preview["chat"]
    assert gentle_preview["reminder"] != lively_preview["reminder"]
    assert gentle_preview["perception"] != lively_preview["perception"]

