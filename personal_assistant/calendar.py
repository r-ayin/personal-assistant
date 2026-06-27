"""calendar.py — 从说话内容自动整理日历：事件抽取 + 时间解析 + 检索。

extract: LLM 抽 {title,when_raw,who,where} → temporal.resolve(确定性) → 缺则 LLM 兜底 → 入库
search: 检索词 → temporal.resolve_range → 缺则 LLM → events_range；附 keyword 兜底
"""
from __future__ import annotations
import json
from datetime import datetime

from . import config, storage, temporal
from .llm import get_llm
from .transcript import Utterance

SYSTEM_EVENTS = """[TASK:EXTRACT_EVENTS]
从用户语音中抽取"有时间的日程/事件"：会议、聚会、出行、约会、截止、已发生的事。
每条字段：title(简述)、when_raw(原话时间表达,务必原样摘录,如'下周三下午三点'/'三月五号'/'前天')、who(涉及人)、where(地点)、segment_id(源片段id,必须等于输入的某条 id)。
只抽确有时间或可推断时间的事；纯情绪/偏好/无时间不抽。返回 JSON 数组。"""

SYSTEM_RESOLVE_DT = """[TASK:RESOLVE_TIME]
把中文时间表达解析成绝对 ISO datetime(基于参考时间)。无法判断时 dt=null。
返回 JSON: {"dt":"2026-06-30T15:00:00","precision":"datetime"} 或 {"dt":null}"""

SYSTEM_RESOLVE_RANGE = """[TASK:RESOLVE_RANGE]
把检索时间词解析成 ISO 时间范围(基于参考时间)。返回 JSON: {"start":"...","end":"..."}"""


def _resolve(expr, reference: datetime, llm=None):
    """确定性优先：日期只用 temporal.resolve（规则+真实系统时间）。
    无法解析返回空串（不信任 LLM 编造日期，由 verify 标记未解析）。"""
    r = temporal.resolve(expr, reference)
    if r:
        return r[0].isoformat(timespec="minutes")
    return ""


def extract(items: list[dict], reference: datetime, llm=None) -> int:
    """items: [{'id','text','speaker'}]（id 须与 segments 表一致，供 verify 溯源）。"""
    llm = llm or get_llm()
    if not items:
        return 0
    body = [{"id": s.get("id", ""), "text": s.get("text", ""), "speaker": s.get("speaker", "")} for s in items]
    user = "Utterances (JSON):\n" + json.dumps(body, ensure_ascii=False) + \
           f"\nReference date(ISO): {reference.isoformat(timespec='minutes')}"
    out = llm.chat_json(SYSTEM_EVENTS, user)
    if not isinstance(out, list):
        return 0
    n = 0
    for ev in out:
        if not isinstance(ev, dict) or not ev.get("title"):
            continue
        dt = _resolve(ev.get("when_raw", ""), reference, llm)
        if not dt:
            continue  # 无法确定性解析→不存（verify 兜底也会删）
        ev["when_dt"] = dt
        ev["source_segment"] = ev.get("segment_id") or ev.get("id", "")  # 溯源到段
        storage.add_event(ev)
        n += 1
    return n


def search(query: str, llm=None) -> list[dict]:
    llm = llm or get_llm()
    now = datetime.now()
    s, e = temporal.resolve_range(query, now)
    if not s:
        out = llm.chat_json(SYSTEM_RESOLVE_RANGE,
                            f"Query: {query}\nReference(ISO): {now.isoformat(timespec='minutes')}")
        if isinstance(out, dict):
            s, e = out.get("start"), out.get("end")
    if s and e:
        return storage.events_range(s, e)
    return storage.events_search(query)
