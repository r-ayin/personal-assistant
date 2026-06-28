"""Tests for temporal.py — deterministic Chinese time-expression parser."""
from datetime import datetime, date, time, timedelta
import pytest
from personal_assistant.temporal import (
    _cn_to_int, _parse_hm, resolve, resolve_range, find_exprs, _safe_date,
)

REF = datetime(2026, 6, 28, 14, 30, 0)


class TestCnToInt:
    def test_arabic(self):
        assert _cn_to_int("5") == 5
        assert _cn_to_int("12") == 12

    def test_single_cn(self):
        assert _cn_to_int("三") == 3
        assert _cn_to_int("两") == 2
        assert _cn_to_int("零") == 0

    def test_shi_alone(self):
        assert _cn_to_int("十") == 10

    def test_shi_with_ones(self):
        assert _cn_to_int("十二") == 12
        assert _cn_to_int("十九") == 19

    def test_tens_with_shi(self):
        assert _cn_to_int("二十") == 20
        assert _cn_to_int("三十") == 30

    def test_tens_ones(self):
        assert _cn_to_int("二十三") == 23
        assert _cn_to_int("三十一") == 31

    def test_whitespace(self):
        assert _cn_to_int("  5  ") == 5
        assert _cn_to_int(" 三 ") == 3


class TestParseHm:
    def test_hour_minute(self):
        assert _parse_hm("三点四十五分") == (3, 45)

    def test_hour_only(self):
        assert _parse_hm("九点") == (9, 0)

    def test_half(self):
        assert _parse_hm("三点半") == (3, 30)

    def test_pm_adjustment(self):
        assert _parse_hm("下午三点") == (15, 0)
        assert _parse_hm("晚上八点") == (20, 0)

    def test_am_no_adjustment(self):
        assert _parse_hm("上午九点") == (9, 0)

    def test_midnight_凌晨(self):
        assert _parse_hm("凌晨12点") == (0, 0)

    def test_no_match(self):
        assert _parse_hm("没有时间") is None

    def test_colon_format(self):
        assert _parse_hm("14:30") == (14, 30)
        assert _parse_hm("9:05") == (9, 5)


class TestResolve:
    def test_empty(self):
        assert resolve("", REF) is None
        assert resolve(None, REF) is None

    def test_absolute_date(self):
        dt, prec = resolve("七月十五号", REF)
        assert dt.date() == date(2026, 7, 15)
        assert prec == "date"

    def test_absolute_date_arabic(self):
        dt, prec = resolve("8月1日", REF)
        assert dt.date() == date(2026, 8, 1)

    def test_absolute_past_wraps_year(self):
        dt, _ = resolve("三月五号", REF)
        assert dt.date() == date(2027, 3, 5)

    def test_absolute_date_with_time(self):
        dt, prec = resolve("七月十五号下午三点", REF)
        assert dt == datetime(2026, 7, 15, 15, 0)
        assert prec == "datetime"

    def test_today(self):
        dt, prec = resolve("今天", REF)
        assert dt.date() == REF.date()
        assert prec == "date"

    def test_tomorrow(self):
        dt, _ = resolve("明天", REF)
        assert dt.date() == REF.date() + timedelta(days=1)

    def test_yesterday(self):
        dt, _ = resolve("昨天", REF)
        assert dt.date() == REF.date() - timedelta(days=1)

    def test_day_after_tomorrow(self):
        dt, _ = resolve("后天", REF)
        assert dt.date() == REF.date() + timedelta(days=2)

    def test_relative_with_time(self):
        dt, prec = resolve("明天下午三点", REF)
        assert dt == datetime(2026, 6, 29, 15, 0)
        assert prec == "datetime"

    def test_this_week(self):
        dt, _ = resolve("这周五", REF)
        # REF is Sunday (wd=6); "这周五" wraps forward if past → next Fri
        target_wd = 4
        delta = target_wd - REF.weekday()
        if delta < 0:
            delta += 7
        assert dt.date() == REF.date() + timedelta(days=delta)

    def test_next_week(self):
        dt, _ = resolve("下周一", REF)
        ref_mon = REF.date() - timedelta(days=REF.weekday())
        assert dt.date() == ref_mon + timedelta(days=7)

    def test_last_week(self):
        dt, _ = resolve("上周三", REF)
        ref_mon = REF.date() - timedelta(days=REF.weekday())
        expected = ref_mon - timedelta(days=7) + timedelta(days=2)
        assert dt.date() == expected

    def test_days_ago(self):
        dt, prec = resolve("三天前", REF)
        assert dt.date() == REF.date() - timedelta(days=3)
        assert prec == "date"

    def test_days_later(self):
        dt, _ = resolve("五天后", REF)
        assert dt.date() == REF.date() + timedelta(days=5)

    def test_bare_time(self):
        dt, prec = resolve("下午两点半", REF)
        assert dt == datetime(2026, 6, 28, 14, 30)
        assert prec == "datetime"

    def test_unrecognized(self):
        assert resolve("某个时间", REF) is None


class TestResolveRange:
    def test_this_week(self):
        s, e = resolve_range("本周", REF)
        mon = REF.date() - timedelta(days=REF.weekday())
        assert s == datetime.combine(mon, time(0)).isoformat(timespec="seconds")
        assert e == datetime.combine(mon + timedelta(days=7), time(0)).isoformat(timespec="seconds")

    def test_last_week(self):
        s, e = resolve_range("上周", REF)
        mon = REF.date() - timedelta(days=REF.weekday() + 7)
        assert s == datetime.combine(mon, time(0)).isoformat(timespec="seconds")

    def test_next_week(self):
        s, e = resolve_range("下周", REF)
        mon = REF.date() - timedelta(days=REF.weekday()) + timedelta(days=7)
        assert s == datetime.combine(mon, time(0)).isoformat(timespec="seconds")

    def test_this_month(self):
        s, e = resolve_range("本月", REF)
        assert s == datetime(2026, 6, 1).isoformat(timespec="seconds")
        assert e == datetime(2026, 7, 1).isoformat(timespec="seconds")

    def test_last_month(self):
        s, e = resolve_range("上月", REF)
        assert s == datetime(2026, 5, 1).isoformat(timespec="seconds")
        assert e == datetime(2026, 6, 1).isoformat(timespec="seconds")

    def test_recent_days(self):
        s, e = resolve_range("最近七天", REF)
        assert s == datetime.combine(REF.date() - timedelta(days=7), time(0)).isoformat(timespec="seconds")

    def test_relative_day(self):
        s, e = resolve_range("今天", REF)
        assert s == datetime.combine(REF.date(), time(0)).isoformat(timespec="seconds")
        assert e == datetime.combine(REF.date() + timedelta(days=1), time(0)).isoformat(timespec="seconds")

    def test_empty(self):
        assert resolve_range("", REF) == (None, None)
        assert resolve_range(None, REF) == (None, None)


class TestFindExprs:
    def test_multiple(self):
        text = "明天和后天都有事，三月五号也是"
        results = find_exprs(text, REF)
        assert len(results) >= 3

    def test_empty(self):
        assert find_exprs("", REF) == []
        assert find_exprs(None, REF) == []

    def test_week_expr(self):
        results = find_exprs("下周一开会", REF)
        assert len(results) == 1


class TestSafeDate:
    def test_valid(self):
        assert _safe_date(2026, 6, 28) == date(2026, 6, 28)

    def test_invalid_day(self):
        assert _safe_date(2026, 2, 30) is None

    def test_invalid_month(self):
        assert _safe_date(2026, 13, 1) is None
        assert _safe_date(2026, 0, 1) is None

    def test_leap_year(self):
        assert _safe_date(2024, 2, 29) == date(2024, 2, 29)
        assert _safe_date(2025, 2, 29) is None
