"""MiniCPM-o 桌面感知结果校验、稳定、去重与 PA 事件映射。

场景证据和稳定策略改编自 LYiHub/pub-local-jarvis（MIT License）。
"""
from __future__ import annotations

import json
import re
import time
from collections import deque
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Any

from . import config, storage

_EVIDENCE_KEYS = (
    "game_surface",
    "interactive_gameplay",
    "game_video_or_stream",
    "fullscreen_game_media",
    "active_instruction",
    "course_surface",
    "instructional_audio",
    "ordinary_browsing",
    "non_game_surface",
)


def _clean_text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _normalize(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold())


def _similar(left: str, right: str) -> bool:
    a, b = _normalize(left), _normalize(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.78


def parse_perception(payload: dict[str, Any]) -> dict[str, Any]:
    """解析 Worker perception.completed；无合法 JSON 时拒绝，不猜测。"""
    source = str(payload.get("text", ""))
    start = source.find("{")
    if start < 0:
        raise ValueError("perception response contains no JSON object")
    try:
        value, _ = json.JSONDecoder().raw_decode(source[start:])
    except json.JSONDecodeError as exc:
        raise ValueError("perception response contains invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("perception JSON must be an object")

    scene = str(value.get("scene", "other")).casefold()
    if scene not in {"game", "course", "other"}:
        scene = "other"
    try:
        confidence = max(0.0, min(1.0, float(value.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    raw_evidence = value.get("scene_evidence")
    raw_evidence = raw_evidence if isinstance(raw_evidence, dict) else {}
    evidence = {key: raw_evidence.get(key) is True for key in _EVIDENCE_KEYS}

    if scene == "game":
        interactive = evidence["game_surface"] and evidence["interactive_gameplay"]
        fullscreen_media = (
            evidence["game_surface"]
            and evidence["game_video_or_stream"]
            and evidence["fullscreen_game_media"]
        )
        if confidence < 0.72 or evidence["non_game_surface"] or not (
            interactive or fullscreen_media
        ):
            scene = "other"
    elif scene == "course":
        corroborated = evidence["active_instruction"] and (
            evidence["course_surface"] or evidence["instructional_audio"]
        )
        browsing_only = evidence["ordinary_browsing"] and not (
            evidence["course_surface"] and evidence["instructional_audio"]
        )
        if confidence < 0.78 or not corroborated or browsing_only:
            scene = "other"

    raw_candidates = value.get("barrage_candidates")
    candidates: list[str] = []
    if scene == "game" and isinstance(raw_candidates, list):
        for candidate in raw_candidates:
            if not isinstance(candidate, str):
                continue
            cleaned = _clean_text(candidate, 30)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
            if len(candidates) == 3:
                break

    return {
        "request_id": payload.get("request_id"),
        "scene": scene,
        "confidence": confidence,
        "scene_evidence": evidence,
        "observation": _clean_text(value.get("observation"), 300),
        "barrage_candidates": candidates,
        "course_transcript": _clean_text(value.get("course_transcript"), 2000),
        "course_note": _clean_text(value.get("course_note"), 1000),
        "course_title": _clean_text(value.get("course_title"), 128),
        "capture_keyframe": value.get("capture_keyframe") is True,
        "keyframe_note": _clean_text(value.get("keyframe_note"), 300),
        "assistant_message": _clean_text(value.get("assistant_message"), 500),
    }


class SceneStabilizer:
    def __init__(self, enter_samples: int = 2, exit_samples: int = 2,
                 game_enter_samples: int = 2):
        if min(enter_samples, exit_samples, game_enter_samples) < 1:
            raise ValueError("sample counts must be positive")
        self.enter_samples = enter_samples
        self.exit_samples = exit_samples
        self.game_enter_samples = game_enter_samples
        self.current = "other"
        self._candidate: str | None = None
        self._streak = 0

    def observe(self, scene: str) -> str:
        scene = scene if scene in {"game", "course", "other"} else "other"
        if scene == self.current:
            self._candidate = None
            self._streak = 0
            return self.current
        self._streak = self._streak + 1 if self._candidate == scene else 1
        self._candidate = scene
        needed = (
            self.game_enter_samples if self.current == "other" and scene == "game"
            else self.enter_samples if self.current == "other"
            else self.exit_samples
        )
        if self._streak >= needed:
            self.current = scene
            self._candidate = None
            self._streak = 0
        return self.current


class PerceptionProcessor:
    """把原生事件转换为 PA 事件；持久化仍使用 PA 的存储边界。"""

    def __init__(
        self,
        *,
        memory_sink: Callable[[dict[str, Any]], Any] | None = None,
        now: Callable[[], float] = time.monotonic,
        activity_min_interval_seconds: float = 120.0,
        message_cooldown_seconds: float = 16.0,
    ) -> None:
        self.scene = SceneStabilizer()
        self.memory_sink = memory_sink or self._store_memory
        self.now = now
        self.activity_min_interval_seconds = activity_min_interval_seconds
        self.message_cooldown_seconds = message_cooldown_seconds
        self._last_activity: tuple[str, str, float] | None = None
        self._recent_messages: deque[tuple[str, float]] = deque(maxlen=8)
        self._seen_course_transcripts: deque[str] = deque(maxlen=16)

    @staticmethod
    def _store_memory(item: dict[str, Any]) -> None:
        source_id = str(item["evidence"])
        with storage.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO segments"
                "(id,source_file,start_sec,end_sec,text,speaker,language,created_at,processed,time_kind) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (source_id, "desktop-perception", 0.0, 0.0, item["content"], "user",
                 "zh", storage.now_iso(), 0, "received"),
            )
            connection.commit()
        storage.add_memory(
            {"segment_id": source_id, "kind": "event", "content": item["content"],
             "evidence": source_id},
            None,
        )

    def _record_activity(self, result: dict[str, Any], observed_scene: str, now: float) -> None:
        text = result["observation"]
        if not text or result["confidence"] < 0.6:
            return
        previous = self._last_activity
        if previous:
            previous_scene, previous_text, recorded_at = previous
            if observed_scene == previous_scene and (
                now - recorded_at < self.activity_min_interval_seconds
                or _similar(text, previous_text)
            ):
                return
        evidence = f"perception:{result['request_id']}"
        self.memory_sink({
            "content": text,
            "evidence": evidence,
            "scene": observed_scene,
            "confidence": result["confidence"],
        })
        self._last_activity = (observed_scene, text, now)

    def _message_available(self, text: str, now: float) -> bool:
        while self._recent_messages and now - self._recent_messages[0][1] > 60:
            self._recent_messages.popleft()
        return not any(
            now - emitted < self.message_cooldown_seconds or _similar(text, previous)
            for previous, emitted in self._recent_messages
        )

    def _queue_course_transcript(self, result: dict[str, Any]) -> Path | None:
        text = result["course_transcript"]
        if not text or any(_similar(text, previous) for previous in self._seen_course_transcripts):
            return None
        self._seen_course_transcripts.append(text)
        inbox = config.inbox_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        request_id = re.sub(r"[^A-Za-z0-9_-]", "-", str(result["request_id"] or "event"))
        path = inbox / f"omni-course-{request_id}.txt"
        path.write_text(text + "\n", encoding="utf-8")
        return path

    def handle(self, payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        topic = str(payload.get("type", "native_event"))
        if topic != "perception.completed":
            return [(topic.replace(".", "_"), dict(payload))]
        result = parse_perception(payload)
        observed_scene = result["scene"]
        previous_scene = self.scene.current
        display_scene = self.scene.observe(observed_scene)
        result["observed_scene"] = observed_scene
        result["scene"] = display_scene
        now = self.now()
        events: list[tuple[str, dict[str, Any]]] = [("perception", result)]
        if display_scene != previous_scene:
            events.append(("scene_changed", {"scene": display_scene,
                                              "confidence": result["confidence"]}))
        self._record_activity(result, display_scene, now)

        if display_scene == "game" and observed_scene == "game":
            for text in result["barrage_candidates"]:
                if self._message_available(text, now):
                    self._recent_messages.append((text, now))
                    events.append(("game_barrage", {"text": text,
                                                     "confidence": result["confidence"]}))
                    break
        elif display_scene == "course" and observed_scene == "course":
            transcript = self._queue_course_transcript(result)
            if result["course_note"]:
                events.append(("course_note", {
                    "title": result["course_title"],
                    "note": result["course_note"],
                    "transcript_file": str(transcript) if transcript else "",
                    "capture_keyframe": result["capture_keyframe"],
                    "keyframe_note": result["keyframe_note"],
                }))
        elif display_scene == "other" and result["assistant_message"]:
            text = result["assistant_message"]
            if self._message_available(text, now):
                self._recent_messages.append((text, now))
                events.append(("assistant_message", {"text": text,
                                                      "source": "perception"}))
        return events
