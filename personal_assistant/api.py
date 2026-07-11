"""api.py — FastAPI 控制端（含 WS 骨干 + 背景音频收集）。"""
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, Query, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from . import config, storage, memory, distill, proactive, chat, ingest, calendar, reminders, speaker
from . import auth, ws_manager, xiaozhi_server

log = logging.getLogger("pa.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动后台巡检。"""
    ws_manager.manager.start_heartbeat()
    stop = asyncio.Event()

    async def _patrol():
        reminder_poll = 60.0
        proactive_interval = float(config.get("proactive.check_interval_minutes", 30) or 30) * 60
        last_proactive = 0.0
        while not stop.is_set():
            try:
                fired_r = await asyncio.to_thread(_collect_due_reminders)
                for item in fired_r:
                    await ws_manager.manager.broadcast(ws_manager.EV_REMINDER, item)
                now = asyncio.get_event_loop().time()
                if now - last_proactive >= proactive_interval:
                    fired_i = await asyncio.to_thread(_collect_proactive)
                    for item in fired_i:
                        await ws_manager.manager.broadcast(ws_manager.EV_INTERVENTION, item)
                    last_proactive = now
            except Exception as e:
                log.warning("patrol error: %s", e)
            try:
                await asyncio.wait_for(stop.wait(), timeout=reminder_poll)
            except asyncio.TimeoutError:
                pass
    task = asyncio.create_task(_patrol())

    # 启动原始 TCP 音频服务器（端口 8004，绕过 WS 层）
    from . import audio_tcp
    audio_server = asyncio.create_task(audio_tcp.start_server())
    log.info("bg audio TCP server started on port 8004")
    yield
    stop.set()
    await task
    await ws_manager.manager.shutdown()


def _collect_due_reminders():
    fired = reminders.check_due()
    return [{"what": r["what"], "when_raw": r["when_raw"], "id": r["id"]} for r in fired]


def _collect_proactive():
    tr = proactive.check()
    return [{"kind": t["kind"], "message": t["message"], "evidence": t.get("evidence", [])} for t in tr]


app = FastAPI(title="personal-assistant", version="0.6.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_WEB_DIR = config.ROOT / "web"
if _WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")


@app.get("/")
def root():
    return RedirectResponse(url="/web/")


class ChatIn(BaseModel):
    message: str


# ── WebSocket ──────────────────────────────────────────────────


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    """手机/Web 端实时推送通道。
    上行：{type:"chat", text:"..."} 或 {type:"ping"}
    下行：任何 broadcast 事件（transcription/chat_reply/reminder/intervention/record）"""
    if not auth.verify_ws_token(ws):
        await ws.close(code=1008)
        return
    await ws_manager.manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            await _handle_live_message(ws, raw)
    except WebSocketDisconnect:
        ws_manager.manager.disconnect(ws)
    except Exception as e:
        log.warning("ws_live error: %s", e)
        ws_manager.manager.disconnect(ws)


async def _handle_live_message(ws: WebSocket, raw: str) -> None:
    import json
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return
    mtype = msg.get("type")
    if mtype == "chat":
        text = (msg.get("text") or "").strip()
        if not text:
            return
        await asyncio.to_thread(storage.add_chat_log, "user", text)
        reply, evidence = await asyncio.to_thread(chat.Assistant().respond, text)
        await asyncio.to_thread(storage.add_chat_log, "assistant", reply, evidence=evidence)
        await ws_manager.manager.broadcast(ws_manager.EV_CHAT_REPLY,
                                           {"text": reply, "evidence": evidence or [],
                                            "is_partial": False})
    elif mtype == "ping":
        await ws_manager.manager.send_to(ws, "pong", {})


async def _save_bg_segment(pcm: bytes, inbox_dir: Path, session_id: str, agent_id: str = "") -> str | None:
    """保存 PCM 段为 WAV 到 inbox，供 scan_inbox 处理。"""
    import wave, io
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    agent_tag = f"-agent={agent_id}" if agent_id else ""
    name = f"bg-{session_id}-{ts}{agent_tag}.wav"
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    try:
        (inbox_dir / name).write_bytes(wav_io.getvalue())
        log.info("bg segment saved: %s (%dB, %.1fs)", name, len(pcm), len(pcm) / 32000)
        return name
    except Exception as e:
        log.warning("bg segment save failed: %s", e)
        return None


@app.websocket("/ws/audio")
async def ws_audio(ws: WebSocket):
    """ESP32 双模式固件背景音频流（Opus 帧）。

    帧格式：
      Byte 0 = 类型: 0=opus_frame, 1=segment_end, 2=ping
      Bytes 1+ = Opus 载荷

    流程：Opus 解码 → RMS VAD 切段 → WAV 到 inbox → scan_inbox。
    可选 query 参数: agent_id 标记来源设备。"""
    await ws.accept()
    # 解析 agent_id（来自 /ws/audio?agent_id=xxx）
    ws_agent_id = ws.query_params.get("agent_id", "")

    # VAD 切段器（内联精简版，零依赖）
    class _Vad:
        def __init__(self, threshold=350, holdout=500, min_utt=300):
            self.rms_threshold = threshold
            self.holdout_ms = holdout
            self.min_utt_ms = min_utt
            self._buf = bytearray()
            self._speaking = False
            self._silence = 0
            self._speech = 0
            self._chunk_n = 512

        def feed(self, pcm: bytes):
            import struct, math
            out = []
            n = len(pcm) // 2
            for i in range(0, n, self._chunk_n):
                chunk = pcm[i*2:(i+self._chunk_n)*2]
                if len(chunk) < 2: break
                samples = struct.unpack(f"<{len(chunk)//2}h", chunk)
                rms = int(math.sqrt(sum(s*s for s in samples) / len(samples)))
                voice = rms >= self.rms_threshold
                if not self._speaking:
                    if voice:
                        self._buf.extend(chunk)
                        if len(self._buf) >= self._chunk_n * 2 * 2:
                            self._speaking = True
                            self._speech = len(self._buf) // 2
                            self._silence = 0
                    else:
                        self._buf = bytearray()
                else:
                    self._buf.extend(chunk)
                    self._speech += self._chunk_n
                    if voice:
                        self._silence = 0
                    else:
                        self._silence += 1
                        ms = self._silence * (self._chunk_n * 1000 // 16000)
                        if ms >= self.holdout_ms:
                            utt_ms = self._speech * 1000 // 16000
                            if utt_ms >= self.min_utt_ms:
                                out.append(bytes(self._buf))
                            self._buf = bytearray()
                            self._speaking = False
                            self._speech = 0
                            self._silence = 0
            return out

        def flush(self):
            out = []
            if self._speaking:
                utt_ms = self._speech * 1000 // 16000
                if utt_ms >= self.min_utt_ms:
                    out.append(bytes(self._buf))
            self._buf = bytearray()
            self._speaking = False
            return out

    segmenter = _Vad()
    inbox_dir = config.inbox_dir()
    session_id = f"esp32-bg-{datetime.now().strftime('%H%M%S')}"
    wav_count = 0

    try:
        while True:
            raw = await ws.receive_bytes()
            if not raw:
                continue
            frame_type = raw[0]

            if frame_type == 0:  # PCM 帧
                # PCM 16kHz 16bit mono, raw data starts after type byte
                pcm = raw[1:]
                for seg in segmenter.feed(pcm):
                    await _save_bg_segment(seg, inbox_dir, session_id, ws_agent_id)
                    wav_count += 1

            elif frame_type == 1:  # 段结束
                for seg in segmenter.flush():
                    await _save_bg_segment(seg, inbox_dir, session_id, ws_agent_id)
                    wav_count += 1

            elif frame_type == 2:  # Ping
                try:
                    await ws.send_bytes(b"\x02")
                except Exception:
                    pass

    except WebSocketDisconnect:
        log.info("ws_audio %s disconnected (%d segs)", session_id, wav_count)
    except Exception as e:
        log.warning("ws_audio error: %s", e)
    finally:
        for seg in segmenter.flush():
            await _save_bg_segment(seg, inbox_dir, session_id, ws_agent_id)
            wav_count += 1
        if wav_count > 0:
            log.info("ws_audio %s total %d segments, triggering ingest", session_id, wav_count)
            try:
                await asyncio.to_thread(ingest.scan_inbox)
            except Exception as e:
                log.warning("ingest after ws_audio: %s", e)


@app.websocket("/ws/xiaozhi")
async def ws_xiaozhi(ws: WebSocket):
    """xiaozhi-esp32 设备接入（唤醒词+对话）。"""
    await xiaozhi_server.xiaozhi_endpoint(ws)


# ── REST API ────────────────────────────────────────────────────


@app.get("/health")
def health():
    from . import llm
    cfg = llm.effective_llm_config()
    return {"status": "ok", "segments": storage.count_segments(),
            "memories": storage.count_memories(),
            "llm": f"{cfg.get('backend','?')} · {cfg.get('model','?')}",
            "asr": "faster_whisper",
            "embedder": "hashing",
            "speaker": "TextDiarizer",
            "db": f"SQLite {storage.db_size_mb()} MB"}


@app.get("/segments")
def list_segments(limit: int = 50, offset: int = 0, agent_id: str = ""):
    segs = storage.get_segments(limit, offset, agent_id)
    return {"segments": segs, "total": storage.count_segments()}


@app.post("/segments/search")
def search_segments(q: str = "", limit: int = 20):
    segs = storage.get_segments(limit, 0)
    if q:
        ql = q.lower()
        segs = [s for s in segs if ql in (s.get("text","") or "").lower()]
    return {"segments": segs[:limit]}


@app.get("/memories")
def list_memories(limit: int = 50, offset: int = 0, agent_id: str = ""):
    mems = storage.get_memories(limit, offset, agent_id)
    return {"memories": mems, "total": storage.count_memories()}


@app.post("/memories/search")
def search_memories(q: str = "", limit: int = 20):
    if q:
        mems = storage.search_memories_by_text(q, limit)
    else:
        mems = storage.get_memories(limit, 0)
    return {"memories": mems}


@app.post("/chat/clear")
def clear_chat():
    n = storage.clear_chat_log()
    return {"deleted": n}


@app.get("/interventions")
def list_interventions(limit: int = 20):
    items = storage.get_interventions(limit)
    return {"interventions": items}


@app.post("/interventions/scan")
def scan_interventions():
    """手动触发干预扫描（主动检查触发器并生成新干预）。"""
    from . import proactive as _proactive
    triggers = _proactive.check()
    n = 0
    for t in triggers:
        storage.add_intervention({
            "trigger_kind": t.get("kind", "unknown"),
            "evidence": ",".join(m.get("id", "") for m in t.get("memories", [])),
            "message": t.get("message", "检测到干预信号"),
        })
        n += 1
    return {"generated": n, "triggers": triggers}


@app.get("/profile")
def get_profile():
    try:
        p = distill.current_profile()
        return p or {"error": "no profile"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/distill")
def run_distill():
    n = distill.run()
    return {"distilled": n, "profile": distill.load_persona()}


class ChatIn(BaseModel):
    message: str


@app.post("/chat")
def chat_endpoint(body: ChatIn):
    reply = chat.Assistant().respond(body.message)
    evidence = []
    storage.add_chat_log("user", body.message)
    try:
        storage.add_chat_log("assistant", reply)
    except Exception:
        pass
    return {"reply": reply, "evidence": evidence}


@app.post("/proactive")
def check_proactive():
    return proactive.check()


@app.post("/ingest")
def run_ingest():
    ingest.scan_inbox()
    return {"ok": True}


@app.get("/events")
def list_events(day: str = ""):
    try:
        rows = storage.all_events()
        if day:
            rows = [r for r in rows if r.get("when_dt", "").startswith(day)]
        return {"events": rows}
    except Exception as e:
        return {"events": [], "error": str(e)}


@app.get("/reminders")
def list_reminders():
    return {"reminders": storage.reminders_all()}


@app.get("/speakers")
def list_speakers():
    return {"speakers": storage.speakers_all()}


@app.get("/chat-log")
def chat_log(limit: int = 50):
    return {"chat_log": storage.chat_logs(limit)}


@app.post("/verify")
def run_verify():
    from . import verify
    return verify.run_all()


@app.get("/recommend")
def do_recommend(kind: str = "", q: str = ""):
    from . import recommend
    items = recommend.recommend(kind=kind or "book", query=q or "")
    return {"recommendations": items}


@app.get("/wiki")
def search_wiki(q: str = "", tag: str = ""):
    from . import wiki
    pages = wiki.retrieve(tag=tag, query=q) if (tag or q) else wiki.retrieve()
    return {"pages": pages, "topics": []}


@app.post("/wiki/build")
def build_wiki():
    from . import wiki
    result = wiki.build()
    return {"ok": True, "pages_created": result.get("pages_created", 0) if isinstance(result, dict) else 0}


@app.get("/status")
def full_status():
    try:
        pf_ver = None
        _p, _s, pf_ver = storage.latest_persona()
    except Exception:
        pf_ver = 0
    return {
        "segments": storage.count_segments(),
        "memories": storage.count_memories(),
        "events": len(storage.all_events()),
        "reminders": len(storage.reminders_all()),
        "speakers": len(storage.speakers_all()),
        "profile_version": pf_ver or 0,
    }


class LLMSettingsIn(BaseModel):
    backend: str | None = None
    model: str | None = None
    context_window: int | None = None
    max_tokens: int | None = None
    thinking_effort: str | None = None
    thinking_format: str | None = None
    base_url: str | None = None
    api_key: str | None = None


@app.get("/settings/llm")
def llm_settings_get():
    from . import llm
    return llm.effective_llm_config()


@app.post("/settings/llm")
def llm_settings_update(body: LLMSettingsIn):
    if body.backend:
        if body.backend not in ("stub", "deepseek", "anthropic_proxy", "ollama",
                                "openai_compat", "glm_anthropic"):
            raise HTTPException(400, f"unknown backend: {body.backend}")
        config.set_override("llm.backend", body.backend)
    backend = config.get("llm.backend", "stub")
    applied = []
    if backend == "stub":
        return {"backend": "stub", "applied": [], "note": "stub 无可配字段"}
    for field in ("model", "context_window", "max_tokens", "thinking_effort",
                  "thinking_format", "base_url", "api_key"):
        val = getattr(body, field)
        if val is not None:
            config.set_override(f"llm.{backend}.{field}", val)
            applied.append(field)
    from . import llm
    eff = llm.effective_llm_config()
    return {"backend": backend, "applied": applied, "effective": eff}


@app.post("/inbox/upload")
async def inbox_upload(request: Request, filename: str = Query(...)):
    if not filename.endswith((".txt", ".srt")):
        raise HTTPException(400, "only .txt/.srt accepted")
    inbox = config.inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / filename
    content = await request.body()
    dest.write_bytes(content)
    return {"saved": str(dest.relative_to(config.ROOT)), "bytes": len(content),
            "ingest_hint": "POST /ingest to scan"}


# ── 多 Agent 管理 ─────────────────────────────────────────────
class AgentIn(BaseModel):
    device_uuid: str
    name: str = ""


class AgentUpdate(BaseModel):
    name: str | None = None
    personality: str | None = None
    voice: str | None = None
    enabled: bool | None = None


@app.get("/agents")
def list_agents():
    return {"agents": storage.list_agents()}


@app.post("/agents")
def register_agent(body: AgentIn):
    return storage.register_agent(body.device_uuid, body.name)


@app.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    a = storage.get_agent(agent_id)
    if not a:
        raise HTTPException(404, f"agent {agent_id} not found")
    return a


@app.put("/agents/{agent_id}")
def update_agent(agent_id: str, body: AgentUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    a = storage.update_agent(agent_id, updates)
    if not a:
        raise HTTPException(404, f"agent {agent_id} not found")
    return a
