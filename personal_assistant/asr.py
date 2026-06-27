"""asr.py — 接入监听 + VAD + 转写 + 说话人分离。

Transcriber 接口 + StubTranscriber(dev,可读 .txt 转录稿) + FasterWhisperTranscriber(prod,lazy import)。
IngestionPipeline：轮询 inbox → 转写 → 片段入库(SQLite) + DuckDB 分析 → 归档音频。
"""
from __future__ import annotations
import time
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path

from . import config


@dataclass
class Segment:
    id: str
    source_file: str
    start_sec: float
    end_sec: float
    text: str
    speaker: str = "user"
    language: str = "zh"
    created_at: str = ""

    def to_tuple(self):
        return (self.id, self.source_file, self.start_sec, self.end_sec,
                self.text, self.speaker, self.language, self.created_at, 0)


class Transcriber:
    def transcribe(self, audio_path: str) -> list[Segment]:
        raise NotImplementedError


class StubTranscriber(Transcriber):
    """若 inbox 文件是 .txt 转录稿，按行切成带假时间戳的片段；否则用内建样例。"""

    SAMPLE = [
        "今天和朋友去爬山了，山顶风景很好，很开心。",
        "最近工作有点累，明天打算早点休息。",
        "我觉得应该多读点书，喜欢历史类的。",
        "下周准备去看一部新电影，朋友推荐的。",
        "有点焦虑项目的进度，但慢慢来吧。",
    ]

    def transcribe(self, audio_path: str) -> list[Segment]:
        p = Path(audio_path)
        lines: list[str]
        if p.suffix.lower() == ".txt" and p.exists():
            lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        else:
            lines = self.SAMPLE
        segs = []
        t = 0.0
        for i, line in enumerate(lines):
            sid = f"{p.stem}-{i:03d}"
            dur = max(2.0, len(line) * 0.4)
            segs.append(Segment(sid, p.name, t, t + dur, line, "user", "zh", ""))
            t += dur + 0.5
        return segs


class FasterWhisperTranscriber(Transcriber):
    """prod：faster-whisper(CTranslate2,免 torch) + vad_filter。lazy import。"""

    def __init__(self):
        self._model = None

    def _ensure(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # lazy
            c = config.get("asr.faster_whisper", {})
            self._model = WhisperModel(
                c.get("model_size", "small"),
                device=c.get("device", "cpu"),
                compute_type=c.get("compute_type", "int8"),
            )
        return self._model

    def transcribe(self, audio_path: str) -> list[Segment]:
        model = self._ensure()
        c = config.get("asr.faster_whisper", {})
        segs = []
        segments, _info = model.transcribe(
            audio_path, vad_filter=c.get("vad_filter", True),
            language=config.get("asr.language", "zh"),
        )
        p = Path(audio_path)
        for i, s in enumerate(segments):
            sid = f"{p.stem}-{i:03d}"
            segs.append(Segment(sid, p.name, s.start, s.end, s.text.strip(),
                                "user", config.get("asr.language", "zh"), ""))
        return segs


def get_transcriber() -> Transcriber:
    backend = config.get("asr.backend", "stub")
    if backend == "stub":
        return StubTranscriber()
    if backend == "faster_whisper":
        return FasterWhisperTranscriber()
    raise ValueError(f"unknown asr backend: {backend}")


class IngestionPipeline:
    """轮询 inbox，转写新文件，片段入库 + DuckDB 分析，音频归档。"""

    def __init__(self, transcriber: Transcriber | None = None, db_path: Path | None = None):
        self.transcriber = transcriber or get_transcriber()
        self.db_path = db_path or config.sqlite_path()
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS segments(
              id TEXT PRIMARY KEY, source_file TEXT, start_sec REAL, end_sec REAL,
              text TEXT, speaker TEXT, language TEXT, created_at TEXT, processed INT DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ingested_files(
              source_file TEXT PRIMARY KEY, ingested_at TEXT, n_segments INT);
            """)
            c.commit()

    def _already(self, c, name: str) -> bool:
        row = c.execute("SELECT 1 FROM ingested_files WHERE source_file=?", (name,)).fetchone()
        return row is not None

    def process_file(self, audio_path: str) -> int:
        from datetime import datetime
        name = Path(audio_path).name
        with self._conn() as c:
            if self._already(c, name):
                return 0
            now = datetime.utcnow().isoformat(timespec="seconds")
            segs = self.transcriber.transcribe(audio_path)
            for s in segs:
                s.created_at = now
                c.execute("INSERT OR IGNORE INTO segments VALUES(?,?,?,?,?,?,?,?,?)", s.to_tuple())
            c.execute("INSERT OR REPLACE INTO ingested_files VALUES(?,?,?)",
                      (name, now, len(segs)))
            c.commit()
        try:
            self._analytics(segs)
        except Exception as e:
            print(f"[asr] duckdb analytics skipped: {e}")
        return len(segs)

    def _analytics(self, segs: list[Segment]):
        import duckdb
        dpath = config.duckdb_path()
        con = duckdb.connect(str(dpath))
        con.execute("""
            CREATE TABLE IF NOT EXISTS segment_stats(
              source_file TEXT, seg_id TEXT, start_sec DOUBLE, end_sec DOUBLE,
              speaker TEXT, char_len INT, day TEXT)
        """)
        from datetime import datetime
        for s in segs:
            day = (s.created_at or datetime.utcnow().isoformat())[:10]
            con.execute("INSERT INTO segment_stats VALUES(?,?,?,?,?,?,?)",
                        (s.source_file, s.id, s.start_sec, s.end_sec, s.speaker, len(s.text), day))
        con.close()

    def scan_once(self) -> int:
        inbox = config.inbox_dir()
        total = 0
        for f in sorted(inbox.iterdir()):
            if f.name.startswith(".") or f.is_dir():
                continue
            if f.suffix.lower() not in (".wav", ".mp3", ".m4a", ".flac", ".txt", ".json"):
                continue
            n = self.process_file(str(f))
            print(f"[asr] {f.name} -> {n} segments")
            total += n
        return total

    def run_loop(self, poll_seconds: float = 10.0):
        while True:
            self.scan_once()
            time.sleep(poll_seconds)
