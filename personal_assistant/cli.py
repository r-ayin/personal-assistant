"""cli.py — 命令行入口：pipeline / distill / chat / proactive / calendar / reminders / speakers / status / serve / test。"""
from __future__ import annotations
import argparse
import json
import logging
import sys
import os
import urllib.error
import urllib.request

from . import (config, storage, asr, memory_bridge, proactive, chat,
               ingest, calendar, reminders, speaker, verify, recommend)


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
    print(json.dumps(memory_bridge.DistillationEngine().run(), ensure_ascii=False, indent=2))


def cmd_chat(args):
    a = chat.Assistant()
    print("（输入消息，空行退出；对话带真实时间戳存档）")
    for line in sys.stdin:
        msg = line.strip()
        if not msg:
            break
        storage.add_chat_log("user", msg)            # 真实系统时间戳
        reply, evidence = a.respond(msg)
        storage.add_chat_log("assistant", reply, evidence=evidence)
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


def cmd_recommend(args):
    recs = recommend.recommend(kind=args.kind, query=args.query or "")
    print(f"{len(recs)} 推荐 (kind={args.kind}, 已反幻觉过滤):")
    for r in recs:
        print(f"  - {r.get('item')}  ← {r.get('based_on')}")
        print(f"      {r.get('reason')}")


def cmd_wiki(args):
    if args.action == "build":
        r = memory_bridge.wiki_build()
        print(f"wiki build: {r}（融合记忆系统 wiki 增量编译）")
    elif args.action == "list":
        pages = memory_bridge.wiki_retrieve("", k=100)
        print(f"{len(pages)} wiki pages:")
        for p in pages:
            tags = p.get('tags') or '[]'
            try:
                tags = json.loads(tags) if isinstance(tags, str) else tags
            except Exception:
                tags = []
            print(f"  [{','.join(tags)}] {p['title']}")
    elif args.action == "search":
        pages = memory_bridge.wiki_retrieve(args.q, k=20)
        print(f"{len(pages)} pages for '{args.q}':")
        for p in pages:
            print(f"  == {p['title']} ==")
            print(f"     {p.get('body', '')[:120]}")


def cmd_status(args):
    with storage.connect() as c:
        nseg = c.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
        nev = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        nrm = c.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
    ms = memory_bridge.status_summary()
    print(f"segments:{nseg} events:{nev} reminders:{nrm}")
    print(f"融合记忆系统: wiki_pages:{ms['wiki_pages']} moments:{ms['moments_total']}"
          f"(未归还 {ms['moments_unrecalled']}) L1:{ms['l1_present']}")
    p = memory_bridge.current_profile()
    if any(v for v in p.values()):
        print(f"profile: {json.dumps(p, ensure_ascii=False)[:300]}")


def cmd_memory(args):
    """记忆调试入口（融合记忆系统）：status / recall / scenes / integrate。"""
    if args.action == "status":
        ms = memory_bridge.status_summary()
        print(f"融合记忆系统根目录: {ms['memory_root']}")
        print(f"wiki 实体页: {ms['wiki_pages']} | 时刻: {ms['moments_total']}"
              f"(未归还 {ms['moments_unrecalled']}) | L1: {ms['l1_present']}")
    elif args.action == "recall":
        rr = memory_bridge.hybrid_recall(args.query, k=args.k, strategy=args.strategy)
        print(f"[{rr.strategy}] {len(rr.items)} hits, {rr.elapsed_ms:.0f}ms"
              + (", truncated" if rr.truncated else ""))
        for it in rr.items:
            m = it["memory"]
            print(f"  {it['score']:.4f} [{'+'.join(it['sources'])}] "
                  f"({m.get('kind')}, p{m.get('priority', 50)}) {m.get('content', '')[:80]}")
    elif args.action == "scenes":
        nav = memory_bridge.navigation()
        print(nav or "（暂无时刻层场景导航）")
    elif args.action == "integrate":
        r = memory_bridge.DistillationEngine().run()
        print(f"记忆重建（融合系统）: {r}")


def cmd_token(args):
    """v0.10 token 宽限轮换：rotate / list / revoke。

    轮换后旧 token 在宽限期（默认 7 天）内仍有效——设备不必重新烧录，
    过渡期内重配 NVS/重新编译即可；revoke 可提前吊销。"""
    from . import auth
    from . import config as _cfg
    if args.action == "list":
        info = auth.list_tokens()
        print(f"当前 token: {info['current']}  (鉴权{'开启' if info['auth_enabled'] else '关闭'})")
        if info["retired"]:
            print("宽限期内的退役 token:")
            for e in info["retired"]:
                print(f"  {e['prefix']}...  退役于 {e['retired_at']}  宽限 {e['grace_days']} 天")
        else:
            print("无退役 token")
    elif args.action == "rotate":
        old = _cfg.api_token()
        if not old:
            print("当前未配置 PA_API_TOKEN（鉴权关闭），直接生成新 token 写入 .env")
        new = auth.generate_token()
        if old:
            auth.retire_token(old, grace_days=args.grace_days)
        env_path = _cfg.ROOT / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        replaced = False
        for i, ln in enumerate(lines):
            if ln.strip().startswith("PA_API_TOKEN="):
                lines[i] = f"PA_API_TOKEN={new}"
                replaced = True
        if not replaced:
            lines.append(f"PA_API_TOKEN={new}")
        env_path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        local_cfg = _cfg.ROOT / "scripts" / "xiaozhi-esp32" / "sdkconfig.local"
        if local_cfg.exists():
            txt = local_cfg.read_text(encoding="utf-8")
            if old:
                txt = txt.replace('CONFIG_PC_TOKEN="' + old + '"',
                                  'CONFIG_PC_TOKEN="' + new + '"')
                txt = txt.replace('CONFIG_PA_SERVER_TOKEN="' + old + '"',
                                  'CONFIG_PA_SERVER_TOKEN="' + new + '"')
            local_cfg.write_text(txt, encoding="utf-8")
        print(f"新 token: {new}")
        if old:
            gd = args.grace_days if args.grace_days is not None else _cfg.get("auth.token_grace_days", 7)
            print(f"旧 token 已登记退役，宽限 {gd} 天内设备可继续连接（免烧录过渡）")
        print("后续：1) 重启后端生效  2) 设备在宽限期内随时重配 NVS 或重新编译  "
              "3) 过渡完成可 `cli token revoke --all` 立即失效旧 token")
    elif args.action == "revoke":
        n = auth.revoke_token(prefix=args.prefix or "", all_tokens=args.all)
        print(f"已吊销 {n} 个退役 token")


def cmd_serve(args):
    import uvicorn
    from pathlib import Path
    # 显式配置 root logger：同时写 stderr + 文件 backend.log
    log_path = Path("backend.log")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # 清掉残留 handler（避免 uvicorn 重复加）
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)
    root.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    root.addHandler(sh)
    uvicorn.run("personal_assistant.api:app", host=args.host, port=args.port, reload=False,
                log_level="info")


def cmd_llm(args):
    """查看生效 LLM 配置（5 旋钮 + key 掩码 + 思考原生字段预览）。"""
    from . import llm as _llm
    cfg = _llm.effective_llm_config()
    if cfg.get("backend") == "stub":
        print("backend: stub（智能桩，无网络）")
        return
    print(f"backend:          {cfg['backend']}")
    print(f"model:            {cfg['model']}")
    print(f"base_url(api):    {cfg['base_url']}")
    print(f"api_key(masked):  {cfg['api_key_masked']}")
    print(f"max_tokens:       {cfg['max_tokens']}")
    print(f"thinking_effort:  {cfg['thinking_effort']}")
    print(f"thinking_format:  {cfg['thinking_format']}")
    print(f"native_preview:   {json.dumps(cfg['native_preview'], ensure_ascii=False)}")
    if cfg.get("uses_max_completion_tokens"):
        print("note:             OpenAI 推理模型 → 改发 max_completion_tokens（非 max_tokens）")


def cmd_habits(args):
    from .asr import query_habits
    h = query_habits()
    if not h["daily"]:
        print("(no DuckDB habit data yet — run pipeline first)")
        return
    print(f"=== 习惯分析 ({h['total_days']} days, {h['total_segments']} segments) ===\n")
    print("-- daily_summary --")
    for d in h["daily"][:15]:
        print(f"  {d['day']}  segs={d['segments']}  chars={d['total_chars']}  dur={d['duration_sec']}s  speakers={d['speakers']}")
    print("\n-- speaker_summary --")
    for s in h["speaker"]:
        print(f"  {s['speaker']:12s}  segs={s['segments']}  chars={s['total_chars']}  avg={s['avg_chars']}  days={s['active_days']}")


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
    rc = sub.add_parser("recommend"); rc.add_argument("kind", nargs="?", default="book", choices=["book","movie","action"]); rc.add_argument("query", nargs="?"); rc.set_defaults(func=cmd_recommend)
    w = sub.add_parser("wiki"); w.add_argument("action", choices=["build","list","search"]); w.add_argument("q", nargs="?"); w.set_defaults(func=cmd_wiki)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("habits").set_defaults(func=cmd_habits)
    m = sub.add_parser("memory"); m.add_argument("action", choices=["status","recall","scenes","integrate"]); m.add_argument("query", nargs="?"); m.add_argument("--k", type=int, default=5); m.add_argument("--strategy", default=None); m.set_defaults(func=cmd_memory)
    t = sub.add_parser("token"); t.add_argument("action", choices=["rotate","list","revoke"]); t.add_argument("--grace-days", type=float, default=None); t.add_argument("--prefix", default=""); t.add_argument("--all", action="store_true"); t.set_defaults(func=cmd_token)
    sub.add_parser("llm").set_defaults(func=cmd_llm)
    s = sub.add_parser("serve"); s.add_argument("--host", default="0.0.0.0"); s.add_argument("--port", type=int, default=8004); s.set_defaults(func=cmd_serve)
    sub.add_parser("test").set_defaults(func=cmd_test)

    args = ap.parse_args(argv)
    config.ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
