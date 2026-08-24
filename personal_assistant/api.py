"""api.py — FastAPI 控制端（含 WS 骨干 + 背景音频收集）。"""
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from typing import Literal
from fastapi import FastAPI, Query, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from . import assistant_personality, barrage, config, storage, memory, distill, proactive, chat, ingest, calendar, reminders, speaker
from . import auth, ws_manager, xiaozhi_server, audio_ws
from .omni_perception import PerceptionProcessor
from .omni_service import get_omni_service

log = logging.getLogger("pa.api")
omni_processor = PerceptionProcessor()
_api_loop: asyncio.AbstractEventLoop | None = None

_BARRAGE_SOURCE_EVENTS = {
    ws_manager.EV_REMINDER,
    ws_manager.EV_INTERVENTION,
    ws_manager.EV_ASSISTANT_MESSAGE,
    ws_manager.EV_GAME_BARRAGE,
    ws_manager.EV_COURSE_NOTE,
}


async def _broadcast_business_event(event_type: str, payload: dict) -> None:
    await ws_manager.manager.broadcast(event_type, payload)
    if event_type in _BARRAGE_SOURCE_EVENTS:
        await barrage.publish(event_type, payload)


async def _handle_omni_event(event: dict) -> None:
    for event_type, payload in omni_processor.handle(event):
        await _broadcast_business_event(event_type, payload)


def _bridge_omni_event(event: dict) -> None:
    loop = _api_loop
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(_handle_omni_event(event), loop)


# ── 简陋 TCP 音频服务（替代 xiaozhi_server）───────────────────
# ESP32 v33 固件通过原始 TCP 发送二进制帧：1B type + 4B LE length + payload
# type=0 PCM | type=1 segment_end | type=2 ping

async def _tcp_audio_handler(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"[tcp] CONNECTED {addr}", flush=True)
    import struct
    buf = bytearray()
    segm = audio_ws._BgVad()
    assistant = chat.assistant_for(f"audio-tcp:{addr}")
    seg_count = 0
    try:
        while True:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=300)
            if not chunk:
                break
            buf.extend(chunk)
            print(f"[tcp] RECV {len(chunk)}B from {addr}", flush=True)
            while len(buf) >= 5:
                t = buf[0]
                flen = struct.unpack('<I', buf[1:5])[0]
                if flen > 65536:
                    buf.clear(); break
                if len(buf) < 5 + flen:
                    print(f"[tcp] WAIT type={t} need={5+flen}B have={len(buf)}B", flush=True)
                    break
                payload = bytes(buf[5:5+flen])
                buf = buf[5+flen:]
                if t == 0:  # PCM
                    seg_count += 1
                    for seg in segm.feed(payload):
                        await audio_ws._save_and_detect(seg, config.inbox_dir(), assistant)
                elif t == 1:  # segment end
                    for seg in segm.flush():
                        await audio_ws._save_and_detect(seg, config.inbox_dir(), assistant)
                elif t == 2:  # ping
                    writer.write(b'\x02'); await writer.drain()
    except (asyncio.TimeoutError, ConnectionResetError) as e:
        print(f"[tcp] CLOSED {addr}: {e}", flush=True)
    except Exception as e:
        print(f"[tcp] ERROR {addr}: {e}", flush=True)
    try:
        writer.close()
    except Exception:
        pass

async def _start_tcp_audio(host="0.0.0.0", port=8004):
    srv = await asyncio.start_server(_tcp_audio_handler, host, port)
    print(f"[tcp_audio] ON {host}:{port}", flush=True)
    async with srv:
        await srv.serve_forever()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动后台巡检；ESP32 v38+ 用 /ws/audio WebSocket，不再开 TCP 8004。"""
    global _api_loop
    _api_loop = asyncio.get_running_loop()
    service = get_omni_service()
    add_event_sink = getattr(service, "add_event_sink", None)
    if callable(add_event_sink):
        add_event_sink(_bridge_omni_event)
    if config.get("llm.backend", "stub") == "minicpm_o":
        await asyncio.to_thread(service.acquire_sync, "chat-backend")
    ws_manager.manager.start_heartbeat()
    stop = asyncio.Event()
    # 后台预热 ASR 模型（faster_whisper 首载 ~8s，预热后首句语音响应快很多）
    from . import xiaozhi_server
    asyncio.ensure_future(asyncio.to_thread(xiaozhi_server.warmup_asr))

    async def _patrol():
        reminder_poll = 60.0
        proactive_interval = float(config.get("proactive.check_interval_minutes", 30) or 30) * 60
        last_proactive = 0.0
        while not stop.is_set():
            try:
                fired_r = await asyncio.to_thread(_collect_due_reminders)
                for item in fired_r:
                    await _broadcast_business_event(ws_manager.EV_REMINDER, item)
                now = asyncio.get_event_loop().time()
                if now - last_proactive >= proactive_interval:
                    fired_i = await asyncio.to_thread(_collect_proactive)
                    for item in fired_i:
                        await _broadcast_business_event(ws_manager.EV_INTERVENTION, item)
                    last_proactive = now
            except Exception as e:
                log.warning("patrol error: %s", e)
            try:
                await asyncio.wait_for(stop.wait(), timeout=reminder_poll)
            except asyncio.TimeoutError:
                pass
    task = asyncio.create_task(_patrol())
    yield
    stop.set()
    await task
    if get_omni_service().status()["state"] != "stopped":
        await asyncio.to_thread(get_omni_service().stop_sync)
    _api_loop = None
    await ws_manager.manager.shutdown()


def _collect_due_reminders():
    fired = reminders.check_due()
    return [{"what": r["what"], "when_raw": r["when_raw"], "id": r["id"]} for r in fired]


def _collect_proactive():
    tr = proactive.ProactiveEngine().check()
    return [{"kind": t["kind"], "message": t["message"], "evidence": t.get("evidence", [])} for t in tr]


app = FastAPI(title="personal-assistant", version="0.8.0", lifespan=lifespan)
app.middleware("http")(auth.auth_middleware)

# ── 最小 Bearer token gate（PA-M-001）──────────────────────────────
async def _require_bearer(request: Request) -> None:
    await auth.verify_http(request)


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_WEB_DIR = config.ROOT / "web" / "dist"
if (_WEB_DIR / "index.html").is_file():
    app.mount("/web", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
else:
    log.warning("PA Web static export not found at %s; /web is not mounted", _WEB_DIR)


@app.get("/")
def root():
    return RedirectResponse(url="/web/")


class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None


# ── WebSocket ──────────────────────────────────────────────────


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    """Role-aware live channel for Web pages, overlay and PA devices."""
    if not auth.verify_ws_token(ws):
        await ws.accept()
        await ws.close(code=1008)
        return
    role = ws.query_params.get("client", "page")
    raw_version = ws.query_params.get("version", "1")
    try:
        version = int(raw_version)
    except ValueError:
        await ws.accept()
        await ws.close(code=1008)
        return
    if role not in {"page", "overlay", "device"} or version != 1:
        await ws.accept()
        await ws.close(code=1008)
        return
    await ws_manager.manager.connect(ws, role=role, version=version)
    conversation_id = ws.query_params.get("conversation_id") or chat.new_conversation_id("ws")
    live_assistant = chat.assistant_for("ws:" + conversation_id)
    await ws_manager.manager.send_to(
        ws, "hello", {"client": role, "version": version}
    )
    if role == "overlay":
        await ws_manager.manager.send_to(ws, "barrage_settings", barrage.get_settings())
    try:
        while True:
            raw = await ws.receive_text()
            await _handle_live_message(ws, raw, assistant=live_assistant)
    except WebSocketDisconnect:
        ws_manager.manager.disconnect(ws)
    except Exception as e:
        log.warning("ws_live error: %s", e)
        ws_manager.manager.disconnect(ws)


async def _handle_live_message(
    ws: WebSocket,
    raw: str,
    assistant: chat.Assistant | None = None,
) -> None:
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
        live_assistant = assistant or chat.assistant_for(f"ws-direct:{id(ws)}")
        await asyncio.to_thread(storage.add_chat_log, "user", text)
        reply, evidence = await asyncio.to_thread(live_assistant.respond, text)
        await asyncio.to_thread(storage.add_chat_log, "assistant", reply, evidence=evidence)
        await ws_manager.manager.broadcast(ws_manager.EV_CHAT_REPLY,
                                           {"text": reply, "evidence": evidence or [],
                                            "is_partial": False})
    elif mtype == "ping":
        await ws_manager.manager.send_to(ws, "pong", {})


async def _save_bg_segment(pcm: bytes, inbox_dir: Path, session_id: str) -> str | None:
    """保存 PCM 段为 WAV 到 inbox，供 scan_inbox 处理。"""
    import wave, io
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"bg-{session_id}-{ts}.wav"
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

    流程：Opus 解码 → RMS VAD 切段 → WAV 到 inbox → scan_inbox。"""
    if not auth.verify_ws_token(ws):
        await ws.close(code=1008)
        return
    await ws.accept()

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
                    await _save_bg_segment(seg, inbox_dir, session_id)
                    wav_count += 1

            elif frame_type == 1:  # 段结束
                for seg in segmenter.flush():
                    await _save_bg_segment(seg, inbox_dir, session_id)
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
            await _save_bg_segment(seg, inbox_dir, session_id)
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
    return {"status": "ok", "segments": storage.count_segments(),
            "memories": storage.count_memories()}


@app.get("/segments")
def list_segments(limit: int = 50, offset: int = 0):
    segs = storage.get_segments(limit, offset)
    return {"segments": segs, "total": storage.count_segments()}


@app.get("/memories", dependencies=[Depends(_require_bearer)])
def list_memories(limit: int = 50, offset: int = 0):
    mems = storage.get_memories(limit, offset)
    return {"memories": mems, "total": storage.count_memories()}


@app.get("/memories/recall", dependencies=[Depends(_require_bearer)])
def recall_memories(q: str, k: int = 5, strategy: str = "hybrid"):
    """v0.10 混合召回端点（BM25+向量+RRF，带预算控制）。"""
    from . import recall as recall_mod
    rr = recall_mod.hybrid_recall(q, k=k, strategy=strategy)
    items = [{"id": it["memory"]["id"], "kind": it["memory"].get("kind", ""),
              "content": it["memory"].get("content", ""),
              "priority": it["memory"].get("priority", 50),
              "score": it["score"], "sources": it["sources"]} for it in rr.items]
    return {"items": items, "truncated": rr.truncated,
            "elapsed_ms": rr.elapsed_ms, "strategy": rr.strategy}


class AssistantPersonalityIn(BaseModel):
    preset_id: Literal["gentle", "rational", "lively", "coach", "custom"]
    name: str
    user_address: str
    directness: int
    humor: int
    initiative: Literal["quiet", "restrained", "balanced", "active", "companion"]
    reply_length: Literal["short", "balanced", "detailed"]
    barrage_style: Literal["restrained", "light", "coach", "game"]
    taboos: list[str]
    custom_instruction: str


class AssistantPersonalitySaveIn(AssistantPersonalityIn):
    expected_version: int


class ProfileFeedbackIn(BaseModel):
    dimension: Literal[
        "personality", "values", "goals", "habits", "skills", "knowledge",
        "thinking_patterns", "preferences", "affective_baseline",
    ]
    value: str
    action: Literal["add", "suppress"]
    evidence_kind: Literal["user_statement"]
    evidence: str


def _personality_value(body: AssistantPersonalityIn) -> dict:
    return body.model_dump(exclude={"expected_version"})


@app.get("/assistant/personality", dependencies=[Depends(_require_bearer)])
def get_assistant_personality():
    return assistant_personality.current()


@app.put("/assistant/personality", dependencies=[Depends(_require_bearer)])
def put_assistant_personality(body: AssistantPersonalitySaveIn):
    try:
        return assistant_personality.save(
            _personality_value(body), expected_version=body.expected_version
        )
    except assistant_personality.VersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/assistant/personality/preview", dependencies=[Depends(_require_bearer)])
def preview_assistant_personality(body: AssistantPersonalityIn):
    try:
        value = assistant_personality.validate(_personality_value(body))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    name = value["name"]
    address = value["user_address"]
    direct = {
        1: "我会先听你说完，再温和地给出建议",
        2: "我会用温和的方式说明重点",
        3: "我会直接说明重点，也保留必要背景",
        4: "我会直接给出判断和下一步",
        5: "我会明确指出问题，并推动你马上行动",
    }[value["directness"]]
    humor = "，偶尔带一点轻松感" if value["humor"] >= 4 else ""
    initiative = {
        "quiet": "只在到期提醒时打扰你",
        "restrained": "仅在依据充分时主动提醒",
        "balanced": "在关键时机主动提醒",
        "active": "发现可行动的变化就及时提醒",
        "companion": "会更自然地陪你推进当前事情",
    }[value["initiative"]]
    style = {
        "restrained": "提醒：约定的时间到了，请查看待办。",
        "light": "提醒一下：时间到了，别让待办等太久。",
        "coach": "时间到了。现在完成第一步，然后继续。",
        "game": "时间到，目标刷新：先处理这项待办。",
    }[value["barrage_style"]]
    return {
        "chat": f"{address}，我是{name}。{direct}{humor}。",
        "reminder": f"{address}，{style}",
        "perception": f"{address}，{initiative}；事实不确定时我会明确说明。",
    }


@app.post("/profile/feedback", dependencies=[Depends(_require_bearer)])
def add_profile_feedback(body: ProfileFeedbackIn):
    try:
        feedback_id = storage.add_profile_feedback(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"id": feedback_id, "active": True}


@app.delete("/profile/feedback/{feedback_id}", dependencies=[Depends(_require_bearer)])
def delete_profile_feedback(feedback_id: str):
    if not storage.deactivate_profile_feedback(feedback_id):
        raise HTTPException(status_code=404, detail="profile feedback not found")
    return {"id": feedback_id, "active": False}


class BarrageSettingsIn(BaseModel):
    enabled: bool | None = None
    quiet_mode: bool | None = None
    paused_until: str | None = None
    position: Literal["top", "center", "bottom"] | None = None
    font_size: int | None = None
    opacity: float | None = None
    duration_seconds: int | None = None
    theme: Literal["contrast", "light", "dark"] | None = None
    display_id: str | None = None


@app.get("/barrage/settings", dependencies=[Depends(_require_bearer)])
def get_barrage_settings():
    return barrage.get_settings()


@app.put("/barrage/settings", dependencies=[Depends(_require_bearer)])
async def put_barrage_settings(body: BarrageSettingsIn):
    patch = body.model_dump(exclude_none=True)
    try:
        settings = barrage.patch_settings(patch)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await ws_manager.manager.broadcast("barrage_settings", settings, roles={"overlay"})
    return settings


@app.get("/barrage/status", dependencies=[Depends(_require_bearer)])
def get_barrage_status():
    settings = barrage.get_settings()
    return {
        "settings": settings,
        "overlay_clients": ws_manager.manager.presence()["overlay"],
        "paused": barrage.is_paused(settings),
    }


@app.post("/barrage/test", dependencies=[Depends(_require_bearer)])
async def test_barrage():
    event = await barrage.publish("test", {"text": "这是一条 PA 测试弹幕"})
    if event is None:
        raise HTTPException(status_code=409, detail="barrage is disabled, paused or quiet")
    return event


@app.get("/profile", dependencies=[Depends(_require_bearer)])
def get_profile():
    inferred, change_summary, version = storage.latest_persona()
    return {
        "inferred": distill.normalize(inferred) if inferred else distill.normalize({}),
        "effective": distill.current_profile(),
        "version": version or 0,
        "change_summary": change_summary or "",
        "feedback": storage.list_profile_feedback(),
    }


@app.post("/distill")
def run_distill():
    n = distill.run()
    return {"distilled": n, "profile": distill.load_persona()}


@app.post("/chat", dependencies=[Depends(_require_bearer)])
def chat_endpoint(body: ChatIn):
    conversation_id = (body.conversation_id or "").strip() or chat.new_conversation_id("rest")
    result = chat.assistant_for("rest:" + conversation_id).respond_detailed(body.message)
    storage.add_chat_log("user", body.message)
    storage.add_chat_log("assistant", result.reply, evidence=result.evidence)
    return {
        "reply": result.reply,
        "evidence": result.evidence,
        "conversation_id": conversation_id,
        "metadata": result.metadata,
    }


@app.post("/proactive")
def check_proactive():
    return proactive.ProactiveEngine().check()


@app.post("/ingest")
def run_ingest():
    ingest.scan_inbox()
    return {"ok": True}


@app.get("/events")
def list_events(day: str = ""):
    if day:
        return {"events": calendar.get_events(day)}
    return {"events": calendar.get_events()}


@app.get("/calendar")
def search_calendar(q: str = ""):
    return {"events": calendar.search(q), "query": q}


@app.get("/reminders")
def list_reminders():
    return {"reminders": reminders.list_all()}


@app.post("/reminders/check")
def check_reminders():
    fired = reminders.check_due()
    return {"fired": len(fired), "items": fired}


@app.get("/speakers")
def list_speakers():
    return {"speakers": storage.get_speakers()}


@app.get("/chat-log", dependencies=[Depends(_require_bearer)])
def chat_log(limit: int = 50):
    return {"chat_log": storage.get_chat_log(limit)}


@app.get("/verify")
def run_verify():
    from . import verify
    return verify.run_all()


@app.post("/recommend")
def do_recommend(kind: str = "book", query: str = ""):
    from . import recommend
    return {"recommendations": recommend.recommend(kind=kind, query=query)}


@app.get("/wiki")
def search_wiki(q: str = ""):
    from . import wiki
    return wiki.search(q) if q else {"topics": wiki.list_topics()}


@app.post("/wiki/build")
def build_wiki():
    from . import wiki
    return wiki.build()


@app.post("/triggers")
def fire_triggers():
    return proactive.ProactiveEngine().check()


@app.get("/status")
def full_status():
    return {
        "segments": storage.count_segments(),
        "memories": storage.count_memories(),
        "events": len(calendar.get_events()),
        "reminders": len(reminders.list_all()),
        "speakers": len(storage.get_speakers()),
        "profile_version": distill.current_version(),
    }


@app.get("/local-model/status")
def local_model_status():
    return get_omni_service().status()


@app.post("/local-model/start", dependencies=[Depends(_require_bearer)])
async def local_model_start():
    try:
        status = await asyncio.to_thread(get_omni_service().acquire_sync, "manual")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    await ws_manager.manager.broadcast(ws_manager.EV_LOCAL_MODEL_STATUS, status)
    return status


@app.post("/local-model/stop", dependencies=[Depends(_require_bearer)])
async def local_model_stop():
    status = await asyncio.to_thread(get_omni_service().release_sync, "manual")
    await ws_manager.manager.broadcast(ws_manager.EV_LOCAL_MODEL_STATUS, status)
    return status


@app.post("/perception/start", dependencies=[Depends(_require_bearer)])
async def perception_start():
    service = get_omni_service()
    try:
        await asyncio.to_thread(service.acquire_sync, "perception")
        await asyncio.to_thread(service.request_sync, "start_monitoring", {})
    except RuntimeError as exc:
        await asyncio.to_thread(service.release_sync, "perception")
        raise HTTPException(503, str(exc)) from exc
    status = service.status()
    await ws_manager.manager.broadcast(ws_manager.EV_PERCEPTION, {"state": "running"})
    await ws_manager.manager.broadcast(ws_manager.EV_LOCAL_MODEL_STATUS, status)
    return {"perception": "running", "local_model": status}


@app.post("/perception/stop", dependencies=[Depends(_require_bearer)])
async def perception_stop():
    service = get_omni_service()
    if "perception" not in service.consumers():
        return {"perception": "stopped", "local_model": service.status()}
    try:
        await asyncio.to_thread(service.request_sync, "stop_monitoring", {})
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    status = await asyncio.to_thread(service.release_sync, "perception")
    await ws_manager.manager.broadcast(ws_manager.EV_PERCEPTION, {"state": "stopped"})
    await ws_manager.manager.broadcast(ws_manager.EV_LOCAL_MODEL_STATUS, status)
    return {"perception": "stopped", "local_model": status}


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
    requested = body.backend
    if requested and requested not in (
        "stub", "anthropic_proxy", "ollama", "openai_compat", "glm_anthropic",
        "deepseek", "deepseek_anthropic", "minicpm_o",
    ):
        raise HTTPException(400, f"unknown backend: {requested}")
    previous = config.get("llm.backend", "stub")
    backend = requested or previous
    service = get_omni_service()
    if backend == "minicpm_o" and previous != "minicpm_o":
        try:
            service.acquire_sync("chat-backend")
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
    if requested:
        config.set_override("llm.backend", requested)
    if previous == "minicpm_o" and backend != "minicpm_o":
        service.release_sync("chat-backend")
    if backend == "stub":
        return {"backend": "stub", "applied": [], "note": "stub 无可配字段"}
    if backend == "minicpm_o":
        from . import llm
        return {"backend": backend, "applied": [],
                "effective": llm.effective_llm_config()}
    applied = []
    for field in ("model", "context_window", "max_tokens", "thinking_effort",
                  "thinking_format", "base_url", "api_key"):
        val = getattr(body, field)
        if val is not None:
            config.set_override(f"llm.{backend}.{field}", val)
            applied.append(field)
    from . import llm
    eff = llm.effective_llm_config()
    return {"backend": backend, "applied": applied, "effective": eff}


@app.post("/inbox/upload", dependencies=[Depends(_require_bearer)])
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
