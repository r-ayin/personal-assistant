from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from personal_assistant import assistant_personality, barrage, config, storage

NOW = datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc)


def test_chat_reply_is_never_a_barrage() -> None:
    assert barrage.from_event("chat_reply", {"text": "页面回复"}, now=NOW) is None


def test_due_reminder_is_high_priority_and_expires(monkeypatch) -> None:
    monkeypatch.setattr(
        assistant_personality,
        "current",
        lambda: {**assistant_personality.from_preset("gentle"), "version": 2},
    )
    event = barrage.from_event(
        "reminder", {"id": "r1", "what": "十分钟后开会", "evidence": "r1"}, now=NOW
    )

    assert event is not None
    assert event["id"] == "reminder:r1"
    assert event["kind"] == "reminder"
    assert event["priority"] == "high"
    assert event["text"] == "十分钟后开会"
    assert event["personality_version"] == 2
    assert datetime.fromisoformat(event["expires_at"]) > NOW


def test_quiet_mode_only_allows_high_priority() -> None:
    settings = {**barrage.DEFAULT_SETTINGS, "quiet_mode": True}
    assert barrage.allowed({"priority": "medium", "kind": "intervention"}, settings, now=NOW) is False
    assert barrage.allowed({"priority": "high", "kind": "reminder"}, settings, now=NOW) is True


def test_paused_and_expired_events_are_rejected() -> None:
    paused = {**barrage.DEFAULT_SETTINGS, "paused_until": (NOW + timedelta(minutes=1)).isoformat()}
    assert barrage.allowed({"priority": "high", "expires_at": (NOW + timedelta(minutes=2)).isoformat()}, paused, now=NOW) is False
    expired = {"expires_at": (NOW - timedelta(seconds=1)).isoformat(), "priority": "high"}
    assert barrage.is_expired(expired, NOW) is True


def test_settings_round_trip_and_validate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "barrage.db")
    saved = barrage.save_settings({**barrage.DEFAULT_SETTINGS, "opacity": 0.75, "font_size": 30})

    assert saved["opacity"] == 0.75
    assert barrage.get_settings()["font_size"] == 30


def test_publish_records_only_metadata_and_emits_normalized_event(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "publish.db")
    sent: list[tuple[str, dict]] = []

    async def emit(event_type: str, payload: dict) -> int:
        sent.append((event_type, payload))
        return 1

    monkeypatch.setattr(barrage, "_emit", emit)
    payload = {"id": "iv1", "message": "起来活动一下，喝口水再继续", "evidence": ["memory:private"]}
    event = asyncio.run(barrage.publish("intervention", payload))

    assert event is not None
    assert sent == [("barrage", event)]
    row = storage.list_barrage_deliveries()[0]
    assert row["status"] == "sent"
    assert "private" not in row["evidence"]


def test_concurrent_setting_patches_preserve_independent_fields(tmp_path, monkeypatch) -> None:
    import threading

    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "concurrent-settings.db")
    barrage.save_settings(barrage.DEFAULT_SETTINGS)
    barrier = threading.Barrier(3)
    results: list[dict] = []

    def apply(patch: dict) -> None:
        barrier.wait()
        results.append(barrage.patch_settings(patch))

    first = threading.Thread(target=apply, args=({"quiet_mode": True},))
    second = threading.Thread(target=apply, args=({"opacity": 0.61},))
    first.start()
    second.start()
    barrier.wait()
    first.join()
    second.join()

    current = barrage.get_settings()
    assert current["quiet_mode"] is True
    assert current["opacity"] == 0.61
    assert len(results) == 2

