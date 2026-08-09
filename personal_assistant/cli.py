"""cli.py — 命令行入口：pipeline / distill / chat / proactive / calendar / reminders / speakers / status / serve / test。"""
from __future__ import annotations
import argparse
import json
import logging
import sys
import os
import urllib.error
import urllib.request

from . import (config, storage, asr, memory, distill, proactive, chat,
               ingest, calendar, reminders, speaker, verify, recommend, wiki)


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
        r = wiki.build()
        print(f"wiki build: {r}（new_pages+extended，增量；反幻觉:source_ids 真实+body 落地源）")
    elif args.action == "list":
        pages = wiki.retrieve()
        print(f"{len(pages)} wiki pages:")
        for p in pages:
            print(f"  [{','.join(p.get('tags', []))}] {p['title']}  (src:{len(p.get('source_ids', []))})")
    elif args.action == "search":
        pages = wiki.retrieve(tag=args.q, query=args.q)
        print(f"{len(pages)} pages for '{args.q}':")
        for p in pages:
            print(f"  == {p['title']} ==")
            print(f"     {p.get('body', '')[:120]}")


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


def cmd_memory(args):
    """v0.10 记忆架构调试入口：status / recall / scenes。"""
    from . import recall as recall_mod, scenes
    if args.action == "status":
        with storage.connect() as c:
            nmem = c.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            nsc = c.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
            nseg = c.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
        _p, _s, pv = storage.latest_persona()
        narr = storage.latest_narrative()
        print(f"L0 segments:{nseg} | L1 memories:{nmem} | L2 scenes:{nsc} | "
              f"L3 persona_v:{pv} narrative:{len(narr)}字符")
        print(f"场景待整合记忆: {scenes.pending_count()}")
    elif args.action == "recall":
        rr = recall_mod.hybrid_recall(args.query, k=args.k, strategy=args.strategy)
        print(f"[{rr.strategy}] {len(rr.items)} hits, {rr.elapsed_ms:.0f}ms"
              + (", truncated" if rr.truncated else ""))
        for it in rr.items:
            m = it["memory"]
            print(f"  {it['score']:.4f} [{'+'.join(it['sources'])}] "
                  f"({m.get('kind')}, p{m.get('priority', 50)}) {m.get('content', '')[:80]}")
    elif args.action == "scenes":
        for s in storage.scenes_all():
            print(f"  heat:{s['heat']:<4} {s['name']} — {s['summary'][:50]} "
                  f"(src:{len(s['source_mem_ids'])}, {s['updated_at'][:19]})")
    elif args.action == "integrate":
        r = scenes.integrate()
        print(f"scene integrate: {r}")


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
    from . import desktop_connection
    from pathlib import Path
    # 显式配置 root logger：同时写 stderr + 文件 backend.log
    # 文件 handler 避免 PowerShell 管道缓冲 stderr 导致 pa.xiaozhi 日志不可见
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
    desktop_connection.publish_for_server(
        host=args.host,
        port=args.port,
        token=config.api_token(),
    )
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


def cmd_local_model(args):
    from . import local_omni
    from .omni_service import get_omni_service
    if args.action == "download":
        endpoint = local_omni.download_models()
        print(json.dumps({"downloaded": True, "endpoint": endpoint,
                          "model_root": str(local_omni.resolve_model_root()),
                          "bytes": local_omni.MODEL_TOTAL_BYTES},
                         ensure_ascii=False, indent=2))
        return
    model_root = local_omni.resolve_model_root()
    worker_path = local_omni.resolve_worker_path()
    print(json.dumps({
        **get_omni_service().status(),
        "worker_path": str(worker_path),
        "worker_exists": worker_path.is_file(),
        "model_root": str(model_root),
        "model_files_valid": local_omni.model_files_are_valid(model_root, verify_hashes=False),
        "model_marker_valid": local_omni.model_marker_is_valid(model_root),
        "model_revision": local_omni.MODEL_REVISION,
        "model_bytes": local_omni.MODEL_TOTAL_BYTES,
    }, ensure_ascii=False, indent=2))


def cmd_perception(args):
    """通过已运行的 PA API 启停本地多模态感知。"""
    base_url = (args.base_url or os.environ.get("PA_API_URL")
                or "http://127.0.0.1:8004").rstrip("/")
    token = args.token or config.api_token()
    if not token:
        raise SystemExit("perception control requires --token or PA_API_TOKEN")
    request = urllib.request.Request(
        f"{base_url}/perception/{args.action}",
        data=b"",
        headers={"Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("detail", str(exc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = str(exc)
        raise SystemExit(f"PA API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"PA API unavailable at {base_url}: {exc.reason}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


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
    lm = sub.add_parser("local-model")
    lm.add_argument("action", nargs="?", default="status",
                    choices=["status", "download"])
    lm.set_defaults(func=cmd_local_model)
    perception = sub.add_parser("perception")
    perception.add_argument("action", choices=["start", "stop"])
    perception.add_argument("--base-url")
    perception.add_argument("--token")
    perception.set_defaults(func=cmd_perception)
    sub.add_parser("test").set_defaults(func=cmd_test)

    args = ap.parse_args(argv)
    config.ensure_dirs()
    args.func(args)


if __name__ == "__main__":
    main()
