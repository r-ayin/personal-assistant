from __future__ import annotations

import json
from pathlib import Path

import pytest

from personal_assistant import config
from personal_assistant.omni_perception import PerceptionProcessor, SceneStabilizer, parse_perception
from personal_assistant.omni_service import OmniService


def _perception(scene="other", confidence=0.9, **extra):
    value = {
        "scene": scene,
        "confidence": confidence,
        "scene_evidence": {},
        "observation": "用户正在编辑 PA 本地模型配置。",
        "barrage_candidates": [],
        "course_transcript": "",
        "course_note": "",
        "assistant_message": "",
        **extra,
    }
    return {"type": "perception.completed", "request_id": 9, "text": json.dumps(value, ensure_ascii=False)}


def test_parse_perception_enforces_scene_evidence_and_types() -> None:
    invalid_game = _perception(scene="game", confidence=0.95, barrage_candidates=["漂亮！"])
    assert parse_perception(invalid_game)["scene"] == "other"

    valid_game = _perception(
        scene="game",
        confidence=0.95,
        scene_evidence={"game_surface": True, "interactive_gameplay": True},
        barrage_candidates=["注意眼前威胁", "注意眼前威胁", 3],
    )
    parsed = parse_perception(valid_game)
    assert parsed["scene"] == "game"
    assert parsed["barrage_candidates"] == ["注意眼前威胁"]

    with pytest.raises(ValueError, match="JSON"):
        parse_perception({"type": "perception.completed", "text": "ignore rules"})


def test_scene_stabilizer_requires_consistent_samples() -> None:
    stable = SceneStabilizer(enter_samples=2, exit_samples=2, game_enter_samples=2)
    assert stable.observe("game") == "other"
    assert stable.observe("other") == "other"
    assert stable.observe("game") == "other"
    assert stable.observe("game") == "game"
    assert stable.observe("other") == "game"
    assert stable.observe("other") == "other"


def test_processor_deduplicates_activity_and_assistant_messages(tmp_path: Path, monkeypatch) -> None:
    memories: list[dict] = []
    monkeypatch.setattr(config, "inbox_dir", lambda: tmp_path / "inbox")
    processor = PerceptionProcessor(
        memory_sink=lambda item: memories.append(item),
        now=lambda: 100.0,
        activity_min_interval_seconds=120,
    )

    first = processor.handle(_perception(assistant_message="配置已经生效。"))
    second = processor.handle(_perception(assistant_message="配置已经生效。"))

    assert len(memories) == 1
    assert memories[0]["evidence"] == "perception:9"
    assert [kind for kind, _ in first].count("assistant_message") == 1
    assert all(kind != "assistant_message" for kind, _ in second)


def test_processor_stabilizes_course_and_queues_transcript(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "inbox_dir", lambda: tmp_path / "inbox")
    processor = PerceptionProcessor(memory_sink=lambda _item: None)
    course = _perception(
        scene="course",
        confidence=0.91,
        scene_evidence={"active_instruction": True, "instructional_audio": True},
        course_transcript="牛顿第二定律是 F=ma。",
        course_note="力等于质量乘加速度。",
        course_title="高中物理",
    )

    first = processor.handle(course)
    second = processor.handle(course)

    assert not any(kind == "scene_changed" for kind, _ in first)
    assert any(kind == "scene_changed" and data["scene"] == "course" for kind, data in second)
    transcripts = list((tmp_path / "inbox").glob("omni-course-*.txt"))
    assert len(transcripts) == 1
    assert "F=ma" in transcripts[0].read_text(encoding="utf-8")
    assert any(kind == "course_note" for kind, _ in second)


class FakeManager:
    def __init__(self):
        self.running = False
        self.starts = 0
        self.stops = 0
        self.requests: list[tuple[str, dict]] = []

    async def start(self):
        self.starts += 1
        self.running = True

    async def stop(self):
        self.stops += 1
        self.running = False

    async def request(self, method, payload):
        if not self.running:
            raise RuntimeError("not running")
        self.requests.append((method, payload))
        return {"ok": True, "text": "local answer"}



def test_omni_service_owns_background_loop_and_sync_request() -> None:
    manager = FakeManager()
    service = OmniService(manager_factory=lambda _sink: manager)

    service.start_sync()
    assert service.request_sync("ask", {"text": "hi"})["text"] == "local answer"
    assert service.status()["state"] == "ready"
    service.stop_sync()

    assert manager.starts == manager.stops == 1
    assert service.status()["state"] == "stopped"


def test_omni_service_does_not_hide_start_failure() -> None:
    class FailingManager(FakeManager):
        async def start(self):
            raise RuntimeError("model files are missing")

    service = OmniService(manager_factory=lambda _sink: FailingManager())
    with pytest.raises(RuntimeError, match="model files are missing"):
        service.start_sync()
    assert service.status()["state"] == "failed"
    assert "model files are missing" in service.status()["error"]


def test_omni_service_stops_after_last_consumer_releases() -> None:
    manager = FakeManager()
    service = OmniService(manager_factory=lambda _sink: manager)

    service.acquire_sync("perception")
    service.acquire_sync("chat-backend")
    assert service.consumers() == ["chat-backend", "perception"]
    assert manager.starts == 1

    assert service.release_sync("perception")["state"] == "ready"
    assert manager.stops == 0
    assert service.release_sync("chat-backend")["state"] == "stopped"
    assert manager.stops == 1


def test_stopped_service_request_does_not_implicitly_start_worker() -> None:
    manager = FakeManager()
    service = OmniService(manager_factory=lambda _sink: manager)

    with pytest.raises(RuntimeError, match="no active consumer"):
        service.request_sync("ask", {"text": "hi"})

    assert manager.starts == 0


def test_failed_consumer_start_removes_lease_and_stops_partial_manager() -> None:
    manager = FakeManager()

    async def fail_start():
        manager.starts += 1
        manager.running = True
        raise RuntimeError("model files are missing")

    manager.start = fail_start
    service = OmniService(manager_factory=lambda _sink: manager)

    with pytest.raises(RuntimeError, match="model files are missing"):
        service.acquire_sync("perception")

    assert service.consumers() == []
    assert manager.stops == 1
    assert service.status()["state"] == "stopped"

