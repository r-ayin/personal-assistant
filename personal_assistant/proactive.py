"""proactive.py — 主动触发引擎：扫未处理记忆的关键信息 → 生成干预 → 推送(CLI/日志)。

触发规则（MVP 3 类）：
- intention_reminder：意图 + 时间词（明天/下周/打算/准备/计划）
- emotional_support：情绪低落（累/焦虑/难过/烦/emo）或 emotion∈{sad,anxious,tired,annoyed}
- topic_pattern：同一内容前缀重复 ≥3 次
每批触发记忆 → LLM [TASK:INTERVENTION] 生成建议 → 入库 + 通知。
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

from . import config, storage
from .llm import get_llm

SYSTEM_INTERVENTION = """[TASK:INTERVENTION]
你是用户的个人助手，主动在关键时机给出干预。基于触发记忆，生成一条简短、有温度的建议/安抚/提醒。
要具体、可执行，引用触发依据。不要说教。返回纯文本（一条消息）。"""

EMO_WORDS = ["累", "焦虑", "难过", "烦", "emo", "崩溃", "压力大", "失眠"]
TIME_WORDS = ["明天", "下周", "今晚", "打算", "准备", "计划", "该去", "要交"]


def _classify(mem: dict) -> str | None:
    content = (mem.get("content") or "")
    kind = mem.get("kind", "")
    if kind == "intention" or any(w in content for w in TIME_WORDS):
        return "intention_reminder"
    if kind == "emotion" or any(w in content for w in EMO_WORDS):
        return "emotional_support"
    return None


def _topic_pattern(mems: list[dict]) -> dict[str, list[dict]]:
    """同内容前缀(前8字)重复≥3 → topic_pattern 触发。"""
    buckets: dict[str, list[dict]] = {}
    for m in mems:
        key = (m.get("content") or "")[:8]
        buckets.setdefault(key, []).append(m)
    return {k: v for k, v in buckets.items() if len(v) >= 3}


class CLINotifier:
    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path or (config.ROOT / "data" / "logs" / "interventions.log")

    def notify(self, message: str, evidence: str, trigger_kind: str):
        line = f"[{storage.now_iso()}] ({trigger_kind}) {message}  ← {evidence}"
        print(f"\n🔔 主动干预: {line}")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def check() -> list[dict]:
    """模块级快捷方式（供 api.py import）。"""
    return ProactiveEngine().check()


class ProactiveEngine:
    def __init__(self, llm=None, notifier=None):
        self.llm = llm or get_llm()
        self.notifier = notifier or CLINotifier()

    def check(self) -> list[dict]:
        unprocessed = storage.memories_unprocessed()
        if not unprocessed:
            return []
        triggers: list[dict] = []
        # 1. 按条分类
        for m in unprocessed:
            k = _classify(m)
            if k:
                triggers.append({"kind": k, "memories": [m]})
        # 2. 话题重复
        for _key, mems in _topic_pattern(unprocessed).items():
            triggers.append({"kind": "topic_pattern", "memories": mems})
        # 去重记忆 id
        seen, fired = set(), []
        for t in triggers:
            mems = [m for m in t["memories"] if m["id"] not in seen]
            if not mems:
                continue
            seen.update(m["id"] for m in mems)
            ev = "; ".join(m.get("evidence", m["id"]) for m in mems)
            user = "Triggering memories (JSON):\n" + json.dumps(
                [{"kind": m.get("kind"), "content": m.get("content")} for m in mems], ensure_ascii=False)
            msg = self.llm.chat(SYSTEM_INTERVENTION, user)
            iid = storage.add_intervention(t["kind"], ev, msg)
            self.notifier.notify(msg, ev, t["kind"])
            fired.append({"id": iid, "kind": t["kind"], "message": msg, "evidence": ev})
        # 标记已审视
        storage.mark_memories_processed([m["id"] for m in unprocessed])
        return fired
