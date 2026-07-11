"""storage.py — SQLite(片段/记忆/人格版本/干预/kv) + numpy 余弦检索 + DuckDB 已在 asr。

embedding 以 BLOB 存 memories.embedding，检索时全量载入做余弦。MVP 规模足够。
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS segments(
  id TEXT PRIMARY KEY, source_file TEXT, start_sec REAL, end_sec REAL,
  text TEXT, speaker TEXT, language TEXT,
  created_at TEXT,  -- 记录时间(系统收文/ingest 时刻)，非真实发生时间(无设备时间戳则不可得)
  processed INT DEFAULT 0,
  time_kind TEXT DEFAULT 'received',
  agent_id TEXT DEFAULT '');  -- 来源 agent/设备 ID
CREATE TABLE IF NOT EXISTS ingested_files(
  source_file TEXT PRIMARY KEY, ingested_at TEXT, n_segments INT);
CREATE TABLE IF NOT EXISTS memories(
  id TEXT PRIMARY KEY, segment_id TEXT, kind TEXT, content TEXT, evidence TEXT,
  embedding BLOB, created_at TEXT, processed INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS persona_versions(
  version INTEGER PRIMARY KEY, created_at TEXT, profile_json TEXT, change_summary TEXT);
CREATE TABLE IF NOT EXISTS interventions(
  id TEXT PRIMARY KEY, created_at TEXT, trigger_kind TEXT, evidence TEXT,
  message TEXT, delivered INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS speakers(
  name TEXT PRIMARY KEY, label TEXT, embedding BLOB, note TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS events(
  id TEXT PRIMARY KEY, title TEXT, when_dt TEXT, when_raw TEXT, who TEXT,
  "where" TEXT, source_segment TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS reminders(
  id TEXT PRIMARY KEY, what TEXT, when_dt TEXT, when_raw TEXT, recurring TEXT,
  source_segment TEXT, fired INT DEFAULT 0, created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_events_when ON events(when_dt);
CREATE INDEX IF NOT EXISTS idx_reminders_when ON reminders(when_dt, fired);
CREATE TABLE IF NOT EXISTS chat_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS wiki_pages(
  id TEXT PRIMARY KEY, title TEXT, body TEXT, tags TEXT,
  source_ids TEXT, link_ids TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS agents(
  id TEXT PRIMARY KEY, name TEXT, device_uuid TEXT UNIQUE,
  personality TEXT DEFAULT '{}', voice TEXT DEFAULT 'default',
  enabled INT DEFAULT 1, created_at TEXT);"""


def connect(db_path: Path | None = None):
    conn = sqlite3.connect(db_path or config.sqlite_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now_iso() -> str:
    """系统真实本地时间戳（带时区）。所有 created_at/when 用它，杜绝假时间。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _s(x) -> str:
    """LLM 可能返回 list/None，统一转可存字符串。"""
    if x is None:
        return ""
    if isinstance(x, list):
        return ", ".join(str(i) for i in x)
    return str(x)


# ── KV ──────────────────────────────────────────────────────────
def kv_get(key: str, default=None):
    with connect() as c:
        row = c.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return row["v"] if row else default


def kv_set(key: str, value: str):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", (key, value))
        c.commit()


# ── 记忆 ────────────────────────────────────────────────────────
def add_memory(mem: dict, embedding: np.ndarray | None):
    mid = mem.get("id") or f"m-{abs(hash((mem.get('segment_id',''), mem.get('content','')[:40])))%10**12}"
    with connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO memories(id,segment_id,kind,content,evidence,embedding,created_at,processed) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (mid, mem.get("segment_id", ""), mem.get("kind", "event"),
             mem.get("content", ""), mem.get("evidence", ""),
             embedding.tobytes() if embedding is not None else None,
             now_iso(), 0))
        c.commit()
    return mid


def memories_all():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM memories ORDER BY created_at")]


def memories_unprocessed():
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM memories WHERE processed=0 ORDER BY created_at")]


def mark_memories_processed(ids: list[str]):
    if not ids:
        return
    with connect() as c:
        c.executemany("UPDATE memories SET processed=1 WHERE id=?", [(i,) for i in ids])
        c.commit()


def search_memories(query_vec: np.ndarray, k: int = 5):
    """余弦相似 top-k。全量载入 embedding。"""
    with connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM memories WHERE embedding IS NOT NULL")]
    if not rows:
        return []
    mat = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    sims = (mat @ q) / norms[:, 0]
    order = np.argsort(sims)[::-1][:k]
    return [{"memory": rows[i], "score": float(sims[i])} for i in order]


# ── 计数与列表（供 API 端点和 health）──────────────────────────
def count_segments() -> int:
    with connect() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM segments").fetchone()
        return row["n"] if row else 0


def count_memories() -> int:
    with connect() as c:
        row = c.execute("SELECT COUNT(*) AS n FROM memories").fetchone()
        return row["n"] if row else 0


def get_segments(limit: int = 50, offset: int = 0) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM segments ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))]


def get_memories(limit: int = 50, offset: int = 0) -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))]


# ── 人格档案版本 ──────────────────────────────────────────────
def save_persona_version(profile: dict, change_summary: str) -> int:
    with connect() as c:
        v = (c.execute("SELECT COALESCE(MAX(version),0)+1 FROM persona_versions").fetchone()[0])
        c.execute("INSERT INTO persona_versions(version,created_at,profile_json,change_summary) VALUES(?,?,?,?)",
                  (v, now_iso(), json.dumps(profile, ensure_ascii=False), change_summary))
        c.commit()
    p = config.persona_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    stamped = {**profile, "_meta": {"version": v, "updated_at": now_iso(),
                                     "change_summary": change_summary}}
    p.write_text(json.dumps(stamped, ensure_ascii=False, indent=2), encoding="utf-8")
    return v


def latest_persona():
    with connect() as c:
        row = c.execute("SELECT * FROM persona_versions ORDER BY version DESC LIMIT 1").fetchone()
        if not row:
            return None, None, None
        return json.loads(row["profile_json"]), row["change_summary"], row["version"]


# ── 干预 ────────────────────────────────────────────────────────
def add_intervention(trigger_kind: str, evidence: str, message: str):
    iid = f"iv-{abs(hash(message))%10**12}"
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO interventions(id,created_at,trigger_kind,evidence,message,delivered) VALUES(?,?,?,?,?,0)",
                  (iid, now_iso(), trigger_kind, evidence, message))
        c.commit()
    return iid


def interventions_undelivered():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM interventions WHERE delivered=0 ORDER BY created_at")]


# ── 说话人 ──────────────────────────────────────────────────────
def upsert_speaker(name: str, label: str = "", embedding: bytes | None = None, note: str = ""):
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO speakers(name,label,embedding,note,created_at) VALUES(?,?,?,?,?)",
                  (name, label, embedding, note, now_iso()))
        c.commit()


def speakers_all():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT name,label,note,created_at FROM speakers")]


# ── 日历事件 ────────────────────────────────────────────────────
def add_event(ev: dict):
    eid = ev.get("id") or f"ev-{abs(hash((ev.get('title',''), ev.get('when_raw',''))))%10**12}"
    with connect() as c:
        c.execute('INSERT OR REPLACE INTO events(id,title,when_dt,when_raw,who,"where",source_segment,created_at) '
                  "VALUES(?,?,?,?,?,?,?,?)",
                  (eid, _s(ev.get("title")), ev.get("when_dt", ""), _s(ev.get("when_raw")),
                   _s(ev.get("who")), _s(ev.get("where")), _s(ev.get("source_segment")), now_iso()))
        c.commit()
    return eid


def events_range(start: str, end: str):
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM events WHERE when_dt>=? AND when_dt<=? ORDER BY when_dt", (start, end))]


def events_search(keyword: str):
    with connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM events ORDER BY when_dt")]
    if not keyword:
        return rows
    kw = keyword.lower()
    return [r for r in rows if kw in (r.get("title", "") + r.get("who", "") + r.get("where", "")).lower()
            or kw in r.get("when_raw", "").lower()]


# ── 提醒 ────────────────────────────────────────────────────────
def add_reminder(rm: dict):
    rid = rm.get("id") or f"rm-{abs(hash((rm.get('what',''), rm.get('when_raw',''))))%10**12}"
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO reminders(id,what,when_dt,when_raw,recurring,source_segment,fired,created_at) "
                  "VALUES(?,?,?,?,?,?,0,?)",
                  (rid, _s(rm.get("what")), rm.get("when_dt", ""), _s(rm.get("when_raw")),
                   _s(rm.get("recurring")), _s(rm.get("source_segment")), now_iso()))
        c.commit()
    return rid


def reminders_due(now_iso_str: str):
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM reminders WHERE fired=0 AND when_dt<>'' AND when_dt<=? ORDER BY when_dt",
            (now_iso_str,))]


def reminders_all():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM reminders ORDER BY when_dt")]


def mark_reminder_fired(rid: str):
    with connect() as c:
        c.execute("UPDATE reminders SET fired=1 WHERE id=?", (rid,))
        c.commit()


# ── 反幻觉校验辅助 ──────────────────────────────────────────────
def segment_get(seg_id: str):
    with connect() as c:
        row = c.execute("SELECT id,text,created_at,source_file FROM segments WHERE id=?", (seg_id,)).fetchone()
        return dict(row) if row else None


def all_events():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM events")]


def delete_event(eid: str):
    with connect() as c:
        c.execute("DELETE FROM events WHERE id=?", (eid,))
        c.commit()


def set_event_when(eid: str, when_dt: str):
    with connect() as c:
        c.execute("UPDATE events SET when_dt=? WHERE id=?", (when_dt, eid))
        c.commit()


def delete_reminder(rid: str):
    with connect() as c:
        c.execute("DELETE FROM reminders WHERE id=?", (rid,))
        c.commit()


def set_reminder_when(rid: str, when_dt: str):
    with connect() as c:
        c.execute("UPDATE reminders SET when_dt=? WHERE id=?", (when_dt, rid))
        c.commit()


def delete_memory(mid: str):
    with connect() as c:
        c.execute("DELETE FROM memories WHERE id=?", (mid,))
        c.commit()


# ── 对话日志（真实时间戳）──────────────────────────────────────
def add_chat_log(role: str, content: str):
    with connect() as c:
        c.execute("INSERT INTO chat_log(role,content,created_at) VALUES(?,?,?)",
                  (role, content, now_iso()))
        c.commit()


def chat_logs(limit: int = 50):
    with connect() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM chat_log ORDER BY id DESC LIMIT ?", (limit,))]


# ── 个人 wiki ───────────────────────────────────────────────────
def add_wiki_page(p: dict):
    import json as _j
    wid = p.get("id") or f"wiki-{abs(hash(p.get('title', ''))) % 10**12}"
    tags = p.get("tags", [])
    src = p.get("source_ids", [])
    links = p.get("links", [])
    with connect() as c:
        c.execute("INSERT OR REPLACE INTO wiki_pages(id,title,body,tags,source_ids,link_ids,created_at) "
                  "VALUES(?,?,?,?,?,?,?)",
                  (wid, _s(p.get("title")), _s(p.get("body")),
                   _j.dumps(tags, ensure_ascii=False), _j.dumps(src, ensure_ascii=False),
                   _j.dumps(links, ensure_ascii=False), now_iso()))
        c.commit()
    return wid


def all_wiki_pages():
    import json as _j
    with connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM wiki_pages ORDER BY created_at")]
    for r in rows:
        for k in ("tags", "source_ids", "link_ids"):
            try:
                r[k] = _j.loads(r[k]) if r.get(k) else []
            except Exception:
                r[k] = []
    return rows


def wiki_search(tag: str = "", query: str = ""):
    pages = all_wiki_pages()
    if tag:
        pages = [p for p in pages if tag in (p.get("tags") or [])]
    if query:
        q = query.lower()
        pages = [p for p in pages if q in (p.get("title", "") + p.get("body", "")).lower()]
    return pages


# ── wiki 增量: 已 wikified 的记忆 id（kv，不改 schema）──────────
def wikified_ids() -> set:
    import json as _j
    raw = kv_get("wikified_mem_ids")
    try:
        return set(_j.loads(raw)) if raw else set()
    except Exception:
        return set()


def mark_wikified(ids) -> None:
    import json as _j
    cur = wikified_ids() | set(ids)
    kv_set("wikified_mem_ids", _j.dumps(list(cur), ensure_ascii=False))


# ── 多 Agent 管理 ──────────────────────────────────────────────
def register_agent(device_uuid: str, name: str = "") -> dict:
    """注册或更新一个 agent（按 device_uuid 识别，idempotent）。"""
    a_id = f"agent-{device_uuid[:8]}"
    now = now_iso()
    with connect() as c:
        existing = c.execute("SELECT * FROM agents WHERE device_uuid=? OR id=?", (device_uuid, a_id)).fetchone()
        if existing:
            c.execute("UPDATE agents SET name=?, device_uuid=? WHERE id=?",
                      (name or existing["name"], device_uuid, existing["id"]))
        else:
            c.execute("INSERT INTO agents(id,name,device_uuid,personality,voice,enabled,created_at) "
                      "VALUES(?,?,?,'{}','default',1,?)", (a_id, name or device_uuid[:8], device_uuid, now))
        c.commit()
        row = c.execute("SELECT * FROM agents WHERE id=?", (a_id,)).fetchone()
    return dict(row)


def get_agent(agent_id: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    return dict(row) if row else None


def get_agent_by_device(device_uuid: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT * FROM agents WHERE device_uuid=?", (device_uuid,)).fetchone()
    return dict(row) if row else None


def list_agents() -> list[dict]:
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM agents ORDER BY created_at")]


def update_agent(agent_id: str, updates: dict) -> dict | None:
    """更新 agent 的 name / personality / voice / enabled。"""
    allowed = {"name", "personality", "voice", "enabled"}
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return get_agent(agent_id)
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values())
    with connect() as c:
        c.execute(f"UPDATE agents SET {sets} WHERE id=?", (*vals, agent_id))
        c.commit()
        row = c.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    return dict(row) if row else None
