"""storage.py — SQLite(片段/记忆/人格版本/干预/kv) + numpy 余弦检索 + DuckDB 已在 asr。

embedding 以 BLOB 存 memories.embedding，检索时全量载入做余弦。MVP 规模足够。
"""
from __future__ import annotations
import json
import sqlite3
import threading
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
  time_kind TEXT DEFAULT 'received');  -- 'received'=记录时间 | 'occurred'=真实发生时间(设备时间戳/强制对齐提供)
CREATE TABLE IF NOT EXISTS ingested_files(
  source_file TEXT PRIMARY KEY, ingested_at TEXT, n_segments INT);
CREATE TABLE IF NOT EXISTS memories(
  id TEXT PRIMARY KEY, segment_id TEXT, kind TEXT, content TEXT, evidence TEXT,
  embedding BLOB, created_at TEXT, processed INT DEFAULT 0,
  priority INTEGER DEFAULT 50,   -- v0.10: 0-100 重要度（TencentDB Memory L1 priority）
  scene_name TEXT DEFAULT '',    -- v0.10: 所属 L2 场景名
  version INTEGER DEFAULT 0,     -- v0.10: 去重 update/merge 单调版本
  updated_at TEXT DEFAULT '');   -- v0.10: 最近去重更新时间
CREATE TABLE IF NOT EXISTS scenes(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, summary TEXT DEFAULT '',
  body TEXT DEFAULT '', heat INTEGER DEFAULT 1,
  source_mem_ids TEXT DEFAULT '[]',  -- JSON 数组，溯源到 memories.id
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS persona_versions(
  version INTEGER PRIMARY KEY, created_at TEXT, profile_json TEXT, change_summary TEXT,
  narrative TEXT DEFAULT '');  -- v0.10: ≤2000 字符叙事档案（L3，对齐 MemoryCore persona.md）
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
  id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, evidence TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS wiki_pages(
  id TEXT PRIMARY KEY, title TEXT, body TEXT, tags TEXT,
  source_ids TEXT, link_ids TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS assistant_personality_versions(
  version INTEGER PRIMARY KEY, preset_id TEXT NOT NULL,
  config_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS barrage_settings(
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  config_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS barrage_deliveries(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, priority TEXT NOT NULL,
  evidence TEXT NOT NULL, status TEXT NOT NULL,
  expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profile_feedback(
  id TEXT PRIMARY KEY, dimension TEXT NOT NULL, value TEXT NOT NULL,
  action TEXT NOT NULL, evidence_kind TEXT NOT NULL, evidence TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
  deactivated_at TEXT NOT NULL DEFAULT '');
"""


# FTS 虚拟表初始化/重建的跨线程互斥：全新数据库并发 connect() 时，
# 两个线程同时对 memories_fts 建表会导致 vtable constructor failed（DatabaseError）。
_FTS_LOCK = threading.RLock()


def connect(db_path: Path | None = None):
    path = db_path or config.sqlite_path()
    with _FTS_LOCK:
        conn = _open_db(path)
        if _fts_corrupted(conn):
            # 损坏的 fts5 表无法 DROP——用独立连接从 sqlite_master 清除后重开
            conn.close()
            _purge_fts(path)
            conn = _open_db(path)
        _ensure_fts(conn)
        return conn


def _open_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # 兼容旧库：chat_log 可能缺少 evidence 列
    try:
        conn.execute("ALTER TABLE chat_log ADD COLUMN evidence TEXT")
    except sqlite3.OperationalError:
        pass
    # v0.10 兼容旧库：memories 四新列 + persona_versions.narrative
    for col, decl in (("priority", "INTEGER DEFAULT 50"),
                      ("scene_name", "TEXT DEFAULT ''"),
                      ("version", "INTEGER DEFAULT 0"),
                      ("updated_at", "TEXT DEFAULT ''")):
        try:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass
    try:
        conn.execute("ALTER TABLE persona_versions ADD COLUMN narrative TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    return conn


def _fts_corrupted(conn) -> bool:
    """区分"表不存在"（正常，待建）与"表损坏"（需清除重建）。

    vtable constructor failed 是 sqlite3.DatabaseError（OperationalError 的父类），
    并发建表竞态或影子表残缺时抛出，必须宽捕获并按损坏处理。
    """
    try:
        conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()
        return False
    except sqlite3.Error as e:
        msg = str(e)
        if "no such table" in msg:
            return False
        return True


def _purge_fts(path) -> None:
    """独立 autocommit 连接删除损坏的 memories_fts 全部影子表。"""
    fix = sqlite3.connect(path)
    fix.isolation_level = None
    fix.execute("PRAGMA writable_schema=ON")
    fix.execute("DELETE FROM sqlite_master WHERE name LIKE 'memories_fts%'")
    fix.execute("PRAGMA writable_schema=OFF")
    fix.close()


def _tokenize_zh(text: str) -> str:
    """中文按字符 bigram 空格连接（无 jieba 依赖），拉丁词保留。
    例：'我喜欢跑步' → '我喜 喜欢 欢跑 跑步'；供 FTS5 默认 tokenizer 检索。"""
    import re
    out = []
    zh_run = []
    for tok in re.findall(r"[\w]+", text or ""):
        if re.search(r"[\u4e00-\u9fff]", tok):
            zh_run.append(tok)
        else:
            if zh_run:
                out.append(_bigrams("".join(zh_run)))
                zh_run = []
            out.append(tok.lower())
    if zh_run:
        out.append(_bigrams("".join(zh_run)))
    return " ".join(out)


def _bigrams(s: str) -> str:
    chars = [c for c in s if "\u4e00" <= c <= "\u9fff"]
    if len(chars) == 1:
        return chars[0]
    return " ".join(chars[i] + chars[i + 1] for i in range(len(chars) - 1))


def _ensure_fts(conn) -> None:
    """memories_fts 虚拟表存在性与一致性：缺表/行数不符则全量重建。
    注意：虚拟表 DDL 必须 autocommit（isolation_level=None），
    隐式事务中创建会导致 %_config 元数据不落盘（'invalid fts5 file format'）。
    健康检查只用 SELECT（不写），避免遗留未提交事务。"""
    try:
        n_fts = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]
        n_mem = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        if n_fts == n_mem:
            return
    except sqlite3.Error:
        pass
    _fts_rebuild(conn)


def _fts_drop(conn) -> None:
    """安全删除 memories_fts：损坏表先删影子表再删主表（需 writable_schema）。"""
    conn.commit()  # 先提交挂起事务，避免持锁干扰
    conn.execute("PRAGMA writable_schema=ON")
    try:
        for name in ("memories_fts_data", "memories_fts_idx", "memories_fts_content",
                     "memories_fts_docsize", "memories_fts_config"):
            conn.execute("DELETE FROM sqlite_master WHERE name=?", (name,))
        conn.execute("DELETE FROM sqlite_master WHERE name='memories_fts'")
    finally:
        conn.execute("PRAGMA writable_schema=OFF")


def _fts_rebuild(conn) -> None:
    old = conn.isolation_level
    conn.isolation_level = None  # autocommit：虚拟表 DDL 要求
    try:
        try:
            conn.execute("DROP TABLE IF EXISTS memories_fts")
        except sqlite3.OperationalError:
            _fts_drop(conn)
        conn.execute(
            "CREATE VIRTUAL TABLE memories_fts USING fts5("
            "content, content_original UNINDEXED, mem_id UNINDEXED)")
        rows = conn.execute("SELECT id, content FROM memories").fetchall()
        for r in rows:
            conn.execute(
                "INSERT INTO memories_fts(content, content_original, mem_id) VALUES(?,?,?)",
                (_tokenize_zh(r["content"]), r["content"], r["id"]))
    finally:
        conn.isolation_level = old


def fts_rebuild() -> None:
    """手动全量重建 FTS 索引（cli/修复用）。"""
    with _FTS_LOCK:
        with connect() as c:
            _fts_rebuild(c)


def fts_search(query: str, k: int = 15) -> list[dict]:
    """BM25 关键词召回：查询同样 bigram 分词后 FTS5 MATCH，按 bm25() 升序（越小越相关）。"""
    q = _tokenize_zh(query)
    if not q.strip():
        return []
    # 各 token OR 连接，单个 token 加引号防特殊字符
    match = " OR ".join('"%s"' % t.replace('"', '""') for t in q.split())
    with connect() as c:
        try:
            rows = c.execute(
                "SELECT mem_id, content_original, bm25(memories_fts) AS rank "
                "FROM memories_fts WHERE memories_fts MATCH ? "
                "ORDER BY rank LIMIT ?", (match, k)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [{"mem_id": r["mem_id"], "content": r["content_original"],
                 "bm25_score": float(r["rank"])} for r in rows]


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
            "INSERT OR REPLACE INTO memories(id,segment_id,kind,content,evidence,embedding,created_at,processed,"
            "priority,scene_name,version,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, mem.get("segment_id", ""), mem.get("kind", "event"),
             mem.get("content", ""), mem.get("evidence", ""),
             embedding.tobytes() if embedding is not None else None,
             now_iso(), 0,
             int(mem.get("priority", 50) or 50), _s(mem.get("scene_name", "")),
             int(mem.get("version", 0) or 0), now_iso()))
        # FTS 同步（先删后插，兼容 REPLACE）
        c.execute("DELETE FROM memories_fts WHERE mem_id=?", (mid,))
        c.execute("INSERT INTO memories_fts(content, content_original, mem_id) VALUES(?,?,?)",
                  (_tokenize_zh(mem.get("content", "")), mem.get("content", ""), mid))
        c.commit()
    return mid


def update_memory(mid: str, *, content: str | None = None, priority: int | None = None,
                  evidence: str | None = None, scene_name: str | None = None) -> None:
    """v0.10 去重 update/merge 用：局部更新 + version+1 + FTS 同步。"""
    with connect() as c:
        row = c.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        if not row:
            return
        new_content = content if content is not None else row["content"]
        new_priority = priority if priority is not None else row["priority"]
        new_evidence = evidence if evidence is not None else row["evidence"]
        new_scene = scene_name if scene_name is not None else row["scene_name"]
        c.execute(
            "UPDATE memories SET content=?, priority=?, evidence=?, scene_name=?, "
            "version=version+1, updated_at=? WHERE id=?",
            (new_content, int(new_priority), new_evidence, new_scene, now_iso(), mid))
        c.execute("DELETE FROM memories_fts WHERE mem_id=?", (mid,))
        c.execute("INSERT INTO memories_fts(content, content_original, mem_id) VALUES(?,?,?)",
                  (_tokenize_zh(new_content), new_content, mid))
        c.commit()


def memory_get(mid: str):
    with connect() as c:
        row = c.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        return dict(row) if row else None


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
def save_persona_version(profile: dict, change_summary: str, narrative: str = "") -> int:
    with connect() as c:
        v = (c.execute("SELECT COALESCE(MAX(version),0)+1 FROM persona_versions").fetchone()[0])
        c.execute("INSERT INTO persona_versions(version,created_at,profile_json,change_summary,narrative) "
                  "VALUES(?,?,?,?,?)",
                  (v, now_iso(), json.dumps(profile, ensure_ascii=False), change_summary, narrative))
        c.commit()
    p = config.persona_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    stamped = {**profile, "_meta": {"version": v, "updated_at": now_iso(),
                                     "change_summary": change_summary}}
    p.write_text(json.dumps(stamped, ensure_ascii=False, indent=2), encoding="utf-8")
    return v


def latest_persona(db_path: Path | None = None):
    with connect(db_path) as c:
        row = c.execute("SELECT * FROM persona_versions ORDER BY version DESC LIMIT 1").fetchone()
        if not row:
            return None, None, None
        return json.loads(row["profile_json"]), row["change_summary"], row["version"]


def latest_narrative(db_path: Path | None = None) -> str:
    """v0.10：最新 L3 叙事档案（无则空串）。"""
    with connect(db_path) as c:
        row = c.execute("SELECT narrative FROM persona_versions ORDER BY version DESC LIMIT 1").fetchone()
        return (row["narrative"] or "") if row else ""


def latest_assistant_personality(db_path: Path | None = None) -> dict | None:
    with connect(db_path) as c:
        row = c.execute(
            "SELECT version,preset_id,config_json,created_at "
            "FROM assistant_personality_versions ORDER BY version DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        **json.loads(row["config_json"]),
        "preset_id": row["preset_id"],
        "version": row["version"],
        "created_at": row["created_at"],
    }


def save_assistant_personality(
    value: dict,
    expected_version: int,
    db_path: Path | None = None,
) -> tuple[int, str]:
    with connect(db_path) as c:
        c.execute("BEGIN IMMEDIATE")
        current_version = c.execute(
            "SELECT COALESCE(MAX(version),0) FROM assistant_personality_versions"
        ).fetchone()[0]
        if current_version != expected_version:
            c.rollback()
            from .assistant_personality import VersionConflict
            raise VersionConflict(
                f"assistant personality version changed: expected {expected_version}, "
                f"current {current_version}"
            )
        version = current_version + 1
        created_at = now_iso()
        payload = {k: v for k, v in value.items() if k != "preset_id"}
        c.execute(
            "INSERT INTO assistant_personality_versions"
            "(version,preset_id,config_json,created_at) VALUES(?,?,?,?)",
            (version, value["preset_id"], json.dumps(payload, ensure_ascii=False), created_at),
        )
        c.commit()
    return version, created_at


def add_profile_feedback(
    *,
    dimension: str,
    value: str,
    action: str,
    evidence_kind: str,
    evidence: str,
    db_path: Path | None = None,
) -> str:
    import uuid

    dimension = dimension.strip()
    value = value.strip()
    evidence = evidence.strip()
    if not dimension or not value or not evidence:
        raise ValueError("dimension, value and evidence must not be empty")
    if action not in {"add", "suppress"}:
        raise ValueError("action must be add or suppress")
    if evidence_kind != "user_statement":
        raise ValueError("evidence_kind must be user_statement")
    feedback_id = f"pf-{uuid.uuid4().hex}"
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO profile_feedback"
            "(id,dimension,value,action,evidence_kind,evidence,active,created_at) "
            "VALUES(?,?,?,?,?,?,1,?)",
            (feedback_id, dimension, value, action, evidence_kind, evidence, now_iso()),
        )
        c.commit()
    return feedback_id


def list_profile_feedback(
    *, active_only: bool = True, db_path: Path | None = None
) -> list[dict]:
    query = "SELECT * FROM profile_feedback"
    if active_only:
        query += " WHERE active=1"
    query += " ORDER BY created_at,id"
    with connect(db_path) as c:
        return [dict(row) for row in c.execute(query)]


def deactivate_profile_feedback(
    feedback_id: str, db_path: Path | None = None
) -> bool:
    with connect(db_path) as c:
        cursor = c.execute(
            "UPDATE profile_feedback SET active=0,deactivated_at=? "
            "WHERE id=? AND active=1",
            (now_iso(), feedback_id),
        )
        c.commit()
        return cursor.rowcount == 1


def get_barrage_settings(db_path: Path | None = None) -> dict | None:
    with connect(db_path) as c:
        row = c.execute(
            "SELECT config_json FROM barrage_settings WHERE singleton=1"
        ).fetchone()
    return json.loads(row["config_json"]) if row else None


def save_barrage_settings(value: dict, db_path: Path | None = None) -> None:
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO barrage_settings(singleton,config_json,updated_at) VALUES(1,?,?) "
            "ON CONFLICT(singleton) DO UPDATE SET config_json=excluded.config_json, "
            "updated_at=excluded.updated_at",
            (json.dumps(value, ensure_ascii=False), now_iso()),
        )
        c.commit()


def add_barrage_delivery(
    event: dict, status: str, db_path: Path | None = None
) -> None:
    with connect(db_path) as c:
        c.execute(
            "INSERT OR REPLACE INTO barrage_deliveries"
            "(id,kind,priority,evidence,status,expires_at,created_at) VALUES(?,?,?,?,?,?,?)",
            (
                event["id"], event["kind"], event["priority"],
                event.get("evidence", ""), status,
                event.get("expires_at", ""), event.get("created_at", now_iso()),
            ),
        )
        c.commit()


def list_barrage_deliveries(db_path: Path | None = None) -> list[dict]:
    with connect(db_path) as c:
        return [
            dict(row) for row in c.execute(
                "SELECT * FROM barrage_deliveries ORDER BY created_at,id"
            )
        ]


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
        c.execute("DELETE FROM memories_fts WHERE mem_id=?", (mid,))
        c.commit()


# ── L2 场景（v0.10）──────────────────────────────────────────────
def scenes_all() -> list[dict]:
    with connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM scenes ORDER BY heat DESC, updated_at, id")]
    for r in rows:
        try:
            r["source_mem_ids"] = json.loads(r.get("source_mem_ids") or "[]")
        except Exception:
            r["source_mem_ids"] = []
    return rows


def scene_get(sid: str):
    with connect() as c:
        row = c.execute("SELECT * FROM scenes WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        r = dict(row)
        try:
            r["source_mem_ids"] = json.loads(r.get("source_mem_ids") or "[]")
        except Exception:
            r["source_mem_ids"] = []
        return r


def scene_upsert(s: dict) -> str:
    sid = s.get("id") or f"sc-{abs(hash(s.get('name', ''))) % 10**12}"
    src = s.get("source_mem_ids", [])
    with connect() as c:
        exist = c.execute("SELECT created_at FROM scenes WHERE id=?", (sid,)).fetchone()
        c.execute(
            "INSERT OR REPLACE INTO scenes(id,name,summary,body,heat,source_mem_ids,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (sid, _s(s.get("name")), _s(s.get("summary", "")), _s(s.get("body", "")),
             int(s.get("heat", 1) or 1), json.dumps(src, ensure_ascii=False),
             exist["created_at"] if exist else now_iso(), now_iso()))
        c.commit()
    return sid


def scene_delete(sid: str):
    with connect() as c:
        c.execute("DELETE FROM scenes WHERE id=?", (sid,))
        c.commit()


# ── 对话日志（真实时间戳）──────────────────────────────────────
def add_chat_log(role: str, content: str, evidence: list[str] | None = None):
    with connect() as c:
        c.execute("INSERT INTO chat_log(role,content,evidence,created_at) VALUES(?,?,?,?)",
                  (role, content, json.dumps(evidence or []), now_iso()))
        c.commit()


def get_segments(limit: int = 50, offset: int = 0):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM segments ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)).fetchall()
        return [dict(r) for r in rows]


def get_memories(limit: int = 50, offset: int = 0):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)).fetchall()
        return [dict(r) for r in rows]


def count_segments() -> int:
    with connect() as c:
        row = c.execute("SELECT COUNT(*) FROM segments").fetchone()
        return row[0] if row else 0


def count_memories() -> int:
    with connect() as c:
        row = c.execute("SELECT COUNT(*) FROM memories").fetchone()
        return row[0] if row else 0


def get_chat_log(limit: int = 50):
    """api.py 用别名，返回 chat_logs 兼容格式。"""
    return chat_logs(limit)


def get_speakers():
    """api.py 用别名。"""
    return speakers_all()


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
