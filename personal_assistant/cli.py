"""cli.py — 命令行入口：pipeline / distill / chat / proactive / calendar / reminders / speakers / status / serve / test。"""
from __future__ import annotations
import argparse
import json
import sys

from . import (config, storage, asr, memory, distill, proactive, chat,
               ingest, calendar, reminders, speaker, verify)


def cmd_pipeline(args):
    if args.once:
        r = ingest.scan_inbox()
        print(f"ingest: {r}")
    else:
        print("polling inbox (Ctrl-C to stop)…")
        import time
        while True:
            print(ingest.scan_inbox())
            time.sleep(args.poll)


def cmd_distill(args):
    print(json.dumps(distill.DistillationEngine().run(), ensure_ascii=False, indent=2))


def cmd_chat(args):
    a = chat.Assistant()
    print("（输入消息，空行退出；对话带真实时间戳存档）")
    for line in sys.stdin:
        msg = line.strip()
        if not msg:
            break
        storage.add_chat_log("user", msg)            # 真实系统时间戳
        reply = a.respond(msg)
        storage.add_chat_log("assistant", reply)
        print("🤖", reply)


def cmd_verify(args):
    rep = verify.run_all()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    try:
        verify.assert_no_hallucination()
        print("✅ 反幻觉断言通过：所有事件 when_dt 确定性可复算、when_raw 落地源文本")
    except AssertionError as e:
        print(f"❌ 幻觉检出：{e}")


def cmd_proactive(args):
    fired = proactive.ProactiveEngine().check()
    print(f"fired {len(fired)} interventions")


def cmd_calendar(args):
    if args.list:
        evs = storage.events_search("")
    else:
        evs = calendar.search(args.query or "")
    print(f"{len(evs)} events:")
    for e in evs:
        print(f"  {e.get('when_dt','?')}  {e.get('title','')}  ({e.get('when_raw','')})  [{e.get('who','')}]")


def cmd_reminders(args):
    if args.check:
        n = reminders.ReminderScheduler().check_due()
        print(f"fired {n} due reminders")
    else:
        rms = storage.reminders_all()
        print(f"{len(rms)} reminders:")
        for r in rms:
            flag = "✅" if r.get("fired") else "⏳"
            print(f"  {flag} {r.get('when_dt','?')}  {r.get('what','')}  ({r.get('when_raw','')})  [{r.get('recurring','')}]")


def cmd_speakers(args):
    sps = storage.speakers_all()
    print(f"{len(sps)} speakers:")
    for s in sps:
        print(f"  {s['name']}  label={s.get('label','')}  {s.get('note','')}")


def cmd_status(args):
    with storage.connect() as c:
        nseg = c.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
        nmem = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        nev = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        nrm = c.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
    p, summ, v = storage.latest_persona()
    print(f"segments:{nseg} memories:{nmem} events:{nev} reminders:{nrm} persona_v:{v}")
    if p:
        print(f"profile: {json.dumps(p, ensure_ascii=False)[:300]}")


def cmd_serve(args):
    import uvicorn
    uvicorn.run("personal_assistant.api:app", host=args.host, port=args.port, reload=False)


def cmd_test(args):
    from tests.test_e2e import run
    sys.exit(0 if run() else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="personal-assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pipeline"); p.add_argument("--once", action="store_true"); p.add_argument("--poll", type=float, default=10.0); p.set_defaults(func=cmd_pipeline)
    sub.add_parser("distill").set_defaults(func=cmd_distill)
    sub.add_parser("chat").set_defaults(func=cmd_chat)
    sub.add_parser("proactive").set_defaults(func=cmd_proactive)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    c = sub.add_parser("calendar"); c.add_argument("query", nargs="?"); c.add_argument("--list", action="store_true"); c.set_defaults(func=cmd_calendar)
    r = sub.add_parser("reminders"); r.add_argument("--check", action="store_true"); r.set_defaults(func=cmd_reminders)
    sub.add_parser("speakers").set_defaults(func=cmd_speakers)
    sub.add_parser("status").set_defaults(func=cmd_status)
    s = sub.add_parser("serve"); s.add_argument("--host", default="0.0.0.0"); s.add_argument("--port", type=int, default=8000); s.set_defaults(func=cmd_serve)
    sub.add_parser("test").set_defaults(func=cmd_test)

    args = ap.parse_args(argv)
    config.ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
