"""recommend.py — 推荐引擎：联网动态搜索真实结果 → LLM 从中挑适合用户的。

反幻觉：item 必须来自真实搜索结果（token 落地），based_on 必须引 persona 非空维度或 result:<idx>；
不写死任何推荐内容，不编造用户偏好。
"""
from __future__ import annotations
import json
import re

from . import distill, memory, storage
from .llm import get_llm
from .web import get_searcher

SYSTEM_RECOMMEND = """[TASK:RECOMMEND]
你是用户的个人助手。基于对其人格档案的理解，从【提供的真实联网搜索结果】中挑 3-5 条适合他的内容。
每条字段：item(来自搜索结果的真实标题,原样或精简)、reason(为什么适合,结合 persona 具体特质)、based_on(依据:persona 维度名之一且该维度有内容,或 result:<0-based 索引> 之一)。
只能从提供的搜索结果里选，不得编造结果外的 item；不得编造用户没有的偏好。返回 JSON 数组。"""


def recommend(kind: str = "book", query: str = "", llm=None, n: int = 5) -> list[dict]:
    """联网搜真实结果 → LLM 挑 → 反幻觉过滤。kind∈{book,movie,action}。"""
    llm = llm or get_llm()
    profile = distill.current_profile()
    q = query or _first_nonempty(profile) or "个人成长"
    results = get_searcher().search(f"{kind} 推荐 {q}", n=10)
    if not results:
        print("[recommend] 无联网搜索结果（离线/受限）→ 不返回，不写死")
        return []
    mems = memory.search(q, k=5) if q else []
    mem_json = [{"id": h["memory"].get("id"), "kind": h["memory"].get("kind"),
                 "content": h["memory"].get("content")} for h in mems]
    user = (f"Persona (JSON):\n{json.dumps(profile, ensure_ascii=False)}\n"
            f"Relevant memories (JSON):\n{json.dumps(mem_json, ensure_ascii=False)}\n"
            f"Web search results (real, JSON):\n{json.dumps(results, ensure_ascii=False)}\n"
            f"Pick 3-5 {kind} FROM THE REAL RESULTS that fit the persona.")
    out = llm.chat_json(SYSTEM_RECOMMEND, user)
    if not isinstance(out, list):
        return []
    recs = [r for r in out if isinstance(r, dict) and r.get("item")]
    kept = grounded(recs, results)
    if len(kept) < len(recs):
        print(f"[recommend] 反幻觉过滤: {len(recs)}→{len(kept)} (item 不落地搜索结果 或 based_on 不落地)")
    return kept[:n]


def _first_nonempty(profile: dict) -> str:
    for d in ("preferences", "personality", "goals", "habits"):
        v = profile.get(d)
        if v:
            return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return ""


def _norm(s: str) -> str:
    return re.sub(r"[，。！？!?,\s、:：（）()\"'`《》「」]", "", s or "")


def grounded(recs: list[dict], results: list[dict] | None = None) -> list[dict]:
    """item 须 token 落地真实搜索结果；based_on 须引 persona 非空维度 或 result:<idx>。"""
    from .distill import DIMENSIONS
    profile = distill.current_profile()
    res_titles = [_norm(r.get("title", "")) for r in (results or [])]
    kept = []
    for r in recs:
        bo = (r.get("based_on") or "").strip()
        item = _norm(r.get("item", ""))
        # based_on 落地
        bo_ok = (bo in DIMENSIONS and profile.get(bo)) or \
                (bo.startswith("result:") and bo[7:].isdigit() and results and int(bo[7:]) < len(results))
        # item 须来自搜索结果（token 落地，容忍精简/微改）
        item_ok = (not res_titles) or any(
            item and (item in t or t in item or _share_token(item, t)) for t in res_titles)
        if bo_ok and item_ok:
            kept.append(r)
    return kept


def _share_token(a: str, b: str) -> bool:
    """至少一个 ≥3 字符子串共享（容忍 LLM 精简标题）。"""
    for i in range(len(a) - 2):
        if a[i:i + 3] in b:
            return True
    return False


def assert_grounded(recs: list[dict], results: list[dict] | None = None) -> None:
    """断言所有推荐落地。供测试/CLI。"""
    kept = grounded(recs, results)
    assert len(kept) == len(recs), f"{len(recs) - len(kept)} 条推荐不落地(幻觉)"
