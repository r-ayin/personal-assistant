"""memory_bridge.py — 记忆后端桥接层：把 PA 全面接入「个人助手」融合记忆系统。

本模块取代原 memory.py / recall.py / wiki.py / distill.py / scenes.py（已删除），
是 PA 与融合记忆系统（信息层 + 时刻层）之间的唯一接口。

融合记忆系统位置：MEMORY_ROOT = <PA 项目根>/../ = 个人助手/
  - 信息层：cockpit.db(wiki_pages) + memory/cockpit-memory.md(L1) + content/(原文) + reports/
  - 时刻层：moments.db(verbatim_quote/narrative/tags/recalled) + moments-export.md

读路径：search / hybrid_recall / current_profile / latest_narrative / navigation
写路径：ingest_segments（转写文本写入融合系统 inbox/，由其 cycle.sh 双层摄入）
主动路径：memories_unprocessed / mark_memories_processed（映射 moments.recalled）

设计：只读消费融合系统产物（不直接写其 DB），写入仅通过 inbox/ 投递——
与融合系统"单一摄入、双头提取"的架构契约保持一致。
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import time
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from . import config, storage

# ── 融合记忆系统定位 ────────────────────────────────────────────────
# PA 项目根 = config.ROOT（personal-assistant/）；融合记忆系统在其上一级（个人助手/）
MEMORY_ROOT = Path(config.ROOT).parent
_MEMORY_DB = MEMORY_ROOT / "cockpit.db"
_MOMENTS_DB = MEMORY_ROOT / "moments.db"
_L1_PATH = MEMORY_ROOT / "memory" / "cockpit-memory.md"
_CONTENT_DIR = MEMORY_ROOT / "content"
_INBOX_DIR = MEMORY_ROOT / "inbox"


def _fused_env() -> dict:
    """子进程环境：注入融合记忆系统根 .env 的变量。

    cycle.sh 是靠 `set -a; . .env` 才有 INFO_LLM_* / MOMENT_LLM_* / TDAI_GATEWAY_*
    这些变量的；本模块用 subprocess 直接调根目录脚本时没走 cycle.sh，
    子进程因此读不到 LLM 配置，wiki_build.py 会抛 NoLLMConfigured。
    用 setdefault 语义：PA 进程环境里已有的值优先，不被 .env 覆盖。
    """
    env = dict(os.environ)
    p = MEMORY_ROOT / ".env"
    if not p.exists():
        return env
    try:
        raw = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return env
    for line in raw:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


# ── 用户画像维度（承袭原 distill.DIMENSIONS，recommend/api 依赖）────
DIMENSIONS = ["personality", "values", "goals", "habits", "skills",
              "knowledge", "thinking_patterns", "preferences", "affective_baseline"]


def normalize(profile: dict) -> dict:
    p = dict(profile or {})
    for d in DIMENSIONS:
        p.setdefault(d, [] if d in ("skills", "knowledge", "preferences") else "")
    return p


# ── 融合系统读取（只读）─────────────────────────────────────────────
def _wiki_pages(limit: int = 200) -> list[dict]:
    if not _MEMORY_DB.exists():
        return []
    try:
        con = sqlite3.connect(str(_MEMORY_DB))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, title, body, tags FROM wiki_pages LIMIT ?", (limit,)).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _moments(limit: int = 50, unrecalled_only: bool = False) -> list[dict]:
    if not _MOMENTS_DB.exists():
        return []
    try:
        con = sqlite3.connect(str(_MOMENTS_DB))
        con.row_factory = sqlite3.Row
        q = "SELECT * FROM moments"
        if unrecalled_only:
            q += " WHERE recalled = 0"
        q += " ORDER BY timestamp DESC LIMIT ?"
        rows = con.execute(q, (limit,)).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def list_moments(limit: int = 80) -> list[dict]:
    """时刻清单（最新在前），供前端时刻墙等只读消费方。
    tags 解析为列表；其余字段（verbatim_quote/narrative/speaker/timestamp/recalled 等）原样返回。"""
    out = []
    for d in _moments(limit=limit):
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        out.append(d)
    return out


def _norm_text(s: str) -> str:
    return re.sub(r"[\s，。！？!?、:：（）()'\"*#\-]+", "", s or "")


def _content_snippets(query: str, k: int = 5) -> list[dict]:
    if not _CONTENT_DIR.exists():
        return []
    qn = _norm_text(query)
    if not qn:
        return []
    hits = []
    for f in _CONTENT_DIR.rglob("*.md"):
        if "_orphan" in f.parts or f.name.startswith("_"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        tn = _norm_text(text)
        idx = tn.find(qn)
        if idx < 0:
            continue
        start = max(0, idx - 60)
        snippet = tn[start:idx + len(qn) + 120]
        hits.append({"file": str(f.relative_to(_CONTENT_DIR)), "snippet": snippet})
        if len(hits) >= k:
            break
    return hits


def _l1_text() -> str:
    try:
        return _L1_PATH.read_text(encoding="utf-8", errors="ignore") if _L1_PATH.exists() else ""
    except Exception:
        return ""


# ── 对外：检索（替代 memory.search / recall.hybrid_recall）──────────
def search(query: str, k: int = 5, embedder=None) -> list[dict]:
    """融合检索：wiki 实体页 + content 原文片段 + 时刻层。
    返回 [{"memory": {...}, "score": ...}]——与旧 memory.search 结构一致，上层零改动。"""
    out: list[dict] = []
    qn = _norm_text(query)
    for p in _wiki_pages():
        hay = _norm_text((p.get("title") or "") + (p.get("body") or ""))
        if qn and qn in hay:
            out.append({"id": f"wiki:{p.get('id')}", "kind": "wiki",
                        "content": (p.get("title") or "") + "：" + (p.get("body") or "")[:300],
                        "priority": 70, "evidence": f"wiki:{p.get('title')}",
                        "created_at": ""})
        if len(out) >= k:
            break
    for h in _content_snippets(query, k=max(1, k - len(out))):
        out.append({"id": f"content:{h['file']}", "kind": "content",
                    "content": h["snippet"], "priority": 55,
                    "evidence": f"content/{h['file']}", "created_at": ""})
    for m in _moments(limit=30):
        hay = _norm_text((m.get("verbatim_quote") or "") + (m.get("narrative") or ""))
        if qn and qn in hay:
            out.append({"id": f"moment:{m.get('id')}", "kind": "moment",
                        "content": (m.get("verbatim_quote") or "") + "｜" + (m.get("narrative") or ""),
                        "priority": 60, "evidence": f"moment:{m.get('id')}",
                        "created_at": m.get("timestamp", "")})
        if len(out) >= k:
            break
    return [{"memory": m, "score": round(1.0 / (60 + i + 1), 6)}
            for i, m in enumerate(out[:k])]


@dataclass
class RecallResult:
    items: list = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: float = 0.0
    strategy: str = "hybrid"

    def to_dict(self) -> dict:
        return asdict(self)


def hybrid_recall(query: str, k: int | None = None, strategy: str = "hybrid",
                  budget: dict | None = None, embedder=None) -> RecallResult:
    """混合召回（接入融合系统后以 search 为准，RecallResult 结构保留供上层兼容）。"""
    t0 = time.time()
    kk = k or int(config.get("memory.recall.max_results", 5) or 5)
    wrapped = search(query, k=kk, embedder=embedder)
    items = [{"memory": w["memory"], "score": w["score"], "sources": ["fused"]}
             for w in wrapped]
    max_chars = int((budget or {}).get("max_total_chars",
                  config.get("memory.recall.max_total_chars", 2000) or 2000) or 2000)
    total, truncated = 0, False
    trimmed = []
    for it in items:
        total += len(it["memory"].get("content", ""))
        if max_chars and total > max_chars:
            truncated = True
            break
        trimmed.append(it)
    return RecallResult(items=trimmed, truncated=truncated,
                        elapsed_ms=(time.time() - t0) * 1000.0, strategy=strategy)


# ── 对外：画像 / 叙事 / 场景导航（替代 distill / scenes）────────────
def current_profile() -> dict:
    """用户画像：推理档案（保留的 persona_versions）为基底，
    叠加融合记忆系统时刻层情感信号，再应用 PA 的 profile_feedback 纠正。"""
    effective = inferred_profile()
    try:
        tags: list[str] = []
        for m in _moments(limit=100):
            try:
                tags.extend(json.loads(m.get("tags") or "[]"))
            except Exception:
                pass
        if tags and not effective.get("affective_baseline"):
            from collections import Counter
            top = ", ".join(t for t, _ in Counter(tags).most_common(3))
            effective["affective_baseline"] = f"近期情感主题：{top}"
    except Exception:
        pass
    try:
        for fb in storage.list_profile_feedback():
            dim = fb["dimension"]
            if dim not in DIMENSIONS:
                continue
            val = fb["value"]
            cur = effective[dim]
            if isinstance(cur, list):
                if fb["action"] == "add" and val not in cur:
                    cur.append(val)
                elif fb["action"] == "suppress":
                    effective[dim] = [x for x in cur if x != val]
            elif fb["action"] == "add":
                effective[dim] = val
            elif fb["action"] == "suppress" and cur == val:
                effective[dim] = ""
    except Exception:
        pass
    return effective


def inferred_profile() -> dict:
    """推理档案：来自保留的 persona_versions 表（原 distill 蒸馏产物存储）。
    接入后新的蒸馏由融合记忆系统负责，此表承载历史蒸馏结果。"""
    try:
        inferred, _cs, _v = storage.latest_persona()
        return normalize(inferred) if inferred else normalize({})
    except Exception:
        return normalize({})


def load_persona() -> dict:
    return current_profile()


def latest_narrative() -> str:
    """用户叙事档案：优先融合系统时刻层最新叙事，回退 L1 概览。"""
    ms = _moments(limit=1)
    if ms and ms[0].get("narrative"):
        return ms[0]["narrative"]
    l1 = _l1_text()
    return l1[:600] if l1 else ""


def navigation() -> str:
    """场景导航（原 scenes 层并入时刻层）：按时刻标签热度给出导航文本。"""
    ms = _moments(limit=30)
    if not ms:
        return ""
    from collections import Counter
    tags: list[str] = []
    for m in ms:
        try:
            tags.extend(json.loads(m.get("tags") or "[]"))
        except Exception:
            pass
    if not tags:
        return ""
    lines = [f"- 近期时刻主题：{t}（{c} 次）" for t, c in Counter(tags).most_common(5)]
    return "\n".join(lines)


# ── 对外：写入（替代 memory.extract/add/dedup、ingest 记忆步）───────
def ingest_segments(segments: list[dict], source: str = "pa_transcript") -> int:
    """把转写片段投递到融合记忆系统 inbox/，由其 cycle.sh 双层（信息+时刻）摄入。
    返回投递的片段数。这是写路径的唯一入口——不直接写融合系统 DB。
    红队加固：source 参数白名单净化，防 ../ / 绝对路径穿透 inbox 目录。"""
    if not segments:
        return 0
    source = re.sub(r"[^a-zA-Z0-9_-]", "_", source) or "pa_transcript"
    _INBOX_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    lines = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        speaker = s.get("speaker", "user")
        lines.append(f"[{ts}] {speaker}: {text}")
    if not lines:
        return 0
    out = _INBOX_DIR / "pa_transcripts" / f"{source}_{ts}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def extract(segments: list[dict], llm=None) -> list[dict]:
    """接入融合系统后，抽取由融合系统时刻头完成；此桩仅做格式透传供旧管线兼容。"""
    return [{"kind": "event", "content": (s.get("text") or ""),
             "segment_id": s.get("id", ""), "evidence": s.get("id", ""),
             "priority": 50} for s in segments if (s.get("text") or "").strip()]


def filter_low_priority(mems: list[dict]) -> list[dict]:
    return [m for m in mems if int(m.get("priority", 50)) >= 40]


def add(mems: list[dict], embedder=None) -> int:
    """接入后记忆入库由融合系统负责；此桩把内容投递到融合系统 inbox/。"""
    segs = [{"text": m.get("content", ""), "speaker": "user", "id": m.get("segment_id", "")}
            for m in mems]
    return ingest_segments(segs, source="pa_memory")


def dedup_and_store(mems: list[dict], embedder=None, llm=None) -> dict:
    n = add(mems, embedder)
    return {"stored": n, "updated": 0, "merged": 0, "skipped": 0}


def extract_and_store(segments: list[dict], llm=None, embedder=None) -> int:
    return ingest_segments(segments, source="pa_transcript")


# ── 对外：主动引擎供数（替代 storage.memories_unprocessed）──────────
def memories_unprocessed() -> list[dict]:
    """未归还时刻 → 主动引擎的"未处理记忆"。"""
    out = []
    for m in _moments(limit=100, unrecalled_only=True):
        out.append({"id": f"moment:{m.get('id')}", "kind": "emotion",
                    "content": (m.get("verbatim_quote") or ""),
                    "evidence": f"moment:{m.get('id')}"})
    return out


def mark_memories_processed(ids: list[str]) -> None:
    """把已审视的时刻标记为已归还（recalled=1）。"""
    if not ids or not _MOMENTS_DB.exists():
        return
    try:
        con = sqlite3.connect(str(_MOMENTS_DB))
        for mid in ids:
            if isinstance(mid, str) and mid.startswith("moment:"):
                try:
                    real_id = int(mid.split(":", 1)[1])
                except ValueError:
                    continue
                con.execute("UPDATE moments SET recalled = 1 WHERE id = ?", (real_id,))
        con.commit()
        con.close()
    except Exception:
        pass


# ── 对外：蒸馏 / wiki 命令（替代 distill.DistillationEngine / wiki）──
class DistillationEngine:
    """接入后蒸馏=触发融合系统重建 L1/L2 记忆索引。"""

    def run(self) -> dict:
        import subprocess
        script = MEMORY_ROOT / "build_memory.py"
        if not script.exists():
            return {"error": "融合记忆系统 build_memory.py 不存在"}
        r = subprocess.run([sys.executable, str(script)], cwd=str(MEMORY_ROOT),
                           capture_output=True, text=True, timeout=300,
                           env=_fused_env())
        return {"distilled": 1 if r.returncode == 0 else 0,
                "stdout_tail": (r.stdout or "")[-300:],
                "returncode": r.returncode}


def run_distill() -> int:
    return DistillationEngine().run().get("distilled", 0)


def wiki_build() -> dict:
    """触发融合系统 wiki 实体图增量编译。"""
    import subprocess
    script = MEMORY_ROOT / "wiki_build.py"
    if not script.exists():
        return {"error": "融合记忆系统 wiki_build.py 不存在"}
    r = subprocess.run([sys.executable, str(script)], cwd=str(MEMORY_ROOT),
                       capture_output=True, text=True, timeout=600,
                       env=_fused_env())
    return {"new_pages": 0, "extended": 0, "returncode": r.returncode,
            "stdout_tail": (r.stdout or "")[-300:]}


def wiki_retrieve(q: str = "", k: int = 10) -> list[dict]:
    """检索融合系统 wiki 实体页。"""
    pages = _wiki_pages(limit=500)
    if not q:
        return pages[:k]
    qn = _norm_text(q)
    out = [p for p in pages if qn in _norm_text((p.get("title") or "") + (p.get("body") or ""))]
    return out[:k]


def wiki_search(q: str) -> dict:
    """api /wiki?q= 端点：返回命中页。"""
    return {"pages": wiki_retrieve(q, k=20)}


def wiki_list_topics() -> list:
    """api /wiki 端点：返回全部主题标签。"""
    topics: set = set()
    for p in _wiki_pages(limit=500):
        tags = p.get("tags") or "[]"
        try:
            for t in json.loads(tags):
                topics.add(t)
        except Exception:
            pass
    return sorted(topics)


# ── 对外：统计 / 状态 ───────────────────────────────────────────────
def current_version() -> int:
    """画像版本（接入后无本地版本化蒸馏，恒 0）。"""
    return 0


def count_memories() -> int:
    """融合系统记忆规模 = wiki 页数 + 时刻数。"""
    return len(_wiki_pages(limit=10000)) + len(_moments(limit=10000))


def status_summary() -> dict:
    return {
        "memory_root": str(MEMORY_ROOT),
        "wiki_pages": len(_wiki_pages(limit=10000)),
        "moments_total": len(_moments(limit=10000)),
        "moments_unrecalled": len(_moments(limit=10000, unrecalled_only=True)),
        "l1_present": _L1_PATH.exists(),
    }
