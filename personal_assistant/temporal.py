"""temporal.py — 中文时间表达解析（确定性规则优先，缺则 LLM 兜底）。

支持中文数字（三月五号/十二号/二十三号/下午三点/三点半）+ 阿拉伯数字。
resolve(expr, reference) -> (datetime, precision) precision∈{'date','datetime'} 或 None
resolve_range(query, reference) -> (start_iso, end_iso)
"""
from __future__ import annotations
import re
from datetime import datetime, date, time, timedelta

WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
CN = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
      "六": 6, "七": 7, "八": 8, "九": 9}
NUM = r"[0-9一二两三四五六七八九十]+"

REL_DAY = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3,
           "昨天": -1, "昨日": -1, "前天": -2, "大前天": -3}


def _cn_to_int(s: str) -> int:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in CN:
        return CN[s]
    if "十" in s:  # 十 / 十X / X十 / X十Y
        parts = s.split("十")
        tens = CN[parts[0]] if parts[0] else 1
        ones = CN[parts[1]] if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return 0


def _parse_hm(s: str, ref_hour_default: int = 9):
    m = re.search(rf"({NUM})\s*[点时]\s*半|({NUM})\s*[点时：:]\s*({NUM})?\s*分?", s)
    if not m:
        return None
    if m.group(1):  # X点半 — must be tried before X点(Y分)? to avoid greedy swallow
        h = _cn_to_int(m.group(1))
        mm = 30
    else:
        h = _cn_to_int(m.group(2))
        mm = _cn_to_int(m.group(3)) if m.group(3) else 0
    if re.search(r"下午|傍晚|晚上|晚间|pm|PM", s) and h < 12:
        h += 12
    if re.search(r"凌晨|深夜", s) and h == 12:
        h = 0
    return h, mm


def resolve(expr: str, reference: datetime):
    if not expr:
        return None
    s = expr.strip()
    ref = reference

    # 绝对：X月X[日号][ + 时间]（X 可中文数字）
    m = re.search(rf"({NUM})\s*月\s*({NUM})\s*[日号]", s)
    if m:
        mon, day = _cn_to_int(m.group(1)), _cn_to_int(m.group(2))
        year = ref.year
        d = _safe_date(year, mon, day)
        if d and d < ref.date():  # 今年已过 → 明年
            d = _safe_date(year + 1, mon, day)
        if not d:
            d = _safe_date(year, mon, day) or _safe_date(year + 1, mon, day)
        if not d:
            return None
        hm = _parse_hm(s)
        if hm:
            return (datetime.combine(d, time(hm[0], hm[1])), "datetime")
        return (datetime.combine(d, time(9, 0)), "date")

    # 相对天数
    for kw, off in REL_DAY.items():
        if kw in s:
            d = ref.date() + timedelta(days=off)
            hm = _parse_hm(s)
            if hm:
                return (datetime.combine(d, time(hm[0], hm[1])), "datetime")
            return (datetime.combine(d, time(9, 0)), "date")

    # 上/这/下周X（周X 保持中文）
    m = re.search(r"(上|这|本|下)\s*周\s*([一二三四五六日天])", s)
    if m:
        pref, wd = m.group(1), m.group(2)
        target_wd = WEEKDAY[wd]
        cur_wd = ref.weekday()
        if pref == "上":
            delta = target_wd - cur_wd - 7
        elif pref in ("这", "本"):
            delta = target_wd - cur_wd
            if delta < 0:
                delta += 7
        else:
            delta = target_wd - cur_wd + 7
        d = ref.date() + timedelta(days=delta)
        hm = _parse_hm(s)
        if hm:
            return (datetime.combine(d, time(hm[0], hm[1])), "datetime")
        return (datetime.combine(d, time(9, 0)), "date")

    # X天前/后
    m = re.search(rf"({NUM})\s*天[前后]", s)
    if m:
        n = _cn_to_int(m.group(1))
        off = -n if "前" in s else n
        return (datetime.combine(ref.date() + timedelta(days=off), time(9, 0)), "date")

    # 仅时间（今天某点）
    hm = _parse_hm(s)
    if hm and re.search(r"[点时半]|上午|下午|晚上|早上|凌晨", s):
        return (datetime.combine(ref.date(), time(hm[0], hm[1])), "datetime")

    return None


def resolve_range(query: str, reference: datetime):
    s = (query or "").strip()
    ref = reference

    if "本周" in s or "这周" in s:
        start = ref.date() - timedelta(days=ref.weekday())
        return (_dt(start), _dt(start + timedelta(days=7)))
    if "上周" in s:
        start = ref.date() - timedelta(days=ref.weekday() + 7)
        return (_dt(start), _dt(start + timedelta(days=7)))
    if "下周" in s:
        start = ref.date() - timedelta(days=ref.weekday()) + timedelta(days=7)
        return (_dt(start), _dt(start + timedelta(days=7)))
    if "本月" in s:
        start = ref.date().replace(day=1)
        return (_dt(start), _dt(_safe_date(start.year, start.month + 1, 1) or _safe_date(start.year + 1, 1, 1)))
    if "上月" in s:
        first_this = ref.date().replace(day=1)
        start = (_safe_date(first_this.year, first_this.month - 1, 1)
                 or _safe_date(first_this.year - 1, 12, 1))
        return (_dt(start), _dt(first_this))
    m = re.search(rf"最近\s*({NUM})\s*天", s)
    if m:
        n = _cn_to_int(m.group(1))
        return (_dt(ref.date() - timedelta(days=n)), _dt(ref.date() + timedelta(days=1)))
    for kw, off in REL_DAY.items():
        if kw in s:
            d = ref.date() + timedelta(days=off)
            return (_dt(d), _dt(d + timedelta(days=1)))
    return (None, None)


def find_exprs(text: str, reference: datetime) -> list[datetime]:
    """从文本里确定性找出所有时间表达并解析，供 verify 做日期等价溯源。"""
    if not text:
        return []
    out = []
    for kw in REL_DAY:
        if kw in text:
            r = resolve(kw, reference)
            if r:
                out.append(r[0])
    for m in re.finditer(r"(上|这|本|下)\s*周\s*([一二三四五六日天])", text):
        r = resolve(m.group(0), reference)
        if r:
            out.append(r[0])
    for m in re.finditer(rf"({NUM})\s*月\s*({NUM})\s*[日号]", text):
        r = resolve(m.group(0), reference)
        if r:
            out.append(r[0])
    for m in re.finditer(rf"({NUM})\s*天[前后]", text):
        r = resolve(m.group(0), reference)
        if r:
            out.append(r[0])
    return out


def _dt(d) -> str:
    return datetime.combine(d, time(0, 0)).isoformat(timespec="seconds")


def _safe_date(year, month, day) -> date | None:
    try:
        if month < 1 or month > 12:
            return None
        return date(year, month, day)
    except Exception:
        return None
