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
    time_kind: str = "received"   # 'received'=记录时间 | 'occurred'=真实发生时间

    def to_tuple(self):
        return (self.id, self.source_file, self.start_sec, self.end_sec,
                self.text, self.speaker, self.language, self.created_at, 0, self.time_kind)


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
        elif config.get("asr.stub.allow_fake", False):
            lines = self.SAMPLE
        else:
            # 默认拒绝造假：stub 对真实音频返回空而不是写死的样例文本。
            # 假转写一旦入库就成了"用户说过的话"，比缺数据危险得多。
            return []
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


class RemoteWhisperTranscriber(Transcriber):
    """走 OpenAI 兼容的 /v1/audio/transcriptions 远端转写。

    部署机只有 2 核 1.8GB 内存且无 GPU，本地 faster_whisper 跑 large-v3-turbo
    不现实；GPU 机上的服务已经由 frp 隧道 + nginx /asr/ 反代暴露成 OpenAI 兼容
    接口。PA 与隧道同机时把 base_url 指到 127.0.0.1，请求不出公网，token 也
    不必暴露到外网。
    """

    def transcribe(self, audio_path: str) -> list[Segment]:
        import json
        import mimetypes
        import urllib.error
        import urllib.request
        import uuid

        c = config.get("asr.remote_whisper", {}) or {}
        base = str(c.get("base_url") or "").strip().rstrip("/")
        api_key = str(c.get("api_key") or "").strip()

        # config 的 ${VAR} 只替换 env 里存在的键，缺失时字面量会原样留下，
        # 直接拿去请求会得到一个看不懂的 URLError，所以在这里拦住。
        for name, val in (("PA_ASR_BASE_URL", base), ("PA_ASR_API_KEY", api_key)):
            if "${" in val:
                raise ValueError(f"asr.remote_whisper 缺少环境变量 {name}（当前值仍是未替换的占位符）")
        if not base:
            raise ValueError("asr.remote_whisper.base_url 未配置，无法使用 remote_whisper 后端")

        url = base if base.endswith("/audio/transcriptions") else base + "/audio/transcriptions"
        model = c.get("model", "large-v3-turbo")
        timeout = float(c.get("timeout_sec", 300))
        language = c.get("language") or config.get("asr.language", "zh")

        p = Path(audio_path)
        if not p.exists():
            raise FileNotFoundError(audio_path)

        boundary = uuid.uuid4().hex
        fields = {"model": str(model), "response_format": "verbose_json"}
        if language:
            fields["language"] = str(language)
        parts = []
        for k, v in fields.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
            )
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{p.name}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n".encode("utf-8")
        )
        parts.append(p.read_bytes())
        parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(url, data=b"".join(parts), method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"ASR 端点返回 HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"ASR 端点不可达 {url}: {e.reason}") from e

        raw_segs = payload.get("segments") or []
        if not raw_segs:
            # 端点对静音/无人声返回空 segments。有整段 text 时用端点自己给的
            # duration 兜一个粗时间轴；两者都空就返回空，绝不编造内容。
            text_all = str(payload.get("text") or "").strip()
            if not text_all:
                return []
            raw_segs = [{"start": 0.0, "end": float(payload.get("duration") or 0.0), "text": text_all}]

        lang = payload.get("language") or language or "zh"
        segs = []
        for i, s in enumerate(raw_segs):
            txt = str(s.get("text") or "").strip()
            if not txt:
                continue
            segs.append(Segment(f"{p.stem}-{i:03d}", p.name,
                                float(s.get("start") or 0.0), float(s.get("end") or 0.0),
                                txt, "user", lang, ""))
        return segs


def get_transcriber() -> Transcriber:
    backend = config.get("asr.backend", "stub")
    if backend == "stub":
        return StubTranscriber()
    if backend == "faster_whisper":
        return FasterWhisperTranscriber()
    if backend == "remote_whisper":
        return RemoteWhisperTranscriber()
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
        # schema 统一由 storage.connect() 创建（含 time_kind），不本地建表避免列不一致
        from . import storage
        storage.connect()

    def _already(self, c, name: str) -> bool:
        row = c.execute("SELECT 1 FROM ingested_files WHERE source_file=?", (name,)).fetchone()
        return row is not None

    def process_file(self, audio_path: str) -> int:
        from . import storage
        name = Path(audio_path).name
        with storage.connect() as c:
            if c.execute("SELECT 1 FROM ingested_files WHERE source_file=?", (name,)).fetchone():
                return 0
            now = storage.now_iso()
            segs = self.transcriber.transcribe(audio_path)
            # 声纹归角色：远程 diarize 单文件聚类 + 本地 MFCC 库跨文件匹配。
            # 未配置/不可用时保持 transcriber 的默认 speaker，不瞎猜角色。
            if config.get("speaker.backend", "text") == "remote":
                from .speaker import RemoteDiarizer
                _dz = RemoteDiarizer()
                if _dz.available():
                    _dz.label_segments(segs, audio_path)
            for s in segs:
                s.created_at = now
                c.execute("INSERT OR IGNORE INTO segments(id,source_file,start_sec,end_sec,text,speaker,language,created_at,processed,time_kind) VALUES(?,?,?,?,?,?,?,?,?,?)", s.to_tuple())
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
        _ensure_views(con)
        from . import storage as _s
        for s in segs:
            day = (s.created_at or _s.now_iso())[:10]
            con.execute("INSERT INTO segment_stats VALUES(?,?,?,?,?,?,?)",
                        (s.source_file, s.id, s.start_sec, s.end_sec, s.speaker, len(s.text), day))
        con.close()


def _ensure_views(con):
    con.execute("""CREATE OR REPLACE VIEW daily_summary AS
        SELECT day, COUNT(*) AS segments, SUM(char_len) AS total_chars,
               ROUND(SUM(end_sec - start_sec), 1) AS total_duration_sec,
               COUNT(DISTINCT speaker) AS speakers,
               COUNT(DISTINCT source_file) AS files
        FROM segment_stats GROUP BY day ORDER BY day DESC""")
    con.execute("""CREATE OR REPLACE VIEW speaker_summary AS
        SELECT speaker, COUNT(*) AS segments, SUM(char_len) AS total_chars,
               ROUND(AVG(char_len), 0) AS avg_chars_per_seg,
               ROUND(SUM(end_sec - start_sec), 1) AS total_duration_sec,
               COUNT(DISTINCT day) AS active_days
        FROM segment_stats GROUP BY speaker ORDER BY total_chars DESC""")


def query_habits() -> dict:
    """Query DuckDB habit views; returns dict with daily/speaker summaries."""
    import duckdb
    dpath = config.duckdb_path()
    if not dpath.exists():
        return {"daily": [], "speaker": [], "total_days": 0, "total_segments": 0}
    con = duckdb.connect(str(dpath), read_only=True)
    try:
        con.execute("SELECT 1 FROM segment_stats LIMIT 1")
    except duckdb.CatalogException:
        con.close()
        return {"daily": [], "speaker": [], "total_days": 0, "total_segments": 0}
    con.close()
    con = duckdb.connect(str(dpath))
    con.execute("""CREATE TABLE IF NOT EXISTS segment_stats(
        source_file TEXT, seg_id TEXT, start_sec DOUBLE, end_sec DOUBLE,
        speaker TEXT, char_len INT, day TEXT)""")
    _ensure_views(con)
    daily = [dict(zip(["day", "segments", "total_chars", "duration_sec", "speakers", "files"], r))
             for r in con.execute("SELECT * FROM daily_summary").fetchall()]
    speaker = [dict(zip(["speaker", "segments", "total_chars", "avg_chars", "duration_sec", "active_days"], r))
               for r in con.execute("SELECT * FROM speaker_summary").fetchall()]
    meta = con.execute("SELECT COUNT(DISTINCT day), COUNT(*) FROM segment_stats").fetchone()
    con.close()
    return {"daily": daily, "speaker": speaker, "total_days": meta[0], "total_segments": meta[1]}

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
