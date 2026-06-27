"""api.py — FastAPI 控制端（MVP 最小集；Web 面板 v1.1 再做）。"""
from __future__ import annotations
from pydantic import BaseModel
from fastapi import FastAPI

from . import config, storage, memory, distill, proactive, asr, chat

app = FastAPI(title="personal-assistant", version="0.1.0")


class ChatIn(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "llm": config.get("llm.backend"),
            "asr": config.get("asr.backend"), "embedder": config.get("embedder.backend")}


@app.post("/ingest")
def ingest():
    n = asr.IngestionPipeline().scan_once()
    return {"ingested_segments": n}


@app.get("/segments")
def segments():
    with storage.connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM segments ORDER BY created_at DESC LIMIT 100")]
    return {"count": len(rows), "segments": rows}


@app.get("/memories")
def memories():
    return {"count": len(storage.memories_all()), "memories": storage.memories_all()[-50:]}


@app.get("/profile")
def profile():
    p, summ, v = storage.latest_persona()
    return {"version": v, "change_summary": summ, "profile": p}


@app.post("/chat")
def converse(body: ChatIn):
    return {"reply": chat.Assistant().respond(body.message)}


@app.post("/distill")
def run_distill():
    return distill.DistillationEngine().run()


@app.post("/triggers")
def run_triggers():
    return {"fired": proactive.ProactiveEngine().check()}
