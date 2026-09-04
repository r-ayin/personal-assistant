"""test_e2e.py — 端到端冒烟（默认 stub 后端，零网络零模型）。

记忆后端已接入「个人助手」融合记忆系统（memory_bridge）：
  - 记忆写入：ingest 把用户转写片段投递到融合系统 inbox/（测试中重定向到本地临时目录，避免污染真实记忆库）
  - 记忆读取：current_profile / hybrid_recall / wiki_retrieve 只读消费融合系统产物
本地保留链路：转录解析→说话人归属→日历事件→提醒→对话→主动→反幻觉→推荐。
cli: python3 -m personal_assistant.cli test
"""
from __future__ import annotations
from pathlib import Path

from personal_assistant import (config, storage, ingest, memory_bridge, proactive,
                                chat, calendar, reminders, speaker, verify, recommend)

# A 话多且多用"我"→ TextDiarizer 识别为 user；B→他人
SAMPLE = """A: 明天下午三点要开项目会。
A: 我每天早上都跑步。
B: 下周三你得交报告吧？
A: 对，下周三交。
A: 三月五号我还和朋友吃饭。
A: 前天去看了那个展览，挺不错。
B: 提醒你明天别忘了带电脑。
"""


def _reset():
    import sqlite3
    for p in [config.sqlite_path(), config.duckdb_path(), config.persona_path(),
              config.ROOT / "data" / "logs" / "interventions.log",
              config.ROOT / "data" / "logs" / "reminders.log"]:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        except PermissionError:
            if p.suffix == ".db":
                try:
                    with sqlite3.connect(str(p)) as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        for row in cur.fetchall():
                            cur.execute(f"DELETE FROM {row[0]}")
                        conn.commit()
                except Exception:
                    pass
    inbox = config.inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    for f in inbox.iterdir():
        if f.is_file() and not f.name.startswith("."):
            try:
                f.unlink()
            except PermissionError:
                pass
    (inbox / "day1.txt").write_text(SAMPLE, encoding="utf-8")
    # 重定向记忆桥接的投递目录到本地测试区，避免写入真实融合记忆系统
    fused_inbox = config.ROOT / "data" / "e2e_fused_inbox"
    memory_bridge._INBOX_DIR = fused_inbox
    fused_inbox.mkdir(parents=True, exist_ok=True)


def run() -> bool:
    print(f"=== e2e  llm={config.get('llm.backend')} asr={config.get('asr.backend')} "
          f"embedder={config.get('embedder.backend')} speaker={config.get('speaker.backend')} ===")
    _reset()
    fails = []

    # 1. ingest（转录解析→说话人归属→入库→[记忆投递融合系统]→事件→提醒）
    r = ingest.scan_inbox()
    print(f"[1] ingest: {r}")
    if r.get("segments", 0) < 5:
        fails.append(f"segments {r.get('segments')} < 5")
    if r.get("events", 0) < 3:
        fails.append(f"events {r.get('events')} < 3")
    if r.get("reminders", 0) < 2:
        fails.append(f"reminders {r.get('reminders')} < 2")
    if r.get("memories", 0) < 1:
        fails.append(f"memories(投递融合系统) {r.get('memories')} < 1")

    # 2. 说话人归属：user 已注册
    sps = storage.speakers_all()
    names = [s["name"] for s in sps]
    print(f"[2] speakers: {names}")
    if "user" not in names:
        fails.append("user speaker not identified")

    # 3. 用户画像（记忆桥接：persona_versions 基底 + 时刻层 + 反馈；只读无副作用）
    prof = memory_bridge.current_profile()
    print(f"[3] profile dims: {sum(1 for v in prof.values() if v)}")

    # 4. 日历检索：明天应有事件
    tom = calendar.search("明天")
    print(f"[4] calendar '明天': {len(tom)} events")
    if not tom:
        fails.append("calendar search '明天' empty")

    # 5. 提醒列表
    rms = storage.reminders_all()
    print(f"[5] reminders: {len(rms)}")
    if not rms:
        fails.append("no reminders stored")

    # 6. 对话（真实时间戳存档）
    msg = "我明天有什么安排？"
    storage.add_chat_log("user", msg)
    reply, _evidence = chat.Assistant().respond(msg)
    storage.add_chat_log("assistant", reply)
    print(f"[6] chat reply: {reply[:80]}")
    if not reply or not reply.strip():
        fails.append("empty chat reply")

    # 7. 主动触发（由融合系统时刻层驱动；无时刻时为空属正常）
    fired = proactive.ProactiveEngine().check()
    print(f"[7] proactive fired: {len(fired)}")

    # 8. 提醒到期检查不崩
    reminders.ReminderScheduler().check_due()
    print("[8] reminder scheduler: ok")

    # 9. 反幻觉断言：事件 when_dt 确定性可复算、when_raw 落地源文本
    try:
        verify.assert_no_hallucination()
        print("[9] verify: no-hallucination 断言通过")
    except AssertionError as e:
        fails.append(f"hallucination: {e}")

    # 10. 对话真实时间戳
    logs = storage.chat_logs()
    print(f"[10] chat_log: {len(logs)} 条 (latest ts={logs[0]['created_at'] if logs else 'none'})")
    if not logs or not logs[0]["created_at"]:
        fails.append("chat_log 无真实时间戳")
    from datetime import datetime
    try:
        ts = datetime.fromisoformat(logs[0]["created_at"])
        if abs((datetime.now(ts.tzinfo) - ts).total_seconds()) > 60:
            fails.append("chat_log 时间戳非系统实时")
    except Exception as e:
        fails.append(f"chat_log 时间戳解析失败: {e}")

    # 11. 推荐（联网动态搜索 + 反幻觉；离线或 stub 后端时容忍为空）
    recs = recommend.recommend(kind="book", query="历史")
    print(f"[11] recommend book: {len(recs)} 条（联网搜索）")
    if not recs:
        if config.get("llm.backend") == "stub":
            print("[11] recommend: 跳过（stub 后端无法将搜索结果落地为推荐，反幻觉拦截属预期）")
        else:
            from personal_assistant.web import get_searcher
            try:
                net_results = get_searcher().search("book 推荐 历史", n=3)
            except Exception:
                net_results = []
            if net_results:
                fails.append("recommend 空（有联网搜索结果但 LLM 未选出任何项）")
            else:
                print("[11] recommend: 跳过（当前网络受限，无搜索结果）")
    for it in recs:
        if not it.get("item") or not it.get("based_on"):
            fails.append(f"recommend 项缺 item/based_on: {it}")

    # 12. 记忆桥接只读消费（融合记忆系统）：召回 + wiki 检索 + 状态
    try:
        rr = memory_bridge.hybrid_recall("跑步")
        print(f"[12] bridge recall: {len(rr.items)} hits, {rr.elapsed_ms:.0f}ms")
        pages = memory_bridge.wiki_retrieve("", k=5)
        st = memory_bridge.status_summary()
        print(f"[12] bridge wiki_pages={st['wiki_pages']} moments={st['moments_total']} "
              f"l1={st['l1_present']}")
    except Exception as e:
        fails.append(f"memory_bridge 只读消费异常: {e}")

    print(f"=== e2e {'PASS' if not fails else 'FAIL'}  fails={fails} ===")
    return not fails


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
