"""reminders.py — 定时任务/日程提醒：抽取意图+目标时间 → 到点触发。

extract: LLM 抽 {what,when_raw,recurring} → temporal.resolve → 入库
ReminderScheduler: 轮询 due 提醒 → 通知 → 标记 fired(循环类重排下次)
"""
from __future__ import annotations
import json
import threading
import time as _time
from datetime import datetime, timedelta

from . import config, storage, temporal
from .llm import get_llm
from .transcript import Utterance

SYSTEM_REMINDERS = """[TASK:EXTRACT_REMINDERS]
从用户语音中抽取"需要到点提醒的意图"：'提醒我...'/'明天要交...'/'下周三开会'/'每天早上跑步'/'周五前完成'。
每条字段：what(提醒内容)、when_raw(原话时间表达,务必原样摘录)、recurring(daily|weekly|monthly|空)、segment_id(源片段id,必须等于输入的某条 id)。
只抽有明显时间或可推断时间的待办/日程。返回 JSON 数组。"""


def _resolve(expr, reference, llm=None, recurring=""):
    """确定性优先：日期只用 temporal.resolve，不信任 LLM 编造日期。"""
    if recurring:  # 循环类：算下一次
        return _next_occurrence(expr, reference, recurring)
    r = temporal.resolve(expr, reference)
    if r:
        return r[0].isoformat(timespec="minutes")
    return ""


def calendar_resolve_prompt():
    """已弃用 LLM 日期兜底（反幻觉）。保留占位避免引用断裂。"""
    return "[deprecated] 日期解析走确定性 temporal.resolve"


def _next_occurrence(expr, reference, recurring):
    """循环提醒：粗略算下次发生。每天→明天同时辰;每周→下周同日;每月→下月同日。"""
    r = temporal.resolve(expr, reference)
    base = r[0] if r else reference
    if recurring == "daily":
        nxt = base + timedelta(days=1)
    elif recurring == "weekly":
        nxt = base + timedelta(days=7)
    elif recurring == "monthly":
        nxt = _add_month(base)
    else:
        nxt = base + timedelta(days=1)
    return nxt.isoformat(timespec="minutes")


def _add_month(dt):
    m = dt.month % 12 + 1
    y = dt.year + (1 if dt.month == 12 else 0)
    from .temporal import _safe_date
    d = _safe_date(y, m, min(dt.day, 28))
    from datetime import datetime as _dt
    return _dt.combine(d, dt.time()) if d else dt + timedelta(days=30)


def extract(items: list[dict], reference: datetime, llm=None) -> int:
    """items: [{'id','text'}]（id 须与 segments 表一致）。"""
    llm = llm or get_llm()
    if not items:
        return 0
    body = [{"id": s.get("id", ""), "text": s.get("text", "")} for s in items]
    user = "Utterances (JSON):\n" + json.dumps(body, ensure_ascii=False) + \
           f"\nReference(ISO): {reference.isoformat(timespec='minutes')}"
    out = llm.chat_json(SYSTEM_REMINDERS, user)
    if not isinstance(out, list):
        return 0
    n = 0
    for rm in out:
        if not isinstance(rm, dict) or not rm.get("what"):
            continue
        rec = rm.get("recurring", "") or ""
        dt = _resolve(rm.get("when_raw", ""), reference, llm, rec)
        if not dt:
            continue
        rm["when_dt"] = dt
        rm["recurring"] = rec
        rm["source_segment"] = rm.get("segment_id") or rm.get("id", "")
        storage.add_reminder(rm)
        n += 1
    return n


class ReminderScheduler:
    def __init__(self, notifier=None):
        self.notifier = notifier or _Notify()
        self._stop = False

    def check_due(self) -> int:
        now = datetime.now().isoformat(timespec="minutes")
        due = storage.reminders_due(now)
        for r in due:
            self.notifier.notify(f"⏰ 提醒：{r['what']}（{r.get('when_raw','')}）", r["id"])
            if r.get("recurring"):
                # 重排下一次
                nxt = _next_occurrence(r.get("when_raw", ""), datetime.now(), r["recurring"])
                storage.add_reminder({**r, "when_dt": nxt, "id": r["id"] + "-next"})
            storage.mark_reminder_fired(r["id"])
        return len(due)

    def run_loop(self, poll_seconds: float = 30.0):
        while not self._stop:
            try:
                self.check_due()
            except Exception as e:
                print(f"[reminders] check error: {e}")
            _time.sleep(poll_seconds)

    def stop(self):
        self._stop = True


# ── 模块级快捷方式 ────────────────────────────────────────────
_SCHEDULER: ReminderScheduler | None = None


def check_due() -> list[dict]:
    """模块级快捷调用（供 api.py import），返回已触发提醒列表。"""
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = ReminderScheduler()
    now = datetime.now().isoformat(timespec="minutes")
    due = storage.reminders_due(now)
    fired = []
    for r in due:
        _SCHEDULER.notifier.notify(f"⏰ 提醒：{r['what']}（{r.get('when_raw','')}）", r["id"])
        if r.get("recurring"):
            nxt = _next_occurrence(r.get("when_raw", ""), datetime.now(), r["recurring"])
            storage.add_reminder({**r, "when_dt": nxt, "id": r["id"] + "-next"})
        storage.mark_reminder_fired(r["id"])
        fired.append(r)
    return fired


class _Notify:
    def notify(self, message, evidence):
        line = f"[{storage.now_iso()}] {message}  ← {evidence}"
        print(f"\n🔔 {line}")
        log = config.ROOT / "data" / "logs" / "reminders.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
