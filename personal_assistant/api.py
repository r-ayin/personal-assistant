"""api.py — FastAPI 控制端（录音上传 + 文字聊天 + 记忆系统）。"""
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

from . import assistant_personality, config, storage, memory_bridge, proactive, chat, ingest, calendar, reminders, speaker
from . import auth

log = logging.getLogger("pa.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动后台巡检（提醒 + 主动干预）。"""
    stop = asyncio.Event()

    async def _patrol():
        reminder_poll = 60.0
        proactive_interval = float(config.get("proactive.check_interval_minutes", 30) or 30) * 60
        last_proactive = 0.0
        while not stop.is_set():
            try:
                await asyncio.to_thread(_collect_due_reminders)
                now = asyncio.get_event_loop().time()
                if now - last_proactive >= proactive_interval:
                    await asyncio.to_thread(_collect_proactive)
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


@app.get("/moments", dependencies=[Depends(_require_bearer)])
def list_moments_route(limit: int = 80):
    """融合记忆系统时刻清单（微信等来源提取的本人时刻）。"""
    return {"moments": memory_bridge.list_moments(limit=limit)}


@app.get("/memories/recall", dependencies=[Depends(_require_bearer)])
def recall_memories(q: str, k: int = 5, strategy: str = "hybrid"):
    """v0.10 混合召回端点（BM25+向量+RRF，带预算控制）。"""
    from . import memory_bridge as recall_mod
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


@app.get("/profile", dependencies=[Depends(_require_bearer)])
def get_profile():
    _inferred, _change_summary, _version = storage.latest_persona()
    return {
        "inferred": memory_bridge.inferred_profile(),
        "effective": memory_bridge.current_profile(),
        "version": _version or 0,
        "change_summary": _change_summary or "",
        "feedback": storage.list_profile_feedback(),
    }


@app.post("/distill")
def run_distill():
    n = memory_bridge.run_distill()
    return {"distilled": n, "profile": memory_bridge.load_persona()}


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
    from . import memory_bridge
    return memory_bridge.wiki_search(q) if q else {"topics": memory_bridge.wiki_list_topics()}


@app.post("/wiki/build")
def build_wiki():
    from . import memory_bridge
    return memory_bridge.wiki_build()


@app.post("/triggers")
def fire_triggers():
    return proactive.ProactiveEngine().check()


@app.get("/status")
def full_status():
    return {
        "segments": storage.count_segments(),
        "memories": memory_bridge.count_memories(),
        "events": len(calendar.get_events()),
        "reminders": len(reminders.list_all()),
        "speakers": len(storage.get_speakers()),
        "profile_version": memory_bridge.current_version(),
    }


# ── 画像 / 复杂度指标 / 混合检索（读融合系统 memory.db，只读）──────────
# 定位方式沿用 memory_bridge：融合根 = PA 项目根的上一级。画像数据由 P5 逐步长出，
# 库不存在时返回 available:false 而非 500。
_MEMORY_DB = Path(config.ROOT).parent / "memory.db"


def _memdb():
    if not _MEMORY_DB.is_file():
        return None
    import sqlite3
    c = sqlite3.connect(f"file:{_MEMORY_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args)]


@app.get("/portrait/self")
def portrait_self():
    c = _memdb()
    if not c:
        return {"available": False}
    with c:
        person = _rows(c, "SELECT * FROM person WHERE person_id='self'")
        return {
            "available": True,
            "person": person[0] if person else None,
            "traits": _rows(c, "SELECT dimension,dist,promoted,n_independent_conv,is_proxy "
                               "FROM trait WHERE subject_id='self' ORDER BY promoted DESC, "
                               "n_independent_conv DESC"),
            "goals": _rows(c, """SELECT *, CAST(julianday('now') - julianday(last_active_at) AS INT) stale_days
                                 FROM goal WHERE subject_id='self'
                                 ORDER BY last_active_at DESC LIMIT 30"""),
            "tasks": _rows(c, """SELECT t.*, u.ts source_ts,
                                        CAST(julianday('now') - julianday(u.ts) AS INT) stale_days
                                 FROM task t LEFT JOIN utterance u ON u.id = t.utterance_id
                                 WHERE t.subject_id='self'
                                   AND t.status IN ('inbox','active','blocked')
                                 ORDER BY stale_days ASC"""),
            "values": _rows(c, "SELECT * FROM value WHERE subject_id='self' "
                               "ORDER BY recurrence_count DESC LIMIT 20"),
            "affect": _rows(c, "SELECT * FROM affect_profile WHERE subject_id='self'"),
            "growth": _rows(c, "SELECT * FROM growth WHERE subject_id='self'"),
        }


@app.get("/portrait/circles")
def portrait_circles(limit: int = 60):
    c = _memdb()
    if not c:
        return {"available": False}
    with c:
        people = _rows(c, """
            SELECT p.person_id, p.display_name, p.role, p.person_kind, p.profile_card,
                   COUNT(DISTINCT u.conv_id) convs, COUNT(*) msgs,
                   (SELECT COALESCE(SUM(c2.user_msg), 0) FROM conversation c2
                     WHERE c2.conv_id IN
                       (SELECT u2.conv_id FROM utterance u2 WHERE u2.person_id = p.person_id)
                   ) user_msgs,
                   MIN(u.ts) first_ts, MAX(u.ts) last_ts
            FROM person p JOIN utterance u ON u.person_id = p.person_id
            WHERE p.person_kind IN ('person','self')
            GROUP BY p.person_id ORDER BY user_msgs DESC, msgs DESC LIMIT ?""", (limit,))
        return {
            "available": True,
            "people": people,
            "layers": _rows(c, "SELECT * FROM metric WHERE name IN "
                               "('dunbar_layers','signature_shares','social_entropy')"),
        }


@app.get("/portrait/person")
def portrait_person(id: str):
    c = _memdb()
    if not c:
        return {"available": False}
    with c:
        person = _rows(c, "SELECT * FROM person WHERE person_id=?", (id,))
        if not person:
            return {"available": True, "person": None}
        return {
            "available": True,
            "person": person[0],
            "aliases": _rows(c, "SELECT label,alias_space,evidence_count,confidence "
                                "FROM person_alias WHERE person_id=? "
                                "ORDER BY evidence_count DESC", (id,)),
            "traits": _rows(c, "SELECT dimension,dist,promoted,n_independent_conv,is_proxy "
                               "FROM trait WHERE subject_id=? ORDER BY promoted DESC", (id,)),
            "values": _rows(c, "SELECT * FROM value WHERE subject_id=? "
                               "ORDER BY recurrence_count DESC LIMIT 12", (id,)),
            "affect": _rows(c, "SELECT * FROM affect_profile WHERE subject_id=?", (id,)),
            "moments": _rows(c, "SELECT id,verbatim_quote,narrative,tags,ts,recalled "
                                "FROM moment WHERE counterpart_person_id=? "
                                "ORDER BY ts DESC LIMIT 30", (id,)),
            "metrics": _rows(c, "SELECT name,value,ci_low,ci_high,n,eligible,"
                                "ineligible_reason FROM metric WHERE subject_id=?", (id,)),
        }


@app.get("/portrait/metrics")
def portrait_metrics():
    c = _memdb()
    if not c:
        return {"available": False}
    with c:
        return {"available": True,
                "metrics": _rows(c, "SELECT subject_id,subject_kind,name,value,ci_low,ci_high,"
                                    "n,null_baseline,params,eligible,ineligible_reason,"
                                    "computed_at FROM metric ORDER BY subject_kind,subject_id,name")}


@app.get("/memory/search")
def memory_search(q: str, k: int = 10, person: str = ""):
    """混合检索：FTS5 bigram + 向量网关（不在线自动降级）+ RRF + GA 三维终排。"""
    if not q.strip():
        return {"results": []}
    import sys
    root = str(Path(config.ROOT).parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from memcore import retrieve
    c = retrieve.connect()
    return {"results": retrieve.search(c, q, k=k, person_id=person or None)}


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
        "deepseek", "deepseek_anthropic",
    ):
        raise HTTPException(400, f"unknown backend: {requested}")
    if requested:
        config.set_override("llm.backend", requested)
    backend = requested or config.get("llm.backend", "stub")
    if backend == "stub":
        return {"backend": "stub", "applied": [], "note": "stub 无可配字段"}
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
    # 红队加固：文件名净化防路径穿越（../、绝对路径、空字节逃逸 inbox）
    import re as _re
    safe = Path(filename).name  # 只取最后一段，剥离目录分量
    safe = _re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", safe)
    if not safe or safe in (".", "..") or safe.startswith("."):
        raise HTTPException(400, "invalid filename")
    inbox = config.inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / safe
    if not dest.resolve().is_relative_to(inbox.resolve()):
        raise HTTPException(400, "invalid filename")
    content = await request.body()
    dest.write_bytes(content)
    try:
        saved = str(dest.relative_to(config.ROOT))
    except ValueError:
        saved = str(dest)
    return {"saved": saved, "bytes": len(content),
            "ingest_hint": "POST /ingest to scan"}
