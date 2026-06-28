"""api.py — FastAPI 控制端。"""
from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from . import config, storage, memory, distill, proactive, chat, ingest, calendar, reminders, speaker

app = FastAPI(title="personal-assistant", version="0.5.0")

# CORS（防前端另行托管时跨域；同源 /web 托管时本不需要）
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

# 同源静态托管前端 web/（/web/ → index.html；fetch 相对路径免跨域）
_WEB_DIR = config.ROOT / "web"
if _WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")


@app.get("/")
def root():
    return RedirectResponse(url="/web/")


class ChatIn(BaseModel):
    message: str


class LLMSettingsIn(BaseModel):
    """POST /settings/llm 入参：任一字段可选，写运行态覆盖当前激活后端。"""
    backend: str | None = None
    model: str | None = None
    context_window: int | None = None
    max_tokens: int | None = None
    thinking_effort: str | None = None
    thinking_format: str | None = None
    base_url: str | None = None
    api_key: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "llm": config.get("llm.backend"), "asr": config.get("asr.backend"),
            "embedder": config.get("embedder.backend"), "speaker": config.get("speaker.backend")}


@app.post("/ingest")
def ingest_now():
    return ingest.scan_inbox()


@app.get("/segments")
def segments():
    with storage.connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM segments ORDER BY created_at DESC LIMIT 100")]
    return {"count": len(rows), "segments": rows}


@app.get("/memories")
def memories():
    ms = storage.memories_all()
    return {"count": len(ms), "memories": ms[-50:]}


@app.get("/profile")
def profile():
    p, summ, v = storage.latest_persona()
    return {"version": v, "change_summary": summ, "profile": p}


@app.post("/chat")
def converse(body: ChatIn):
    storage.add_chat_log("user", body.message)          # 真实系统时间戳
    reply = chat.Assistant().respond(body.message)
    storage.add_chat_log("assistant", reply)
    return {"reply": reply}


@app.post("/verify")
def verify_now():
    from . import verify
    rep = verify.run_all()
    try:
        verify.assert_no_hallucination()
        rep["assertion"] = "passed"
    except AssertionError as e:
        rep["assertion"] = f"failed: {e}"
    return rep


@app.get("/chat-log")
def chat_log():
    return {"logs": storage.chat_logs()}


@app.post("/distill")
def run_distill():
    return distill.DistillationEngine().run()


@app.post("/triggers")
def run_triggers():
    return {"fired": proactive.ProactiveEngine().check()}


@app.get("/calendar")
def calendar_search(q: str = Query(default="")):
    return {"count": 0 if not q else len(calendar.search(q)), "events": calendar.search(q) if q else storage.events_search("")}


@app.get("/events")
def events():
    return {"events": storage.events_search("")}


@app.get("/reminders")
def reminders_list():
    return {"reminders": storage.reminders_all()}


@app.post("/reminders/check")
def reminders_check():
    return {"fired": reminders.ReminderScheduler().check_due()}


@app.get("/speakers")
def speakers():
    return {"speakers": storage.speakers_all()}


@app.get("/recommend")
def recommend_api(kind: str = "book", q: str = Query(default="")):
    from . import recommend
    recs = recommend.recommend(kind=kind, query=q)
    return {"count": len(recs), "recommendations": recs}


@app.get("/wiki")
def wiki_list(tag: str = "", q: str = ""):
    from . import wiki
    return {"pages": wiki.retrieve(tag=tag, query=q)}


@app.post("/wiki/build")
def wiki_build():
    from . import wiki
    return {"built": wiki.build()}


# ── LLM 配置（前端设置面板回接）──────────────────────────────────
@app.get("/settings/llm")
def llm_settings():
    """生效配置（key 掩码）+ native thinking 字段预览。"""
    from . import llm
    return llm.effective_llm_config()


@app.post("/settings/llm")
def llm_settings_update(body: LLMSettingsIn):
    """写运行态覆盖（作用于当前激活后端）。key 不回显。"""
    if body.backend:
        if body.backend not in ("stub", "anthropic_proxy", "ollama",
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
    """上传转录文件到 inbox。原始 body + filename 查询参数（免 multipart 依赖）。
    前端：fetch('/inbox/upload?filename=day1.txt', {method:'POST', body: text})."""
    if not filename.endswith((".txt", ".srt")):
        raise HTTPException(400, "only .txt/.srt accepted")
    inbox = config.inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / filename
    content = await request.body()
    dest.write_bytes(content)
    return {"saved": str(dest.relative_to(config.ROOT)), "bytes": len(content),
            "ingest_hint": "POST /ingest to scan"}
