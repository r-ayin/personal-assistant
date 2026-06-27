"""test_e2e.py — 端到端冒烟（stub 后端，零网络零模型）。

run() 跑通：ingest→ASR→入库→记忆抽取→蒸馏→对话→主动触发，全程断言非空/合法。
cli: `python3 -m personal_assistant.cli test`  或  `python3 -m tests.test_e2e`
"""
from __future__ import annotations
import shutil
from pathlib import Path

from personal_assistant import config, storage, asr, memory, distill, proactive, chat

SAMPLE_TRANSCRIPT = """今天和朋友去爬山了，山顶风景很好，很开心。
最近工作有点累，明天打算早点休息。
我觉得应该多读点书，喜欢历史类的。
下周准备去看一部新电影，朋友推荐的。
有点焦虑项目的进度，但慢慢来吧。
今天又聊到了那部电影，期待。
晚上还在想那部电影的事。
"""


def _reset():
    for p in [config.sqlite_path(), config.duckdb_path(), config.persona_path(),
              config.ROOT / "data" / "logs" / "interventions.log"]:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    inbox = config.inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    for f in inbox.iterdir():
        if f.is_file() and not f.name.startswith("."):
            f.unlink()
    (inbox / "day1.txt").write_text(SAMPLE_TRANSCRIPT, encoding="utf-8")


def run() -> bool:
    print(f"=== e2e  llm={config.get('llm.backend')} asr={config.get('asr.backend')} embedder={config.get('embedder.backend')} ===")
    _reset()
    fails = []

    # 1. ingest → ASR → segments
    n = asr.IngestionPipeline().scan_once()
    print(f"[1] ingest: {n} segments")
    if n < 5:
        fails.append(f"segments {n} < 5")

    # 2. memory extraction + store
    with storage.connect() as c:
        segs = [dict(r) for r in c.execute("SELECT * FROM segments")]
    added = memory.extract_and_store(segs)
    print(f"[2] memories added: {added}")
    if added < 5:
        fails.append(f"memories {added} < 5")

    # 3. distill → persona profile
    r = distill.DistillationEngine().run()
    print(f"[3] distill: {r}")
    if r.get("skipped"):
        fails.append(f"distill skipped: {r.get('reason')}")
    if not config.persona_path().exists():
        fails.append("persona/profile.json not written")

    # 4. chat
    reply = chat.Assistant().respond("我今天有点累，想休息")
    print(f"[4] chat reply: {reply[:80]}")
    if not reply or not reply.strip():
        fails.append("empty chat reply")

    # 5. proactive triggers
    fired = proactive.ProactiveEngine().check()
    print(f"[5] proactive fired: {len(fired)}")
    # 样例含 累/焦虑/明天/下周/电影重复 → 至少 1 条
    if len(fired) < 1:
        fails.append("no proactive interventions fired")

    # 6. retrieval sanity
    hits = memory.search("电影", k=3)
    print(f"[6] retrieve '电影': {len(hits)} hits")
    if not hits:
        fails.append("retrieval returned nothing")

    if fails:
        print("\n❌ FAIL:")
        for f in fails:
            print("  -", f)
        return False
    print("\n✅ PASS — 全链路跑通（stub）")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
