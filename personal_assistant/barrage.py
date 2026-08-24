"""PA-owned normalization, gating and delivery for desktop barrage events."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from . import assistant_personality, storage, ws_manager

DEFAULT_SETTINGS = {
    "enabled": True,
    "quiet_mode": False,
    "paused_until": "",
    "position": "top",
    "font_size": 24,
    "opacity": 0.92,
    "duration_seconds": 8,
    "theme": "contrast",
    "display_id": "active",
}

_EVENT_POLICY = {
    "reminder": ("high", timedelta(minutes=10)),
    "intervention": ("medium", timedelta(minutes=5)),
    "assistant_message": ("medium", timedelta(minutes=2)),
    "game_barrage": ("low", timedelta(seconds=30)),
    "course_note": ("low", timedelta(minutes=5)),
    "test": ("low", timedelta(seconds=30)),
}


async def _emit(event_type: str, payload: dict) -> int:
    return await ws_manager.manager.broadcast(event_type, payload, roles={"overlay"})


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current


def _text(event_type: str, payload: dict) -> str:
    if event_type == "reminder":
        value = payload.get("what")
    elif event_type == "intervention":
        value = payload.get("message")
    elif event_type == "course_note":
        value = payload.get("note") or payload.get("title")
    else:
        value = payload.get("text")
    text = " ".join(str(value or "").split())
    return text[:40]


def from_event(
    event_type: str, payload: dict, *, now: datetime | None = None
) -> dict | None:
    policy = _EVENT_POLICY.get(event_type)
    if policy is None:
        return None
    text = _text(event_type, payload)
    if not text:
        return None
    current = _now(now)
    priority, lifetime = policy
    source_id = str(payload.get("id") or "").strip()
    if source_id:
        event_id = f"{event_type}:{source_id}"
    else:
        digest = hashlib.sha256(
            f"{event_type}\0{text}\0{current.isoformat()}".encode("utf-8")
        ).hexdigest()[:20]
        event_id = f"{event_type}:{digest}"
    personality = assistant_personality.current()
    return {
        "id": event_id,
        "kind": event_type,
        "priority": priority,
        "text": text,
        "created_at": current.isoformat(),
        "expires_at": (current + lifetime).isoformat(),
        "personality_version": personality["version"],
        "style": personality["barrage_style"],
        "assistant_name": personality["name"],
        "evidence": "present" if payload.get("evidence") else "",
    }


def is_expired(event: dict, now: datetime | None = None) -> bool:
    value = event.get("expires_at")
    if not value:
        return False
    expires_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return expires_at <= _now(now)


def is_paused(settings: dict, now: datetime | None = None) -> bool:
    paused_until = settings.get("paused_until")
    if not paused_until:
        return False
    paused = datetime.fromisoformat(str(paused_until).replace("Z", "+00:00"))
    return paused > _now(now)


def allowed(
    event: dict, settings: dict, *, now: datetime | None = None
) -> bool:
    current = _now(now)
    if not settings.get("enabled", True) or is_expired(event, current):
        return False
    if is_paused(settings, current):
        return False
    if settings.get("quiet_mode") and event.get("priority") != "high":
        return False
    initiative = assistant_personality.current().get("initiative", "balanced")
    if initiative == "quiet" and event.get("priority") != "high":
        return False
    return True


def _validate_settings(value: dict) -> dict:
    merged = {**DEFAULT_SETTINGS, **value}
    if not isinstance(merged["enabled"], bool) or not isinstance(merged["quiet_mode"], bool):
        raise ValueError("enabled and quiet_mode must be booleans")
    if merged["position"] not in {"top", "center", "bottom"}:
        raise ValueError("position must be top, center or bottom")
    if not isinstance(merged["font_size"], int) or not 14 <= merged["font_size"] <= 72:
        raise ValueError("font_size must be an integer from 14 to 72")
    if isinstance(merged["opacity"], bool) or not isinstance(merged["opacity"], (int, float)) or not 0.2 <= merged["opacity"] <= 1:
        raise ValueError("opacity must be from 0.2 to 1")
    if not isinstance(merged["duration_seconds"], int) or not 3 <= merged["duration_seconds"] <= 30:
        raise ValueError("duration_seconds must be an integer from 3 to 30")
    if merged["theme"] not in {"contrast", "light", "dark"}:
        raise ValueError("theme must be contrast, light or dark")
    display_id = str(merged["display_id"] or "").strip()
    if not display_id:
        raise ValueError("display_id must not be empty")
    merged["display_id"] = display_id
    paused_until = str(merged.get("paused_until") or "")
    if paused_until:
        datetime.fromisoformat(paused_until.replace("Z", "+00:00"))
    merged["paused_until"] = paused_until
    merged["opacity"] = float(merged["opacity"])
    return merged


def get_settings() -> dict:
    saved = storage.get_barrage_settings()
    return _validate_settings(saved or {})


def save_settings(value: dict) -> dict:
    settings = _validate_settings(value)
    storage.save_barrage_settings(settings)
    return settings


def patch_settings(patch: dict) -> dict:
    with storage.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT config_json FROM barrage_settings WHERE singleton=1"
        ).fetchone()
        import json

        current = json.loads(row["config_json"]) if row else DEFAULT_SETTINGS
        settings = _validate_settings({**current, **patch})
        connection.execute(
            "INSERT INTO barrage_settings(singleton,config_json,updated_at) VALUES(1,?,?) "
            "ON CONFLICT(singleton) DO UPDATE SET config_json=excluded.config_json, "
            "updated_at=excluded.updated_at",
            (json.dumps(settings, ensure_ascii=False), storage.now_iso()),
        )
        connection.commit()
    return settings


async def publish(event_type: str, payload: dict) -> dict | None:
    event = from_event(event_type, payload)
    if event is None:
        return None
    if not allowed(event, get_settings()):
        storage.add_barrage_delivery(event, "dropped")
        return None
    delivered = await _emit(ws_manager.EV_BARRAGE, event)
    storage.add_barrage_delivery(event, "sent" if delivered else "attempted")
    return event
