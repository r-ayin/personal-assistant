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

SYSTEM_NARRATIVE = """[TASK:NARRATIVE]
你是用户叙事档案生成器。输入 profile（9 维结构化档案）、scene_navigation（活跃场景）、
old_narrative（上一版叙事，可能为空）。输出 ≤2000 字符的叙事体档案（纯文本，不用 JSON）：
第一人称观察者视角，含核心特质、长期偏好、近期目标/场景、交互要点。
增量模式（有 old_narrative）：保留稳定信息，追加/修订演变部分。只输出叙事文本。"""


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


def inferred_profile() -> dict:
    inferred, _summary, _version = storage.latest_persona()
    return normalize(inferred) if inferred else normalize({})


def current_profile() -> dict:
    effective = inferred_profile()
    for feedback in storage.list_profile_feedback():
        dimension = feedback["dimension"]
        if dimension not in DIMENSIONS:
            continue
        value = feedback["value"]
        current = effective[dimension]
        if isinstance(current, list):
            if feedback["action"] == "add" and value not in current:
                current.append(value)
            elif feedback["action"] == "suppress":
                effective[dimension] = [item for item in current if item != value]
        elif feedback["action"] == "add":
            effective[dimension] = value
        elif feedback["action"] == "suppress" and current == value:
            effective[dimension] = ""
    return effective


class DistillationEngine:
    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def run(self) -> dict:
        mems = _memories_for_distill()
        min_seg = config.get("distill.min_segments_for_distill", 5)
        if len(mems) < min_seg:
            return {"skipped": True, "reason": f"新记忆 {len(mems)} < {min_seg}", "memories": len(mems)}
        # v0.10：distill 前先整合未处理的 L2 场景（narrative 需要场景导航）
        try:
            from . import scenes
            if scenes.pending_count() > 0:
                scenes.integrate(llm=self.llm)
        except Exception as e:
            print(f"[distill] scene integrate skipped: {e}")
        cur = inferred_profile()
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
        narrative = self._gen_narrative(profile)
        version = storage.save_persona_version(profile, change, narrative=narrative)
        storage.kv_set("last_distill_at", storage.now_iso())
        return {"skipped": False, "version": version, "change_summary": change,
                "memories_distilled": len(mems), "narrative_chars": len(narrative)}

    def _gen_narrative(self, profile: dict) -> str:
        """v0.10 L3 叙事档案：从 9 维档案 + 场景导航生成 ≤2000 字符叙事体。"""
        try:
            from . import scenes
            nav = scenes.navigation()
        except Exception:
            nav = ""
        old = storage.latest_narrative()
        payload = {"profile": profile, "scene_navigation": nav, "old_narrative": old}
        try:
            text = self.llm.chat(SYSTEM_NARRATIVE, json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            print(f"[distill] narrative gen failed: {e}")
            return ""
        text = (text or "").strip()
        # LLM 可能回吐 JSON 包裹——只取字符串内容
        if text.startswith("{") or text.startswith("["):
            try:
                v = json.loads(text)
                text = v.get("narrative", text) if isinstance(v, dict) else text
            except Exception:
                pass
        return text[:2000]


def run() -> int:
    """模块级便捷入口，供 api.py /distill 调用。返回新增/更新的版本号，0 表示跳过。"""
    r = DistillationEngine().run()
    return r.get("version", 0) if not r.get("skipped") else 0


def load_persona() -> dict | None:
    """api.py /profile 用别名。返回 latest persona 或 None。"""
    from . import storage
    p, _sum, _v = storage.latest_persona()
    return p


def current_version() -> int:
    """api.py /status 用别名。"""
    _p, _s, v = storage.latest_persona()
    return v or 0
