"""test_e2e.py — 端到端冒烟（默认 stub 后端，零网络零模型）。

样例：多说话人转录(A/B) + 时间表达 + 提醒意图。
跑通：ingest(转录解析→说话人归属→入库)→记忆→蒸馏→日历事件→提醒→对话→主动→检索。
cli: `python3 -m personal_assistant.cli test`  或设 PA_LLM_BACKEND=anthropic_proxy 用真 GLM。
"""
from __future__ import annotations
from pathlib import Path

from personal_assistant import (config, storage, ingest, memory, distill, proactive,
                                chat, calendar, reminders, speaker, verify, recommend, wiki)

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
    import time
    for p in [config.sqlite_path(), config.duckdb_path(), config.persona_path(),
              config.ROOT / "data" / "logs" / "interventions.log",
              config.ROOT / "data" / "logs" / "reminders.log"]:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        except PermissionError:
            # Windows 下 db 可能被其他进程占用：尝试清空表数据而非删文件
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
    reply, _evidence = chat.Assistant().respond(msg)
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

    # 11. 推荐（联网动态搜索真实结果 + 反幻觉）
    recs = recommend.recommend(kind="book", query="历史")
    print(f"[11] recommend book: {len(recs)} 条（联网搜索）")
    if not recs:
        # 离线/网络受限时允许为空，但要求不是幻觉导致
        from personal_assistant.web import get_searcher
        try:
            net_results = get_searcher().search("book 推荐 历史", n=3)
        except Exception:
            net_results = []
        if net_results:
            fails.append("recommend 空（有联网搜索结果但 LLM 未选出任何项）")
        else:
            print("[11] recommend: 跳过（当前网络受限，无搜索结果）")
    for r in recs:
        if not r.get("item") or not r.get("based_on"):
            fails.append(f"recommend 项缺 item/based_on: {r}")

    # 12. 个人 wiki（增量编译 + 反幻觉）
    r12 = wiki.build()
    print(f"[12] wiki build: {r12}")
    if r12.get("new_pages", 0) + r12.get("extended", 0) < 1:
        fails.append("wiki 未编译出页面")
    else:
        try:
            wiki.assert_grounded()
        except AssertionError as e:
            fails.append(f"wiki 幻觉: {e}")
    # 12b. 增量：灌第 2 份转录（含新内容）→ 再 build → wiki 增长（扩展或新页）
    pages_before = len(storage.all_wiki_pages())
    (config.inbox_dir() / "day2.txt").write_text(
        "最近在学吉他，想组个乐队。\n下周要去听一场爵士乐演出，很期待。\n我喜欢爵士乐的即兴。",
        encoding="utf-8")
    ingest.scan_inbox()
    r12b = wiki.build()
    print(f"[12b] 2nd build: {r12b}, pages {pages_before}→{len(storage.all_wiki_pages())}")
    if r12b.get("new_pages", 0) + r12b.get("extended", 0) < 1:
        fails.append("wiki 增量未处理新记忆（应扩展/新页）")
    try:
        wiki.assert_grounded()
    except AssertionError as e:
        fails.append(f"wiki(2nd) 幻觉: {e}")

    # 13. v0.10 记忆架构链路（L1 去重 → L2 场景 → L3 narrative → 混合召回）
    from personal_assistant import scenes, recall
    nmem_before = storage.count_memories()
    # 13a. L1 去重：重复灌 day1 → 记忆数不增（skip/merge 生效）
    (config.inbox_dir() / "day1.txt").write_text(SAMPLE, encoding="utf-8")
    try:
        (config.inbox_dir() / "day2.txt").unlink()
    except FileNotFoundError:
        pass
    with storage.connect() as c:
        c.execute("DELETE FROM ingested_files WHERE source_file='day1.txt'")
        c.commit()
    r13 = ingest.scan_inbox()
    print(f"[13a] re-ingest dedup: {r13.get('memories_dedup')}")
    if storage.count_memories() > nmem_before:
        fails.append(f"L1 去重失效：重复灌入记忆增加 {nmem_before}→{storage.count_memories()}")
    # 13b. L2 场景：整合后 scenes 非空、溯源真实
    sr = scenes.integrate()
    print(f"[13b] scenes integrate: {sr}")
    all_scenes = storage.scenes_all()
    if not all_scenes:
        fails.append("L2 场景层为空")
    mem_ids_valid = {m["id"] for m in storage.memories_all()}
    for s in all_scenes:
        if not all(i in mem_ids_valid for i in s["source_mem_ids"]):
            fails.append(f"场景 {s['name']} 溯源失效")
            break
    # 13c. L3 narrative：distill 后叙事档案非空 ≤2000 字符
    dr13 = distill.DistillationEngine().run()
    narr = storage.latest_narrative()
    print(f"[13c] narrative: {len(narr)} 字符 (distill={dr13.get('version', dr13.get('reason'))})")
    if not dr13.get("skipped") and not narr:
        fails.append("L3 narrative 为空")
    if len(narr) > 2000:
        fails.append(f"narrative 超长 {len(narr)}")
    # 13d. 混合召回：结构完整、可命中
    rr = recall.hybrid_recall("跑步 爵士乐", k=5)
    print(f"[13d] hybrid recall: {len(rr.items)} hits, {rr.elapsed_ms:.0f}ms, strategy={rr.strategy}")
    if not rr.items:
        fails.append("hybrid_recall 无结果")
    for it in rr.items:
        if not set(it.keys()) >= {"memory", "score", "sources"}:
            fails.append("recall item 缺结构")
            break
    # 13e. chat 引用召回记忆：evidence 含记忆 id
    _reply13, ev13 = chat.Assistant().respond("我平时有什么爱好？")
    mem_ev = [e for e in ev13 if not e.startswith("segment") and ":" not in e]
    print(f"[13e] chat evidence: {len(ev13)} 条")
    if not ev13:
        fails.append("chat evidence 为空（未引用记忆/感知）")

    def _safe_print(text: str):
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", errors="replace").decode("ascii"))

    if fails:
        _safe_print("\n❌ FAIL:")
        for f in fails:
            _safe_print(f"  - {f}")
        return False
    _safe_print("\n✅ PASS — 转录→说话人→记忆→蒸馏→日历→提醒→对话 全链路跑通")
    return True


def test_stub_e2e():
    assert run(), "e2e pipeline failed — see stdout for details"


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
