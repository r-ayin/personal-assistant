"""scenes.py — v0.10 L2 场景层（对齐 TencentDB Memory Scenario）。

场景 = 围绕情境组织的知识块（name/summary/body/heat），存 SQLite scenes 表。
整合策略：UPDATE(默认) > MERGE > CREATE；容量 scene_max(15) 上限强制 MERGE；
heat：新建=1 / 更新+1 / 合并=sum+1；body ≤1500 字符；
溯源：source_mem_ids 必须全部存在 memories 表，否则丢弃该操作（反幻觉）。
"""
from __future__ import annotations
import json

from . import config, storage
from .llm import get_llm

MAX_BODY_CHARS = 1500
TRUNCATION_MARK = "…(已截断)"

SYSTEM_SCENE = """[TASK:SCENE_INTEGRATE]
你是场景整合器。输入：现有场景列表(scenes)与新增记忆(memories)。
对每批相关记忆输出操作列表，每个操作：
- action=UPDATE：记忆属于某现有场景 → {action, scene_id, name, summary, body, source_mem_ids}
- action=MERGE：两个以上场景高度重叠 → {action, scene_ids:[...], name, summary, body, source_mem_ids}（合并后的场景）
- action=CREATE：记忆构成全新情境且与现有场景都不重叠 → {action, name, summary, body, source_mem_ids}
规则：
1. 优先 UPDATE；容量接近上限时优先 MERGE；只有确实不重叠才 CREATE（一次最多新增 1 个）。
2. name 格式"我(AI)在和xxx做xxx"或简短情境名（≤20字）；summary 30-40 字摘要。
3. body 为 Markdown，章节：## 用户基础信息 ## 用户偏好 ## 核心叙事 ## 演变轨迹 ## 待确认点（缺内容可省略章节），总长 ≤1500 字符。
4. source_mem_ids 必须是输入 memories 中出现的 id，不得编造。
只输出 JSON 数组。"""


def pending_count() -> int:
    """未参与过场景整合的记忆数（kv 游标）。"""
    seen = _integrated_ids()
    total = storage.count_memories()
    return max(0, total - len(seen))


def _integrated_ids() -> set:
    raw = storage.kv_get("scene_integrated_mem_ids")
    try:
        return set(json.loads(raw)) if raw else set()
    except Exception:
        return set()


def _mark_integrated(ids) -> None:
    cur = _integrated_ids() | set(ids)
    storage.kv_set("scene_integrated_mem_ids", json.dumps(sorted(cur), ensure_ascii=False))


def _new_memories() -> list[dict]:
    seen = _integrated_ids()
    return [m for m in storage.memories_all() if m["id"] not in seen]


def integrate(new_mem_ids: list[str] | None = None, llm=None) -> dict:
    """场景整合主入口。返回 {created,updated,merged,scenes_total}。"""
    llm = llm or get_llm()
    scene_max = int(config.get("memory.scene_max", 15))
    mems = ([storage.memory_get(i) for i in new_mem_ids] if new_mem_ids else _new_memories())
    mems = [m for m in mems if m]
    result = {"created": 0, "updated": 0, "merged": 0, "scenes_total": len(storage.scenes_all())}
    if not mems:
        return result

    scenes = storage.scenes_all()
    llm_input = {
        "scenes": [{"id": s["id"], "name": s["name"], "summary": s["summary"],
                    "heat": s["heat"]} for s in scenes],
        "memories": [{"id": m["id"], "kind": m.get("kind", ""),
                      "content": m.get("content", ""),
                      "priority": m.get("priority", 50)} for m in mems],
        "scene_max": scene_max,
        "capacity_warning": ("MERGE 强制：场景已达上限" if len(scenes) >= scene_max else
                             "禁止 CREATE：已达上限-1" if len(scenes) >= scene_max - 1 else ""),
    }
    try:
        ops = llm.chat_json(SYSTEM_SCENE, json.dumps(llm_input, ensure_ascii=False))
    except Exception:
        ops = []
    if not isinstance(ops, list):
        ops = []

    mem_ids_valid = {m["id"] for m in mems}
    for op in ops:
        if not isinstance(op, dict):
            continue
        action = op.get("action")
        # 溯源校验：source_mem_ids 必须全部为本批真实记忆 id
        src = [i for i in (op.get("source_mem_ids") or []) if i in mem_ids_valid]
        if not src:
            continue  # 无有效溯源 → 丢弃操作（反幻觉）
        body = _truncate(str(op.get("body", "")))
        name = str(op.get("name", "")).strip()[:40]
        summary = str(op.get("summary", "")).strip()[:80]
        if not name:
            continue

        if action == "UPDATE" and op.get("scene_id"):
            s = storage.scene_get(op["scene_id"])
            if not s:
                continue
            merged_src = sorted(set(s["source_mem_ids"]) | set(src))
            storage.scene_upsert({
                "id": s["id"], "name": name or s["name"], "summary": summary or s["summary"],
                "body": body or s["body"], "heat": s["heat"] + 1, "source_mem_ids": merged_src})
            result["updated"] += 1
        elif action == "MERGE" and len(op.get("scene_ids") or []) >= 2:
            targets = [storage.scene_get(i) for i in op["scene_ids"]]
            targets = [t for t in targets if t]
            if len(targets) < 2:
                continue
            heat = sum(t["heat"] for t in targets) + 1
            merged_src = sorted(set(src) | {i for t in targets for i in t["source_mem_ids"]})
            new_id = storage.scene_upsert({
                "name": name, "summary": summary, "body": body,
                "heat": heat, "source_mem_ids": merged_src})
            for t in targets:
                storage.scene_delete(t["id"])
            result["merged"] += 1
        elif action == "CREATE" and len(storage.scenes_all()) < scene_max:
            storage.scene_upsert({
                "name": name, "summary": summary, "body": body,
                "heat": 1, "source_mem_ids": sorted(set(src))})
            result["created"] += 1
        # 其他（容量已满的 CREATE 等）静默丢弃

    _mark_integrated([m["id"] for m in mems])
    result["scenes_total"] = len(storage.scenes_all())
    return result


def _truncate(body: str) -> str:
    if len(body) <= MAX_BODY_CHARS:
        return body
    return body[:MAX_BODY_CHARS - len(TRUNCATION_MARK)] + TRUNCATION_MARK


def navigation() -> str:
    """场景导航文本（heat 降序，对齐 MemoryCore scene-navigation）。"""
    lines = []
    for s in storage.scenes_all():
        flames = ""
        h = s.get("heat", 1)
        for th, mark in ((1000, "🔥🔥🔥🔥🔥"), (500, "🔥🔥🔥🔥"), (200, "🔥🔥🔥"),
                         (100, "🔥🔥"), (50, "🔥")):
            if h >= th:
                flames = mark
                break
        lines.append(f"- {flames} {s['name']} — {s['summary']}".rstrip(" —"))
    return "\n".join(lines)
