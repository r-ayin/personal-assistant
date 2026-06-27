"""transcript.py — 解析设备产出的转录文本（多种格式）→ Utterance 列表。

支持：纯文本每行一段 / 带时间戳 [start-end] 或 MM:SS / 带说话人标签 A: / SRT。
不调 LLM、纯解析；时间戳缺失则按行递增给假时间。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Utterance:
    text: str
    start: float = 0.0
    end: float = 0.0
    speaker: str = ""        # 设备原标签（若有）
    source: str = ""         # 文件名
    line: int = 0


def _parse_ts(s: str) -> float | None:
    """MM:SS 或 HH:MM:SS → 秒。"""
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d+))?", s)
    if not m:
        return None
    h = int(m.group(1)) if m.group(1) else 0
    return h * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def parse(path: str) -> list[Utterance]:
    p = Path(path)
    name = p.name
    text = p.read_text(encoding="utf-8")
    suffix = p.suffix.lower()
    if suffix == ".srt":
        return _parse_srt(text, name)
    return _parse_lines(text, name)


def _parse_lines(text: str, name: str) -> list[Utterance]:
    out, t = [], 0.0
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        spk = ""
        m = re.match(r"^([^:：]{1,12})[：:]\s*(.*)$", line)
        if m and not re.match(r"^\d", m.group(1)):
            spk = m.group(1).strip()
            line = m.group(2).strip()
        # 前置时间戳 [00:12-00:18] 或 00:12
        start = end = 0.0
        ts = re.match(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)[\-~到](\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)$", line)
        if ts:
            start = _parse_ts(ts.group(1)) or 0.0
            end = _parse_ts(ts.group(2)) or start
            line = ts.group(3).strip()
        else:
            ts2 = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.*)$", line)
            if ts2:
                start = _parse_ts(ts2.group(1)) or 0.0
                end = start + 5.0
                line = ts2.group(2).strip()
        if not line:
            continue
        if end <= start:
            end = start + max(2.0, len(line) * 0.4)
        if start == 0.0 and not ts and not ts2:
            start, end = t, t + max(2.0, len(line) * 0.4)
            t = end + 0.5
        else:
            t = end + 0.5
        out.append(Utterance(line, start, end, spk, name, i))
    return out


def _parse_srt(text: str, name: str) -> list[Utterance]:
    out = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for i, blk in enumerate(blocks, 1):
        lines = [l.strip() for l in blk.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d{2}:\d{2}:\d{2}[.,]\d+)\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d+)", lines[1])
        if not m:
            continue
        start = _parse_ts(m.group(1).replace(",", ".")) or 0.0
        end = _parse_ts(m.group(2).replace(",", ".")) or start
        body = " ".join(lines[2:])
        out.append(Utterance(body, start, end, "", name, i))
    return out
