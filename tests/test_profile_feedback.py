"""test_profile_feedback.py — profile_feedback（保留于 storage）+ memory_bridge 合并。

记忆后端已接入融合记忆系统：current_profile = persona_versions 基底 + 时刻层情感 + 反馈纠正。
"""
from __future__ import annotations

from personal_assistant import memory_bridge, storage


def test_user_correction_is_separate_from_inferred_profile(tmp_path, monkeypatch) -> None:
    database = tmp_path / "profile.db"
    monkeypatch.setattr(storage.config, "sqlite_path", lambda: database)
    storage.save_persona_version({"preferences": ["咖啡"]}, "inferred")

    feedback_id = storage.add_profile_feedback(
        dimension="preferences",
        value="茶",
        action="add",
        evidence_kind="user_statement",
        evidence="用户明确纠正",
    )

    merged = memory_bridge.current_profile()
    assert "茶" in merged["preferences"]
    assert storage.latest_persona()[0]["preferences"] == ["咖啡"]
    assert feedback_id


def test_profile_item_can_be_suppressed_without_deleting_history(tmp_path, monkeypatch) -> None:
    database = tmp_path / "profile.db"
    monkeypatch.setattr(storage.config, "sqlite_path", lambda: database)
    storage.save_persona_version({"preferences": ["咖啡", "茶"]}, "inferred")

    storage.add_profile_feedback(
        dimension="preferences",
        value="咖啡",
        action="suppress",
        evidence_kind="user_statement",
        evidence="用户明确否认",
    )

    assert memory_bridge.current_profile()["preferences"] == ["茶"]
    assert storage.latest_persona()[0]["preferences"] == ["咖啡", "茶"]


def test_deleting_feedback_restores_inferred_value_but_keeps_audit_row(tmp_path, monkeypatch) -> None:
    database = tmp_path / "profile.db"
    monkeypatch.setattr(storage.config, "sqlite_path", lambda: database)
    storage.save_persona_version({"preferences": ["咖啡"]}, "inferred")
    feedback_id = storage.add_profile_feedback(
        dimension="preferences",
        value="咖啡",
        action="suppress",
        evidence_kind="user_statement",
        evidence="暂时不喜欢",
    )

    assert memory_bridge.current_profile()["preferences"] == []
    assert storage.deactivate_profile_feedback(feedback_id) is True
    assert memory_bridge.current_profile()["preferences"] == ["咖啡"]
    rows = storage.list_profile_feedback(active_only=False)
    assert rows[0]["active"] == 0
