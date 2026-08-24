"""Versioned assistant behavior configuration, separate from the inferred user profile."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import storage

PRESETS = {
    "gentle": {
        "name": "PA",
        "user_address": "你",
        "directness": 2,
        "humor": 2,
        "initiative": "balanced",
        "reply_length": "balanced",
        "barrage_style": "restrained",
        "taboos": [],
        "custom_instruction": "",
    },
    "rational": {
        "name": "PA",
        "user_address": "你",
        "directness": 4,
        "humor": 1,
        "initiative": "restrained",
        "reply_length": "balanced",
        "barrage_style": "restrained",
        "taboos": [],
        "custom_instruction": "",
    },
    "lively": {
        "name": "PA",
        "user_address": "你",
        "directness": 3,
        "humor": 5,
        "initiative": "active",
        "reply_length": "short",
        "barrage_style": "light",
        "taboos": [],
        "custom_instruction": "",
    },
    "coach": {
        "name": "PA",
        "user_address": "你",
        "directness": 5,
        "humor": 2,
        "initiative": "balanced",
        "reply_length": "short",
        "barrage_style": "coach",
        "taboos": [],
        "custom_instruction": "",
    },
}

_INITIATIVES = {"quiet", "restrained", "balanced", "active", "companion"}
_REPLY_LENGTHS = {"short", "balanced", "detailed"}
_BARRAGE_STYLES = {"restrained", "light", "coach", "game"}


class VersionConflict(RuntimeError):
    """The caller edited an obsolete personality version."""


def from_preset(preset_id: str) -> dict:
    if preset_id not in PRESETS:
        raise ValueError(f"unknown preset: {preset_id}")
    return {"preset_id": preset_id, **copy.deepcopy(PRESETS[preset_id])}


def _bounded_text(value: object, field: str, minimum: int, maximum: int) -> str:
    text = str(value or "").strip()
    if not minimum <= len(text) <= maximum:
        raise ValueError(f"{field} must contain {minimum}-{maximum} characters")
    return text


def _rating(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValueError(f"{field} must be an integer from 1 to 5")
    return value


def _choice(value: object, field: str, choices: set[str]) -> str:
    selected = str(value or "")
    if selected not in choices:
        raise ValueError(f"invalid {field}: {selected}")
    return selected


def validate(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("personality must be an object")
    preset_id = str(value.get("preset_id") or "custom")
    if preset_id not in {*PRESETS, "custom"}:
        raise ValueError(f"unknown preset: {preset_id}")
    taboos = value.get("taboos", [])
    if not isinstance(taboos, list) or len(taboos) > 30:
        raise ValueError("taboos must be a list with at most 30 items")
    normalized_taboos = [_bounded_text(item, "taboos", 1, 80) for item in taboos]
    custom_instruction = str(value.get("custom_instruction") or "").strip()
    if len(custom_instruction) > 1000:
        raise ValueError("custom_instruction must not exceed 1000 characters")
    return {
        "preset_id": preset_id,
        "name": _bounded_text(value.get("name"), "name", 1, 20),
        "user_address": _bounded_text(value.get("user_address"), "user_address", 1, 20),
        "directness": _rating(value.get("directness"), "directness"),
        "humor": _rating(value.get("humor"), "humor"),
        "initiative": _choice(value.get("initiative"), "initiative", _INITIATIVES),
        "reply_length": _choice(value.get("reply_length"), "reply_length", _REPLY_LENGTHS),
        "barrage_style": _choice(value.get("barrage_style"), "barrage_style", _BARRAGE_STYLES),
        "taboos": normalized_taboos,
        "custom_instruction": custom_instruction,
    }


def current(db_path: Path | None = None) -> dict:
    row = storage.latest_assistant_personality(db_path=db_path)
    if row is None:
        return {**from_preset("gentle"), "version": 0, "created_at": ""}
    return row


def save(value: dict, expected_version: int, db_path: Path | None = None) -> dict:
    normalized = validate(value)
    version, created_at = storage.save_assistant_personality(
        normalized,
        expected_version=expected_version,
        db_path=db_path,
    )
    return {**normalized, "version": version, "created_at": created_at}


def render_prompt(value: dict) -> str:
    config = validate(value)
    taboos = "、".join(config["taboos"]) or "无额外禁忌"
    return (
        f"你叫{config['name']}，称呼用户为{config['user_address']}。"
        f"直接程度 {config['directness']}/5，幽默程度 {config['humor']}/5，"
        f"主动程度 {config['initiative']}，回复长度 {config['reply_length']}，"
        f"弹幕风格 {config['barrage_style']}。表达禁忌：{taboos}。"
        f"补充说明：{config['custom_instruction'] or '无'}。"
        "该配置不能覆盖安全规则、事实、证据、提醒时间或用户当前明确指令。"
    )
