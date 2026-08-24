"""ingest.py — 新接入编排：设备转录文本(+可选音频) → 解析 → 说话人归属 → 入库
→ Pipeline 处理链。ASR 不再做（设备已转录）。

Pipeline 是可插拔的处理步骤列表。默认管线 = 记忆抽取 + 日历 + 提醒 + 反幻觉复查。
可通过注入自定义 pipeline 扩展或替换步骤，不修改本文件。
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config, storage, transcript, speaker, memory, calendar, reminders
from .llm import get_llm, get_embedder

# Pipeline 步骤签：(segments, metadata) -> dict
# metadata 包含: {"llm": ..., "embedder": ..., "reference": datetime, ...}
PipelineStep = Callable[[list[dict], dict], dict]


def _default_pipeline(llm, embedder, reference) -> list[PipelineStep]:
    """创建默认处理管线（v0.10：记忆抽取走两阶段去重，可选场景整合）。"""
    def _memory_step(segs, meta):
        user_segs = [s for s in segs if s.get("speaker") == "user"] or segs
        _llm = meta.get("llm", llm)
        _embedder = meta.get("embedder", embedder)
        mems = memory.filter_low_priority(memory.extract(user_segs, _llm))
        if config.get("memory.dedup_enabled", True):
            counts = memory.dedup_and_store(mems, _embedder, _llm)
            return {"memories": counts["stored"], "memories_dedup": counts}
        n = memory.add(mems, _embedder)
        return {"memories": n}

    def _calendar_step(segs, meta):
        n = calendar.extract(segs, meta.get("reference", reference), meta.get("llm", llm))
        return {"events": n}

    def _reminders_step(segs, meta):
        n = reminders.extract(segs, meta.get("reference", reference), meta.get("llm", llm))
        return {"reminders": n}

    def _scene_step(segs, meta):
        # v0.10 L2：新增记忆达到阈值时触发场景整合（verify 前）
        from . import scenes
        if scenes.pending_count() >= config.get("memory.scene_min_memories", 10):
            return {"scenes": scenes.integrate(llm=meta.get("llm", llm))}
        return {"scenes": None}

    def _verify_step(segs, meta):
        from . import verify
        return {"verify": verify.run_all()}

    return [_memory_step, _calendar_step, _reminders_step, _scene_step, _verify_step]


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


def ingest_transcript(path: str, llm=None, embedder=None, diarizer=None,
                      pipeline: list[PipelineStep] | None = None) -> dict:
    llm = llm or get_llm()
    embedder = embedder or get_embedder()
    p = Path(path)
    uts = transcript.parse(str(p))
    if not uts:
        return {"segments": 0}
    diarizer = diarizer or speaker.get_diarizer()
    audio = _paired_audio(p)
    uts = diarizer.attribute(uts, audio_path=str(audio) if audio else None)

    reference = datetime.now().astimezone()
    now = reference.isoformat(timespec="seconds")
    seg_dicts = []
    with storage.connect() as c:
        if c.execute("SELECT 1 FROM ingested_files WHERE source_file=?", (p.name,)).fetchone():
            return {"segments": 0, "skipped": "already ingested"}
        for u in uts:
            sid = f"{p.stem}:{u.line}"
            c.execute("INSERT OR IGNORE INTO segments(id,source_file,start_sec,end_sec,text,speaker,language,created_at,processed,time_kind) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (sid, p.name, u.start, u.end, u.text, u.speaker, "zh", now, 0, "received"))
            seg_dicts.append({"id": sid, "source_file": p.name, "start_sec": u.start,
                              "end_sec": u.end, "text": u.text, "speaker": u.speaker,
                              "created_at": now})
        c.execute("INSERT OR REPLACE INTO ingested_files VALUES(?,?,?)", (p.name, now, len(uts)))
        c.commit()
    try:
        _analytics(seg_dicts, now)
    except Exception as e:
        print(f"[ingest] duckdb analytics skipped: {e}")

    # 运行管线
    steps = pipeline if pipeline is not None else _default_pipeline(llm, embedder, reference)
    meta = {"llm": llm, "embedder": embedder, "reference": reference}
    result = {"segments": len(uts)}
    for step in steps:
        try:
            out = step(seg_dicts, meta)
            if isinstance(out, dict):
                result.update(out)
        except Exception as e:
            print(f"[ingest] pipeline step {step.__name__}: {e}")
    return result


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
