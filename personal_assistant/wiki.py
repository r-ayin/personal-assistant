"""wiki.py — 个人 wiki：记忆→自动切片(原子化)+LLM 分类打标+编译互链主题页+源引用。

build(): 取记忆 → LLM 按主题分组编译成 wiki 页(title/body/tags/source_ids/links)。
反幻觉：source_ids 必须真实存在；body 必须 bigram 落地 source 记忆内容；不落地即弃。
retrieve(): 按标签/关键词检索页。
"""
from __future__ import annotations
import json
import re

from . import storage
from .llm import get_llm

SYSTEM_BUILD_WIKI = """[TASK:BUILD_WIKI]
你是个人 wiki 编译器。把提供的记忆条目按主题分组编译成 wiki 页面。
每页字段：title(主题名)、body(markdown,综合该主题下记忆要点,可用要点列表)、tags(分类标签数组,如 工作/健康/社交/兴趣/情绪/日程)、source_ids(本页依据的记忆 id 数组,必须来自提供的记忆 id)、links(相关页 title 数组,供互链)。
规则：source_ids 必须真实存在；body 只综合 source_ids 对应记忆的内容,不得编造；按主题归并相近记忆。返回 JSON 数组(3-8 页)。"""


def _norm(s: str) -> str:
    return re.sub(r"[，。！？!?,\s、:：（）()\"'`#*\-\n\r\t]", "", s or "")


def _body_grounded(body: str, src_text: str) -> bool:
    """body 至少一个 bigram 落地源记忆内容（容忍综合改写,但禁止凭空）。"""
    b = _norm(body)
    s = _norm(src_text)
    if not b:
        return False
    for i in range(len(b) - 1):
        if b[i:i + 2] in s:
            return True
    return False


def _grounded_page(p: dict, mems: list[dict]) -> dict | None:
    mem_ids = {m["id"] for m in mems}
    mem_by_id = {m["id"]: m for m in mems}
    src = [s for s in (p.get("source_ids") or []) if s in mem_ids]
    if not src:
        return None
    p["source_ids"] = src
    src_text = " ".join(mem_by_id[s].get("content", "") for s in src)
    if not _body_grounded(p.get("body", ""), src_text):
        return None
    tags = p.get("tags", [])
    p["tags"] = tags if isinstance(tags, list) else [str(tags)]
    links = p.get("links", [])
    p["links"] = links if isinstance(links, list) else [str(links)]
    return p


def build(llm=None) -> int:
    """记忆 → LLM 编译主题 wiki 页 → 反幻觉过滤入库。返回入库页数。"""
    llm = llm or get_llm()
    mems = storage.memories_all()
    if not mems:
        return 0
    body_mem = [{"id": m["id"], "kind": m.get("kind"), "content": m.get("content")} for m in mems]
    user = "Memories (JSON):\n" + json.dumps(body_mem, ensure_ascii=False) + \
           "\nCompile into 3-8 topic wiki pages."
    out = llm.chat_json(SYSTEM_BUILD_WIKI, user)
    if not isinstance(out, list):
        return 0
    n = 0
    for p in out:
        if not isinstance(p, dict) or not p.get("title"):
            continue
        p = _grounded_page(p, mems)
        if p:
            storage.add_wiki_page(p)
            n += 1
    return n


def retrieve(tag: str = "", query: str = "") -> list[dict]:
    return storage.wiki_search(tag=tag, query=query)


def assert_grounded() -> None:
    """断言：每个 wiki 页 source_ids 真实 + body 落地源记忆。供测试/CLI。"""
    mems = storage.memories_all()
    mem_ids = {m["id"] for m in mems}
    mem_by_id = {m["id"]: m for m in mems}
    pages = storage.all_wiki_pages()
    assert pages, "wiki 为空(应已编译)"
    for p in pages:
        src = p.get("source_ids") or []
        assert src and all(s in mem_ids for s in src), f"wiki {p['id']} source_ids 不真实(幻觉)"
        src_text = " ".join(mem_by_id[s].get("content", "") for s in src)
        assert _body_grounded(p.get("body", ""), src_text), f"wiki {p['id']} body 不落地源(幻觉)"
