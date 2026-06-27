"""ingest.py — 新接入编排：设备转录文本(+可选音频) → 解析 → 说话人归属 → 入库
→ 记忆抽取 + 日历事件 + 提醒。ASR 不再做（设备已转录）。
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

from . import config, storage, transcript, speaker, memory, calendar, reminders
from .llm import get_llm, get_embedder


def _paired_audio(p: Path) -> Path | None:
    for suf in (".wav", ".mp3", ".m4a", ".flac"):
        a = p.with_suffix(suf)
        if a.exists():
            return a
    return None


def _analytics(seg_dicts: list[dict], now_iso: str):
    import duckdb
    con = duckdb.connect(str(config.duckdb_path()))
    con.execute("""CREATE TABLE IF NOT EXISTS segment_stats(
      source_file TEXT, seg_id TEXT, start_sec DOUBLE, end_sec DOUBLE,
      speaker TEXT, char_len INT, day TEXT)""")
    for s in seg_dicts:
        day = (s.get("created_at") or now_iso)[:10]
        con.execute("INSERT INTO segment_stats VALUES(?,?,?,?,?,?,?)",
                    (s.get("source_file"), s["id"], s.get("start_sec", 0), s.get("end_sec", 0),
                     s.get("speaker", "user"), len(s.get("text", "")), day))
    con.close()


def ingest_transcript(path: str, llm=None, embedder=None, diarizer=None) -> dict:
    llm = llm or get_llm()
    embedder = embedder or get_embedder()
    p = Path(path)
    uts = transcript.parse(str(p))
    if not uts:
        return {"segments": 0}
    diarizer = diarizer or speaker.get_diarizer()
    audio = _paired_audio(p)
    uts = diarizer.attribute(uts, audio_path=str(audio) if audio else None)

    reference = datetime.now()
    now = storage.now_iso()
    seg_dicts = []
    with storage.connect() as c:
        if c.execute("SELECT 1 FROM ingested_files WHERE source_file=?", (p.name,)).fetchone():
            return {"segments": 0, "skipped": "already ingested"}
        for u in uts:
            sid = f"{p.stem}:{u.line}"
            c.execute("INSERT OR IGNORE INTO segments VALUES(?,?,?,?,?,?,?,?,?)",
                      (sid, p.name, u.start, u.end, u.text, u.speaker, "zh", now, 0))
            seg_dicts.append({"id": sid, "source_file": p.name, "start_sec": u.start,
                              "end_sec": u.end, "text": u.text, "speaker": u.speaker,
                              "created_at": now})
        c.execute("INSERT OR REPLACE INTO ingested_files VALUES(?,?,?)", (p.name, now, len(uts)))
        c.commit()
    try:
        _analytics(seg_dicts, now)
    except Exception as e:
        print(f"[ingest] duckdb analytics skipped: {e}")

    user_segs = [s for s in seg_dicts if s["speaker"] == "user"] or seg_dicts
    m_n = memory.extract_and_store(user_segs, llm, embedder)
    ev_n = calendar.extract(seg_dicts, reference, llm)
    rm_n = reminders.extract(seg_dicts, reference, llm)
    # 反幻觉复查：确定性重解 when_dt + 溯源校验 + 删不落地项
    from . import verify
    vrep = verify.run_all()
    return {"segments": len(uts), "memories": m_n, "events": ev_n, "reminders": rm_n,
            "verify": vrep}


def scan_inbox() -> dict:
    """轮询 inbox：转录文件(.txt/.srt/.json) 优先；纯音频回退 ASR。"""
    inbox = config.inbox_dir()
    total = {"segments": 0, "memories": 0, "events": 0, "reminders": 0, "files": 0}
    for f in sorted(inbox.iterdir()):
        if f.name.startswith(".") or f.is_dir():
            continue
        suf = f.suffix.lower()
        if suf in (".txt", ".srt", ".json", ".vtt"):
            r = ingest_transcript(str(f))
            print(f"[ingest] {f.name} -> {r}")
            for k in ("segments", "memories", "events", "reminders"):
                total[k] += r.get(k, 0)
            total["files"] += 1
        elif suf in (".wav", ".mp3", ".m4a", ".flac"):
            # 设备没给转录才回退 ASR（罕见，按 ASR 后端处理）
            from .asr import IngestionPipeline
            n = IngestionPipeline().process_file(str(f))
            print(f"[ingest-asr] {f.name} -> {n} segments (no transcript)")
            total["segments"] += n
            total["files"] += 1
    return total
