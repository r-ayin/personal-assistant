"""wiki.py — 个人 wiki：增量编译，主题动态增长。

build(): 只处理新记忆(未 wikified)。能并入已有主题页→扩展(body 重生成覆盖 old+new,source_ids 取并);
新主题→建新页。记忆标记 wikified 不重处理。反幻觉:source_ids 真实+body bigram 落地"全部"source_ids 内容。
"""
from __future__ import annotations
import json
import re

from . import storage
from .llm import get_llm

SYSTEM_BUILD_WIKI = """[TASK:BUILD_WIKI]
你是个人 wiki 增量编译器。把【新记忆】并入已有 wiki 或建新页。
规则：
- 新记忆能归入已有主题→EXTEND：复用已有页的精确 title；body 重新综合该页全部源(旧+新)内容；source_ids 输出并集(旧+新)。
- 新主题(genuinely new)→CREATE 新页：title/body/tags/source_ids(新记忆 id)。
- 不得编造：source_ids 必须来自提供的记忆 id；body 只综合 source_ids 对应内容。
- 不要为已有主题建重复页。
返回 JSON 数组：[{title, body(markdown), tags[], source_ids[], links[]}]。"""


def _norm(s: str) -> str:
    return re.sub(r"[，。！？!?,\s、:：（）()\"'`#*\-\n\r\t]", "", s or "")


def _body_grounded(body: str, src_text: str) -> bool:
    b = _norm(body)
    s = _norm(src_text)
    if not b:
        return False
    for i in range(len(b) - 1):
        if b[i:i + 2] in s:
            return True
    return False


def _find_existing(title: str, existing: list[dict]) -> dict | None:
    t = _norm(title)
    if not t:
        return None
    for p in existing:
        et = _norm(p.get("title", ""))
        if t == et or t in et or et in t:
            return p
    return None


def build(llm=None) -> dict:
    """增量编译：新记忆 → 扩展已有页 / 建新页。返回 {new_pages, extended}。"""
    llm = llm or get_llm()
    all_mems = storage.memories_all()
    if not all_mems:
        return {"new_pages": 0, "extended": 0, "reason": "no memories"}
    wids = storage.wikified_ids()
    new_mems = [m for m in all_mems if m["id"] not in wids]
    if not new_mems:
        return {"new_pages": 0, "extended": 0, "reason": "no new memories (all wikified)"}
    new_ids = {m["id"] for m in new_mems}
    mem_by_id = {m["id"]: m for m in all_mems}
    existing = storage.all_wiki_pages()
    existing_ctx = [{"title": p["title"], "tags": p.get("tags", []),
                     "source_ids": p.get("source_ids", []),
                     "source_contents": [mem_by_id[s].get("content", "")
                                          for s in p.get("source_ids", []) if s in mem_by_id]}
                    for p in existing]
    body_new = [{"id": m["id"], "kind": m.get("kind"), "content": m.get("content")} for m in new_mems]
    user = ("New memories (JSON):\n" + json.dumps(body_new, ensure_ascii=False) +
            "\nExisting wiki pages (JSON):\n" + json.dumps(existing_ctx, ensure_ascii=False) +
            "\nIncremental compile: extend existing pages (reuse exact title, body covers old+new, "
            "source_ids = union) or create new pages for genuinely new topics. Don't duplicate topics.")
    out = llm.chat_json(SYSTEM_BUILD_WIKI, user)
    if not isinstance(out, list):
        return {"new_pages": 0, "extended": 0, "reason": "LLM 未返回数组"}
    new_pages = extended = 0
    used = set()
    for p in out:
        if not isinstance(p, dict) or not p.get("title"):
            continue
        src = [s for s in (p.get("source_ids") or []) if s in mem_by_id]
        if not src:
            continue
        ex = _find_existing(p["title"], existing)
        if ex:
            src = list(set(ex.get("source_ids", [])) | set(src))  # 并集
        # body 须落地"全部"最终 source_ids 内容
        src_text = " ".join(mem_by_id[s].get("content", "") for s in src if s in mem_by_id)
        if not _body_grounded(p.get("body", ""), src_text):
            continue
        p["source_ids"] = src
        p["tags"] = p.get("tags") if isinstance(p.get("tags"), list) else [str(p.get("tags", ""))]
        p["links"] = p.get("links") if isinstance(p.get("links"), list) else [str(p.get("links", ""))]
        if ex:
            storage.add_wiki_page({"id": ex["id"], **p})  # 同 id 更新=扩展
            extended += 1
        else:
            storage.add_wiki_page(p)
            new_pages += 1
        used.update(s for s in src if s in new_ids)
    storage.mark_wikified(used)
    return {"new_pages": new_pages, "extended": extended}


def retrieve(tag: str = "", query: str = "") -> list[dict]:
    return storage.wiki_search(tag=tag, query=query)


def assert_grounded() -> None:
    """断言：每个 wiki 页 source_ids 真实 + body 落地全部源。供测试/CLI。"""
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
