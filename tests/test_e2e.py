"""test_e2e.py — 端到端冒烟（默认 stub 后端，零网络零模型）。

样例：多说话人转录(A/B) + 时间表达 + 提醒意图。
跑通：ingest(转录解析→说话人归属→入库)→记忆→蒸馏→日历事件→提醒→对话→主动→检索。
cli: `python3 -m personal_assistant.cli test`  或设 PA_LLM_BACKEND=anthropic_proxy 用真 GLM。
"""
from __future__ import annotations
from pathlib import Path

from personal_assistant import (config, storage, ingest, memory, distill, proactive,
                                chat, calendar, reminders, speaker, verify)

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
    for p in [config.sqlite_path(), config.duckdb_path(), config.persona_path(),
              config.ROOT / "data" / "logs" / "interventions.log",
              config.ROOT / "data" / "logs" / "reminders.log"]:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    inbox = config.inbox_dir()
    inbox.mkdir(parents=True, exist_ok=True)
    for f in inbox.iterdir():
        if f.is_file() and not f.name.startswith("."):
            f.unlink()
    (inbox / "day1.txt").write_text(SAMPLE, encoding="utf-8")


def run() -> bool:
    print(f"=== e2e  llm={config.get('llm.backend')} asr={config.get('asr.backend')} "
          f"embedder={config.get('embedder.backend')} speaker={config.get('speaker.backend')} ===")
    _reset()
    fails = []

    # 1. ingest（转录解析→说话人归属→入库→记忆→事件→提醒）
    r = ingest.scan_inbox()
    print(f"[1] ingest: {r}")
    if r.get("segments", 0) < 5:
        fails.append(f"segments {r.get('segments')} < 5")
    if r.get("events", 0) < 3:
        fails.append(f"events {r.get('events')} < 3")
    if r.get("reminders", 0) < 2:
        fails.append(f"reminders {r.get('reminders')} < 2")
    if r.get("memories", 0) < 3:
        fails.append(f"memories {r.get('memories')} < 3")

    # 2. 说话人归属：user 已注册
    sps = storage.speakers_all()
    names = [s["name"] for s in sps]
    print(f"[2] speakers: {names}")
    if "user" not in names:
        fails.append("user speaker not identified")

    # 3. 蒸馏
    dr = distill.DistillationEngine().run()
    print(f"[3] distill: {dr}")
    if dr.get("skipped"):
        fails.append(f"distill skipped: {dr.get('reason')}")
    if not config.persona_path().exists():
        fails.append("persona/profile.json not written")

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
    reply = chat.Assistant().respond(msg)
    storage.add_chat_log("assistant", reply)
    print(f"[6] chat reply: {reply[:80]}")
    if not reply or not reply.strip():
        fails.append("empty chat reply")

    # 7. 主动触发
    fired = proactive.ProactiveEngine().check()
    print(f"[7] proactive fired: {len(fired)}")

    # 8. 提醒到期检查不崩
    reminders.ReminderScheduler().check_due()
    print("[8] reminder scheduler: ok")

    # 9. 反幻觉断言：所有事件 when_dt 确定性可复算、when_raw 落地源文本
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
    # 时间戳须是合法 ISO 且为当下附近（真实）
    from datetime import datetime
    try:
        ts = datetime.fromisoformat(logs[0]["created_at"])
        if abs((datetime.now(ts.tzinfo) - ts).total_seconds()) > 60:
            fails.append("chat_log 时间戳非系统实时")
    except Exception as e:
        fails.append(f"chat_log 时间戳解析失败: {e}")

    if fails:
        print("\n❌ FAIL:")
        for f in fails:
            print("  -", f)
        return False
    print("\n✅ PASS — 转录→说话人→记忆→蒸馏→日历→提醒→对话 全链路跑通")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
