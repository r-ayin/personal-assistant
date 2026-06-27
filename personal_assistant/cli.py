"""cli.py — 命令行入口：pipeline / distill / chat / proactive / status / serve / test。"""
from __future__ import annotations
import argparse
import json
import sys

from . import config, storage, asr, memory, distill, proactive, chat


def cmd_pipeline(args):
    pipe = asr.IngestionPipeline()
    if args.once:
        n = pipe.scan_once()
        print(f"ingested {n} segments")
    else:
        print("polling inbox (Ctrl-C to stop)…")
        pipe.run_loop(args.poll)


def cmd_distill(args):
    r = distill.DistillationEngine().run()
    print(json.dumps(r, ensure_ascii=False, indent=2))


def cmd_chat(args):
    a = chat.Assistant()
    print("（输入消息，空行退出）")
    for line in sys.stdin:
        msg = line.strip()
        if not msg:
            break
        print("🤖", a.respond(msg))


def cmd_proactive(args):
    fired = proactive.ProactiveEngine().check()
    print(f"fired {len(fired)} interventions")


def cmd_status(args):
    with storage.connect() as c:
        nseg = c.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
        nmem = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    p, summ, v = storage.latest_persona()
    print(f"segments: {nseg}  memories: {nmem}  persona_version: {v}")
    print(f"profile: {json.dumps(p, ensure_ascii=False)[:400] if p else '(none — run distill)'}")


def cmd_serve(args):
    import uvicorn
    uvicorn.run("personal_assistant.api:app", host=args.host, port=args.port, reload=False)


def cmd_test(args):
    from tests.test_e2e import run
    ok = run()
    sys.exit(0 if ok else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="personal-assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pipeline"); p.add_argument("--once", action="store_true"); p.add_argument("--poll", type=float, default=10.0); p.set_defaults(func=cmd_pipeline)
    sub.add_parser("distill").set_defaults(func=cmd_distill)
    sub.add_parser("chat").set_defaults(func=cmd_chat)
    sub.add_parser("proactive").set_defaults(func=cmd_proactive)
    sub.add_parser("status").set_defaults(func=cmd_status)
    s = sub.add_parser("serve"); s.add_argument("--host", default="0.0.0.0"); s.add_argument("--port", type=int, default=8000); s.set_defaults(func=cmd_serve)
    sub.add_parser("test").set_defaults(func=cmd_test)

    args = ap.parse_args(argv)
    config.ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
