"""test_no_fabricated_data.py — 反造假回归守卫。

背景（2026-09-04 事故）：stub ASR 对真实硬件录音返回 5 条写死样例、stub LLM 解析
失败时塞一条「（样例）…」、测试转录稿 day1.txt 被当真数据 ingest——三者顺着
segments → events/reminders → UI 一路变成"用户说过的话/用户的日程"，用户实际看到过
「前天去看了那个展览，挺不错。」这种从未说过的内容。

本测试锁死四条不变量：
  1. stub ASR 对非 .txt 音频返回空（绝不返回写死样例）
  2. stub ASR 对 .txt 只返回文件真实行
  3. stub LLM 解析失败返回空（绝不塞样例 segment）
  4. 库里不存在任何已知造假字符串；隔离区 fixture 不在活体 inbox 里
"""
from __future__ import annotations

from pathlib import Path

import pytest

from personal_assistant import config
from personal_assistant.asr import StubTranscriber
from personal_assistant.llm import StubLLM

# 历史上真实入库过的造假字符串（stub 样例 + day1 测试稿）
FABRICATED = [
    "今天和朋友去爬山了，山顶风景很好，很开心。",
    "最近工作有点累，明天打算早点休息。",
    "我觉得应该多读点书，喜欢历史类的。",
    "下周准备去看一部新电影，朋友推荐的。",
    "有点焦虑项目的进度，但慢慢来吧。",
    "前天去看了那个展览，挺不错。",
    "明天下午三点要开项目会。",
    "提醒你明天别忘了带电脑。",
    "今晚的月亮很亮，突然想吃妈妈做的饭。",
    "和朋友散步到河边，聊了很久关于未来的事。",
]


def test_stub_asr_returns_empty_for_audio(tmp_path: Path):
    wav = tmp_path / "real-recording.wav"
    wav.write_bytes(b"RIFF....WAVEfmt ")
    assert StubTranscriber().transcribe(str(wav)) == []


def test_stub_asr_returns_only_real_txt_lines(tmp_path: Path):
    txt = tmp_path / "note.txt"
    txt.write_text("第一行真话\n第二行真话\n", encoding="utf-8")
    segs = StubTranscriber().transcribe(str(txt))
    assert [s.text for s in segs] == ["第一行真话", "第二行真话"]


def test_stub_llm_never_fabricates_segments():
    segs = StubLLM()._extract("没有任何 JSON 块的 prompt")
    assert segs == []


def test_no_fabricated_strings_in_live_db():
    import sqlite3

    db = config.sqlite_path()
    if not Path(db).is_file():
        pytest.skip("PA db 不存在")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = (
            [r[0] for r in c.execute("SELECT text FROM segments")]
            + [r[0] for r in c.execute("SELECT title FROM events")]
            + [r[0] for r in c.execute("SELECT what FROM reminders")]
        )
    finally:
        c.close()
    leaked = [t for t in rows if any(f in (t or "") for f in FABRICATED)]
    assert not leaked, f"库里仍有造假内容: {leaked[:3]}"


def test_quarantined_fixtures_not_in_live_inbox():
    inbox = config.inbox_dir()
    live = [p.name for p in inbox.iterdir() if not p.name.startswith(".")]
    assert "day1.txt" not in live, "day1.txt 测试稿回到了活体 inbox"
    pa_tr = inbox / "pa_transcripts"
    if pa_tr.is_dir():
        names = [p.name for p in pa_tr.iterdir()]
        assert not any("pa_transcript_20260901" in n for n in names), \
            "假转写投递文件回到了活体 inbox"
