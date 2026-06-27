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
  text TEXT, speaker TEXT, language TEXT, created_at TEXT, processed INT DEFAULT 0);
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
"""


def connect(db_path: Path | None = None):
    conn = sqlite3.connect(db_path or config.sqlite_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


# ── 人格档案版本 ──────────────────────────────────────────────
def save_persona_version(profile: dict, change_summary: str) -> int:
    with connect() as c:
        v = (c.execute("SELECT COALESCE(MAX(version),0)+1 FROM persona_versions").fetchone()[0])
        c.execute("INSERT INTO persona_versions(version,created_at,profile_json,change_summary) VALUES(?,?,?,?)",
                  (v, now_iso(), json.dumps(profile, ensure_ascii=False), change_summary))
        c.commit()
    # 落盘最新版
    p = config.persona_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
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
