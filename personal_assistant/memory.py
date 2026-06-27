"""memory.py — 记忆抽取(LLM) + 入库(embedding) + 检索。

extract: 给 LLM [TASK:EXTRACT_MEMORIES] + 片段 JSON，产出 {kind,content,evidence} 列表。
add: embed content → storage.add_memory。
search: embed query → storage.search_memories 余弦 top-k。
"""
from __future__ import annotations
import json

from . import config, storage
from .llm import get_llm, get_embedder

SYSTEM_EXTRACT = """[TASK:EXTRACT_MEMORIES]
你是记忆抽取器。从用户语音转写片段中抽取结构化记忆。
每条记忆字段：kind(必为 fact|event|preference|intention|emotion|skill 之一)、content(简述)、evidence(引用片段 id,如 segment:s1)。
只抽取片段中确实出现的信息，不得编造。返回 JSON 数组。"""


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
    # 补 segment_id 关联 + 校验 kind
    valid = {"fact", "event", "preference", "intention", "emotion", "skill"}
    for m in out:
        if not isinstance(m, dict):
            continue
        m.setdefault("segment_id", "")
        if m.get("kind") not in valid:
            m["kind"] = "event"
    return [m for m in out if isinstance(m, dict) and m.get("content")]


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
    return add(mems, embedder)
