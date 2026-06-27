"""distill.py — 蒸馏引擎：反思循环 → 更新结构化人格档案（版本化、带证据）。

run(): 取上次蒸馏后的新记忆，给 LLM [TASK:DISTILL] + 当前档案 → 新 profile + change_summary
→ storage.save_persona_version（落盘 data/persona/profile.json + DB 版本）。
原则：每项更新须可追溯到记忆，不接受 LLM 散文自评（change_summary 引 evidence）。
"""
from __future__ import annotations
import json

from . import config, storage
from .llm import get_llm

DIMENSIONS = ["personality", "values", "goals", "habits", "skills",
              "knowledge", "thinking_patterns", "preferences", "affective_baseline"]

SYSTEM_DISTILL = """[TASK:DISTILL]
你是人格蒸馏引擎。基于用户近期语音记忆，更新其结构化人格档案。
档案维度：personality(人格特质)、values(价值观)、goals(目标)、habits(习惯作息)、
skills(技能)、knowledge(知识地图)、thinking_patterns(思维模式)、preferences(偏好)、affective_baseline(情绪基线)。
规则：
- 只从提供的记忆归纳，不得编造。
- change_summary 必须引用记忆 evidence（如"依据 segment:s3"）。
- 保留旧档案中仍成立的内容，仅增量更新。
返回 JSON：{"profile":{<9 维度>}, "change_summary":"依据...做了哪些更新"}"""


def normalize(profile: dict) -> dict:
    p = dict(profile or {})
    for d in DIMENSIONS:
        p.setdefault(d, [] if d in ("skills", "knowledge", "preferences") else "")
    return p


def _memories_for_distill() -> list[dict]:
    last = storage.kv_get("last_distill_at")
    mems = storage.memories_all()
    if not last:
        return mems
    return [m for m in mems if (m.get("created_at") or "") > last]


def current_profile() -> dict:
    p, _sum, _v = storage.latest_persona()
    return normalize(p) if p else normalize({})


class DistillationEngine:
    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def run(self) -> dict:
        mems = _memories_for_distill()
        min_seg = config.get("distill.min_segments_for_distill", 5)
        if len(mems) < min_seg:
            return {"skipped": True, "reason": f"新记忆 {len(mems)} < {min_seg}", "memories": len(mems)}
        cur = current_profile()
        mem_json = [{"kind": m.get("kind"), "content": m.get("content"),
                     "evidence": m.get("evidence")} for m in mems]
        user = ("Current profile (JSON or null):\n" + json.dumps(cur, ensure_ascii=False)
                + "\nRecent memories (JSON):\n" + json.dumps(mem_json, ensure_ascii=False))
        out = self.llm.chat_json(SYSTEM_DISTILL, user)
        if not isinstance(out, dict) or "profile" not in out:
            # 重试一次，明确要求只返回 profile JSON
            out = self.llm.chat_json(
                "只返回 JSON：{\"profile\":{...9 维度...},\"change_summary\":\"...\"}，不要任何额外文字。",
                user + "\n（上次返回不合法，请严格返回 JSON 对象）")
        if not isinstance(out, dict) or "profile" not in out:
            return {"skipped": True, "reason": "LLM 未返回合法 profile"}
        profile = normalize(out["profile"])
        change = out.get("change_summary", "")
        version = storage.save_persona_version(profile, change)
        storage.kv_set("last_distill_at", storage.now_iso())
        return {"skipped": False, "version": version, "change_summary": change,
                "memories_distilled": len(mems)}
