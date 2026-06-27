"""verify.py — 反幻觉脚本复查。每个 LLM 抽取环节后跑：

- 事件/提醒：用 temporal 确定性重解 when_dt 覆盖（权威，真实时间）；无法确定性给出真实日期→删；
  校验 when_raw 落地源转录（逐字 或 日期等价：源文本任一时间表达解析出的日期同天）；
  source_segment 段不存在→删；不落地→删。
- 记忆：evidence/segment_id 段存在 + content bigram 可溯源；否则删。
保证：存储日历时间=确定性规则算出（非 LLM 编造），每条结论可回溯到真实转录。
"""
from __future__ import annotations
import re
from datetime import datetime

from . import storage, temporal


def _norm(s: str) -> str:
    return re.sub(r"[，。！？!?,\s、:：（）()\"'`]", "", s or "")


def _seg_ref(seg_id: str):
    src = storage.segment_get(seg_id) if seg_id else None
    if not src:
        return None, None
    try:
        ref = datetime.fromisoformat(src["created_at"]) if src.get("created_at") else datetime.now()
    except Exception:
        ref = datetime.now()
    return src, ref


def _when_grounded(when_raw: str, src_text: str, ref: datetime, det_dt) -> bool:
    """when_raw 落地判定：逐字命中 或 源文本有时间表达解析到同一天（容忍数字归一）。"""
    if not when_raw:
        return False
    if _norm(when_raw) in _norm(src_text):
        return True
    if det_dt is None:
        return False
    src_dates = {d.date() for d in temporal.find_exprs(src_text or "", ref)}
    return det_dt.date() in src_dates


def correct_events() -> tuple[int, int]:
    kept = deleted = 0
    for ev in storage.all_events():
        src, ref = _seg_ref(ev.get("source_segment", ""))
        if not src:
            storage.delete_event(ev["id"])
            deleted += 1
            continue
        det = temporal.resolve(ev.get("when_raw", ""), ref)
        if not det:
            storage.delete_event(ev["id"])   # 无真实日期→不留
            deleted += 1
            continue
        storage.set_event_when(ev["id"], det[0].isoformat(timespec="minutes"))
        if not _when_grounded(ev.get("when_raw", ""), src.get("text", ""), ref, det[0]):
            storage.delete_event(ev["id"])
            deleted += 1
        else:
            kept += 1
    return kept, deleted


def correct_reminders() -> tuple[int, int]:
    kept = deleted = 0
    from . import reminders as _r
    for rm in storage.reminders_all():
        src, ref = _seg_ref(rm.get("source_segment", ""))
        if not src:
            storage.delete_reminder(rm["id"])
            deleted += 1
            continue
        det_str = _r._resolve(rm.get("when_raw", ""), ref, None, rm.get("recurring", ""))
        if not det_str:
            storage.delete_reminder(rm["id"])
            deleted += 1
            continue
        storage.set_reminder_when(rm["id"], det_str)
        det = temporal.resolve(rm.get("when_raw", ""), ref)  # 取日期做等价溯源
        det_dt = det[0] if det else None
        if not _when_grounded(rm.get("when_raw", ""), src.get("text", ""), ref, det_dt):
            storage.delete_reminder(rm["id"])
            deleted += 1
        else:
            kept += 1
    return kept, deleted


def _seg_id_from_evidence(ev: str) -> str:
    m = re.search(r"segment:([^\s)]+)", ev or "")
    return m.group(1) if m else ""


def verify_memories() -> tuple[int, int]:
    kept = deleted = 0
    for m in storage.memories_all():
        seg_id = m.get("segment_id") or _seg_id_from_evidence(m.get("evidence", ""))
        src = storage.segment_get(seg_id) if seg_id else None
        if not src:
            storage.delete_memory(m["id"])
            deleted += 1
            continue
        content = m.get("content", "") or ""
        src_norm = _norm(src.get("text", ""))
        bigrams = {content[i:i + 2] for i in range(len(content) - 1)}
        grounded = any(bg and bg in src_norm for bg in bigrams)
        if not grounded:
            storage.delete_memory(m["id"])
            deleted += 1
        else:
            kept += 1
    return kept, deleted


def run_all() -> dict:
    ek, ed = correct_events()
    rk, rd = correct_reminders()
    mk, md = verify_memories()
    rep = {"events_kept": ek, "events_deleted": ed,
           "reminders_kept": rk, "reminders_deleted": rd,
           "memories_kept": mk, "memories_deleted": md}
    print(f"[verify] {rep}")
    return rep


def assert_no_hallucination() -> None:
    """断言：所有存储事件 when_raw 落地源文本、when_dt 确定性可复算。"""
    for ev in storage.all_events():
        src = storage.segment_get(ev.get("source_segment", ""))
        assert src is not None, f"event {ev['id']} 无源段（幻觉）"
        ref = datetime.fromisoformat(src["created_at"]) if src.get("created_at") else datetime.now()
        det = temporal.resolve(ev["when_raw"], ref)
        assert det is not None, f"event {ev['id']} when_dt 无法确定性复算"
        assert ev["when_dt"] == det[0].isoformat(timespec="minutes"), \
            f"event {ev['id']} when_dt={ev['when_dt']} ≠ 确定性 {det[0].isoformat(timespec='minutes')}"
        assert _when_grounded(ev["when_raw"], src["text"], ref, det[0]), \
            f"event {ev['id']} when_raw 不落地源文本"
