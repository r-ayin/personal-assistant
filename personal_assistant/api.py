"""api.py — FastAPI 控制端。"""
from __future__ import annotations
from pydantic import BaseModel
from fastapi import FastAPI, Query

from . import config, storage, memory, distill, proactive, chat, ingest, calendar, reminders, speaker

app = FastAPI(title="personal-assistant", version="0.2.0")


class ChatIn(BaseModel):
    message: str


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
