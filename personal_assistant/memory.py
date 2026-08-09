"""memory.py — 记忆抽取(LLM) + 入库(embedding) + 检索 + 两阶段去重(v0.10)。

extract: 给 LLM [TASK:EXTRACT_MEMORIES] + 片段 JSON，产出 {kind,content,evidence,priority} 列表。
add: embed content → storage.add_memory。
search: embed query → storage.search_memories 余弦 top-k。
dedup_and_store: v0.10 两阶段去重 — 向量候选召回 → LLM 判决 store/update/merge/skip。
"""
from __future__ import annotations
import json

from . import config, storage
from .llm import get_llm, get_embedder

SYSTEM_EXTRACT = """[TASK:EXTRACT_MEMORIES]
你是记忆抽取器。从用户语音转写片段中抽取结构化记忆。
每条记忆字段：kind(必为 fact|event|preference|intention|emotion|skill 之一)、content(简述)、segment_id(源片段id,必须等于输入的某条 id)、evidence(同 segment_id)、priority(0-100 整数)。
priority 分档：fact/preference 50-100（核心事实/长期偏好≥80）；event 60-100（重要事件≥80）；intention/skill 50-100；emotion 40-100。琐碎信息给低分。
只抽取片段中确实出现的信息，不得编造。返回 JSON 数组。"""

SYSTEM_DEDUP = """[TASK:DEDUP_MEMORIES]
你是记忆去重判决器。对每条新记忆(new)，对照候选已有记忆(candidates)给出判决。
action 取值：
- store：与候选无语义重叠，直接新增
- update：新记忆是候选的更新/修正，覆盖候选 content（target_id=该候选 id，merged_content=更新后内容）
- merge：新记忆与候选可合并为一条更完整记忆（target_id=该候选 id，merged_content=合并后内容，merged_priority=合并后重要度）
- skip：新记忆与候选完全重复，丢弃
每条新记忆必须输出：{new_id, action, target_id(可空), merged_content(action 为 update/merge 时必填), merged_priority(update/merge 时给 0-100 整数)}。
返回 JSON 数组，只输出 JSON。"""

# 低 priority 丢弃阈值（按 kind）；config memory.priority_drop_thresholds 可覆盖
DEFAULT_DROP_THRESHOLDS = {"fact": 50, "event": 60, "emotion": 40,
                           "preference": 50, "intention": 50, "skill": 50}


def _segments_to_extract(segments: list[dict]) -> list[dict]:
    return [{"id": s["id"], "text": s["text"],
             "start": s.get("start_sec"), "end": s.get("end_sec")} for s in segments]


def extract(segments: list[dict], llm=None) -> list[dict]:
    llm = llm or get_llm()
    if not segments:
        return []
    user = "Segments (JSON):\n" + json.dumps(_segments_to_extract(segments), ensure_ascii=False)
    out = llm.chat_json(SYSTEM_EXTRACT, user)
    if not isinstance(out, list):
        return []
    # 补 segment_id 关联 + 校验 kind + priority 容错（缺失/非法修复为 50）
    valid = {"fact", "event", "preference", "intention", "emotion", "skill"}
    for m in out:
        if not isinstance(m, dict):
            continue
        m.setdefault("segment_id", "")
        if m.get("kind") not in valid:
            m["kind"] = "event"
        try:
            p = int(m.get("priority", 50))
            m["priority"] = max(0, min(100, p))
        except (TypeError, ValueError):
            m["priority"] = 50
    return [m for m in out if isinstance(m, dict) and m.get("content")]


def _drop_thresholds() -> dict:
    th = dict(DEFAULT_DROP_THRESHOLDS)
    try:
        th.update(config.get("memory.priority_drop_thresholds", {}) or {})
    except Exception:
        pass
    return th


def filter_low_priority(mems: list[dict]) -> list[dict]:
    """v0.10：按 kind 阈值过滤低 priority 记忆（宁缺毋滥）。"""
    th = _drop_thresholds()
    return [m for m in mems if int(m.get("priority", 50)) >= th.get(m.get("kind", "event"), 50)]


def add(memories: list[dict], embedder=None) -> int:
    embedder = embedder or get_embedder()
    n = 0
    for m in memories:
        try:
            vec = embedder.embed_one(m.get("content", ""))
        except Exception:
            vec = None
        m.setdefault("segment_id", m.get("evidence", "").replace("segment:", "").split()[0] if m.get("evidence") else "")
        storage.add_memory(m, vec)
        n += 1
    return n


def search(query: str, k: int = 5, embedder=None):
    embedder = embedder or get_embedder()
    vec = embedder.embed_one(query)
    return storage.search_memories(vec, k)


def extract_and_store(segments: list[dict], llm=None, embedder=None) -> int:
    mems = extract(segments, llm)
    mems = filter_low_priority(mems)
    return add(mems, embedder)


# ── v0.10 两阶段去重（对齐 TencentDB Memory L1 dedup）────────────
def _bigram_overlap(a: str, b: str) -> float:
    """字符 bigram Jaccard 重叠度（0-1），供 stub 判决与测试。"""
    def grams(s):
        s = "".join(s.split())
        return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _merge_evidence(old: str, new: str) -> str:
    parts = [p.strip() for p in [old, new] if p and p.strip()]
    seen, out = set(), []
    for p in parts:
        for piece in p.split(";"):
            piece = piece.strip()
            if piece and piece not in seen:
                seen.add(piece)
                out.append(piece)
    return "; ".join(out)


def dedup_and_store(new_mems: list[dict], embedder=None, llm=None) -> dict:
    """两阶段去重入库：
    阶段1 每条新记忆向量召回 top-5 候选；
    阶段2 LLM 批量判决 store/update/merge/skip；候选为空则跳过判决全部 store。
    非法 action 降级 store（宁可重复不漏存）。
    返回 {"stored","updated","merged","skipped","total"}。
    """
    embedder = embedder or get_embedder()
    llm = llm or get_llm()
    counts = {"stored": 0, "updated": 0, "merged": 0, "skipped": 0, "total": len(new_mems)}
    if not new_mems:
        return counts

    # 阶段1：候选召回（向量 top-5）
    payload = []
    has_candidates = False
    for m in new_mems:
        try:
            vec = embedder.embed_one(m.get("content", ""))
        except Exception:
            vec = None
        cands = storage.search_memories(vec, k=5) if vec is not None else []
        # 排除空内容候选
        cands = [c for c in cands if c.get("memory", {}).get("content")]
        if cands:
            has_candidates = True
        payload.append({"mem": m, "vec": vec, "candidates": cands})

    # 阶段2：LLM 批量判决（无候选时全部 store，对齐 MemoryCore Tier 3）
    decisions: dict[int, dict] = {}
    if has_candidates:
        llm_input = {
            "new_memories": [
                {"new_id": i, "kind": p["mem"].get("kind", "event"),
                 "content": p["mem"].get("content", "")}
                for i, p in enumerate(payload)],
            "candidates": {
                str(i): [{"id": c["memory"]["id"], "kind": c["memory"].get("kind", ""),
                          "content": c["memory"].get("content", "")} for c in p["candidates"]]
                for i, p in enumerate(payload) if p["candidates"]},
        }
        try:
            out = llm.chat_json(SYSTEM_DEDUP, json.dumps(llm_input, ensure_ascii=False))
        except Exception:
            out = []
        if isinstance(out, list):
            for d in out:
                if isinstance(d, dict) and isinstance(d.get("new_id"), int):
                    decisions[d["new_id"]] = d

    # 执行判决
    for i, p in enumerate(payload):
        m, vec = p["mem"], p["vec"]
        d = decisions.get(i, {})
        action = d.get("action", "store")
        target_id = d.get("target_id") or ""
        target = storage.memory_get(target_id) if target_id else None
        if action not in ("store", "update", "merge", "skip") or \
                (action in ("update", "merge") and not target):
            action = "store"  # 非法/目标缺失降级 store

        if action == "skip":
            counts["skipped"] += 1
            continue
        if action == "update":
            storage.update_memory(
                target_id,
                content=d.get("merged_content") or m.get("content", ""),
                priority=_merged_priority(int(target.get("priority") or 50),
                                          int(m.get("priority", 50)), action, d),
                evidence=_merge_evidence(target.get("evidence", ""), m.get("evidence", "")),
                scene_name=target.get("scene_name") or m.get("scene_name", ""))
            counts["updated"] += 1
            continue
        if action == "merge":
            storage.update_memory(
                target_id,
                content=d.get("merged_content") or
                        f'{target.get("content", "")}；{m.get("content", "")}',
                priority=_merged_priority(int(target.get("priority") or 50),
                                          int(m.get("priority", 50)), action, d),
                evidence=_merge_evidence(target.get("evidence", ""), m.get("evidence", "")),
                scene_name=target.get("scene_name") or m.get("scene_name", ""))
            counts["merged"] += 1
            continue
        # store
        m.setdefault("segment_id",
                     m.get("evidence", "").replace("segment:", "").split()[0] if m.get("evidence") else "")
        storage.add_memory(m, vec)
        counts["stored"] += 1
    return counts


def _merged_priority(old_p: int, new_p: int, action: str, decision: dict) -> int:
    """merge/update 后 priority：LLM 给定优先；否则取高者，merge 再 +10（≤100）。"""
    try:
        p = decision.get("merged_priority")
        if p is not None:
            return max(0, min(100, int(p)))
    except (TypeError, ValueError):
        pass
    p = max(old_p, new_p)
    if action == "merge":
        p = min(100, p + 10)
    return p
