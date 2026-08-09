"""recall.py — v0.10 混合召回（对齐 TencentDB Memory recall）。

策略：BM25(FTS5, 中文 bigram) + 向量余弦 → RRF(k=60) 融合 → 阈值过滤 → 预算截断。
分层注入由 chat.py 负责：L1 结果进 user 前缀，L3 narrative+场景导航进 system。
预算：max_results / score_threshold / timeout_ms / max_total_chars（config memory.recall.*）。
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field, asdict

from . import config, storage
from .llm import get_embedder

RRF_K = 60  # 对齐 MemoryCore search-utils.ts RRF_K

DEFAULT_BUDGET = {
    "strategy": "hybrid",       # hybrid | keyword | embedding
    "max_results": 5,
    "score_threshold": 0.008,   # RRF 域阈值（双榜命中基准 ≈ 2/(60+1)≈0.033）
    "timeout_ms": 5000,
    "max_chars_per_memory": 0,  # 0=不限
    "max_total_chars": 2000,    # 0=不限
}


@dataclass
class RecallResult:
    items: list = field(default_factory=list)   # [{memory, score, sources}]
    truncated: bool = False
    elapsed_ms: float = 0.0
    strategy: str = "hybrid"

    def to_dict(self) -> dict:
        return asdict(self)


def _budget(budget: dict | None) -> dict:
    b = dict(DEFAULT_BUDGET)
    try:
        b.update(config.get("memory.recall", {}) or {})
    except Exception:
        pass
    if budget:
        b.update(budget)
    return b


def bm25_search(query: str, k: int = 15) -> list[dict]:
    """FTS5 BM25 召回，返回 [{memory, rank}]（bm25 越小越相关）。"""
    hits = storage.fts_search(query, k=k)
    out = []
    for h in hits:
        mem = storage.memory_get(h["mem_id"])
        if mem:
            out.append({"memory": mem, "bm25_score": h["bm25_score"]})
    return out


def vector_search(query: str, k: int = 15, embedder=None) -> list[dict]:
    """向量余弦召回（复用 storage.search_memories）。"""
    embedder = embedder or get_embedder()
    try:
        vec = embedder.embed_one(query)
    except Exception:
        return []
    hits = storage.search_memories(vec, k=k)
    # 维度不匹配时 search_memories 可能抛错/空——由调用方回落
    return hits


def rrf_fuse(ranked_lists: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + rank + 1)，双榜命中分数相加。
    输入：多个按相关性降序的结果列表，元素含 memory。输出按融合分降序。"""
    scores: dict[str, float] = {}
    sources: dict[str, set] = {}
    mem_by_id: dict[str, dict] = {}
    for lst, src_name in zip(ranked_lists, ("bm25", "vector")):
        for rank, item in enumerate(lst):
            mid = item["memory"]["id"]
            scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)
            sources.setdefault(mid, set()).add(src_name)
            mem_by_id[mid] = item["memory"]
    out = [{"memory": mem_by_id[mid], "score": s, "sources": sorted(sources[mid])}
           for mid, s in scores.items()]
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def hybrid_recall(query: str, k: int | None = None, strategy: str | None = None,
                  embedder=None, budget: dict | None = None) -> RecallResult:
    """混合召回主入口。超时返回已得结果 + truncated=True，不抛异常。"""
    b = _budget(budget)
    k = k or b["max_results"]
    strategy = strategy or b["strategy"]
    t0 = time.monotonic()
    deadline = t0 + b["timeout_ms"] / 1000.0
    result = RecallResult(strategy=strategy)

    def _elapsed():
        return (time.monotonic() - t0) * 1000.0

    candidate_k = k * 3
    lists = []
    if strategy in ("hybrid", "keyword"):
        try:
            lists.append(bm25_search(query, k=candidate_k))
        except Exception:
            lists.append([])
    if strategy in ("hybrid", "embedding"):
        try:
            vec_hits = vector_search(query, k=candidate_k, embedder=embedder)
            # embedding 维度变更回落：向量结果与库存维度不一致时 search 已容错为空/报错
            lists.append(vec_hits)
        except Exception as e:
            print(f"[recall] vector search 回落（{e}），仅用 BM25")
            if not lists:  # embedding 单路模式且失败
                lists.append([])

    fused = rrf_fuse(lists) if len(lists) > 1 else [
        {"memory": it["memory"], "score": 1.0 / (RRF_K + r + 1),
         "sources": ["bm25" if strategy == "keyword" else "vector"]}
        for r, it in enumerate(lists[0])] if lists else []

    # 阈值过滤
    fused = [f for f in fused if f["score"] >= b["score_threshold"]]
    result.elapsed_ms = _elapsed()
    if time.monotonic() > deadline:
        result.truncated = True
        result.items = fused[:k]
        result.elapsed_ms = _elapsed()
        return result

    # 条数预算
    if len(fused) > k:
        fused = fused[:k]
        result.truncated = True

    # 字符预算
    max_total = b["max_total_chars"]
    max_per = b["max_chars_per_memory"]
    items = []
    total_chars = 0
    for f in fused:
        mem = dict(f["memory"])
        content = mem.get("content", "") or ""
        cut = False
        if max_per and len(content) > max_per:
            content = content[:max_per] + "…(已截断)"
            cut = True
        if max_total and total_chars + len(content) > max_total:
            remain = max_total - total_chars
            if remain >= 40:  # 最小保留 40 字符，否则停止
                content = content[:remain] + "…(已截断)"
                mem["content"] = content
                f = {**f, "memory": mem}
                items.append(f)
                total_chars += len(content)
            result.truncated = True
            break
        mem["content"] = content
        f = {**f, "memory": mem}
        items.append(f)
        total_chars += len(content)
        if cut:
            result.truncated = True

    result.items = items
    result.elapsed_ms = _elapsed()
    return result
