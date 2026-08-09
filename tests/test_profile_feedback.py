from __future__ import annotations

from personal_assistant import distill, storage


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

    merged = distill.current_profile()
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

    assert distill.current_profile()["preferences"] == ["茶"]
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

    assert distill.current_profile()["preferences"] == []
    assert storage.deactivate_profile_feedback(feedback_id) is True
    assert distill.current_profile()["preferences"] == ["咖啡"]
    rows = storage.list_profile_feedback(active_only=False)
    assert rows[0]["active"] == 0


def test_distillation_uses_inferred_profile_not_feedback_overrides(tmp_path, monkeypatch) -> None:
    database = tmp_path / "distill-profile.db"
    monkeypatch.setattr(storage.config, "sqlite_path", lambda: database)
    storage.save_persona_version({"preferences": ["咖啡"]}, "inferred")
    storage.add_profile_feedback(
        dimension="preferences",
        value="茶",
        action="add",
        evidence_kind="user_statement",
        evidence="用户明确纠正",
    )
    monkeypatch.setattr(
        distill,
        "_memories_for_distill",
        lambda: [{"kind": "event", "content": "今天散步", "evidence": "segment:s1"}],
    )
    original_get = distill.config.get
    monkeypatch.setattr(
        distill.config,
        "get",
        lambda path, default=None: 1
        if path == "distill.min_segments_for_distill"
        else original_get(path, default),
    )
    monkeypatch.setattr(storage.config, "persona_path", lambda: tmp_path / "profile.json")
    class RecordingLLM:
        def __init__(self):
            self.user = ""

        def chat_json(self, _system, user):
            self.user = user
            return {"profile": {"preferences": ["咖啡"]}, "change_summary": "依据 segment:s1"}

    model = RecordingLLM()
    result = distill.DistillationEngine(llm=model).run()

    assert result["skipped"] is False
    current_block = model.user.split("Recent memories (JSON):", 1)[0]
    assert "咖啡" in current_block
    assert "茶" not in current_block
    assert storage.latest_persona()[0]["preferences"] == ["咖啡"]
    assert distill.current_profile()["preferences"] == ["咖啡", "茶"]
