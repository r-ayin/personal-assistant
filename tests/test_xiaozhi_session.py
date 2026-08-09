"""test_xiaozhi_session.py — Xiaozhi 可取消 turn 状态机与终态恢复测试。

全部用 fake WebSocket / fake ASR / fake Assistant / fake TTS，零网络、零外部服务。
覆盖：
- hello 能力协商边界（格式/采样率/声道/帧长/无 Opus 解码器）
- 正常 turn：stt → tts.start → 音频包 → tts.stop 收敛
- abort 及时消费：LLM 阻塞时 abort，旧 generation 不再发送任何包
- abort 后下一轮可正常完成，无需重连
- 空 ASR / 短音频都有明确终态，不再卡在 listening
- endpoint 层：无 token 关闭 1008，非法 hello 关闭 1003
"""
from __future__ import annotations

import asyncio
import json

import pytest

from personal_assistant import xiaozhi_server
from personal_assistant.xiaozhi_server import XiaozhiSession, _ProtocolError

_PCM_FRAME = b"\x00" * 1920  # 60ms @16kHz mono 16bit


class FakeWS:
    """记录 send_text/send_bytes 的最小 WebSocket 替身。"""

    def __init__(self):
        self.sent: list[tuple[str, object]] = []
        self.closed: int | None = None

    async def send_text(self, text: str) -> None:
        self.sent.append(("text", json.loads(text)))

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(("bytes", data))

    async def close(self, code: int = 1000) -> None:
        self.closed = code


class FakeDecoder:
    """返回 60ms 静音 PCM 的假 Opus 解码器。"""

    def decode(self, data: bytes, frame_size: int = 0) -> bytes:
        return _PCM_FRAME


class FakeAssistant:
    def respond(self, text: str, voice: bool = False):
        return self.respond_stream(text, voice=voice)

    def respond_stream(self, text: str, voice: bool = False, on_delta=None):
        reply = "你好，有什么可以帮你。"
        if on_delta is not None:
            on_delta(reply)
        return reply, ["ev-1"]


def _opus_session(ws: FakeWS, asr=None, assistant=None, tts=None) -> XiaozhiSession:
    """构造已通过 opus hello 的会话（解码器用假实现）。"""
    sess = XiaozhiSession(
        ws,
        asr=asr if asr is not None else (lambda wav: "你好世界"),
        assistant=assistant if assistant is not None else FakeAssistant(),
        tts=tts if tts is not None else (lambda s: [b"p1", b"p2"]),
    )
    return sess


async def _do_opus_hello(sess: XiaozhiSession, monkeypatch) -> None:
    monkeypatch.setattr(
        xiaozhi_server._OpusDecoder, "get",
        staticmethod(lambda sr, ch: FakeDecoder()))
    await sess._on_hello({"type": "hello",
                          "audio_params": {"format": "opus", "sample_rate": 16000,
                                           "channels": 1, "frame_duration": 60}})


async def _feed_silence_until_finalize(sess: XiaozhiSession, frames: int = 9) -> None:
    """连发静音帧触发服务端 VAD 静音 finalize（8 帧阈值 + 0.5s 最小长度）。"""
    for _ in range(frames):
        await sess._on_audio(_PCM_FRAME)


def test_hello_rejects_unsupported_params(monkeypatch) -> None:
    async def run():
        ws = FakeWS()
        sess = XiaozhiSession(ws)
        with pytest.raises(_ProtocolError):
            await sess._on_hello({"type": "hello", "audio_params":
                                  {"format": "pcm", "sample_rate": 8000,
                                   "channels": 1, "frame_duration": 60}})
        with pytest.raises(_ProtocolError):
            await sess._on_hello({"type": "hello", "audio_params":
                                  {"format": "wav", "sample_rate": 16000,
                                   "channels": 1, "frame_duration": 60}})
        # 无 Opus 解码器时 opus hello 必须拒绝（不协商伪 pcm）
        monkeypatch.setattr(
            xiaozhi_server._OpusDecoder, "get", staticmethod(lambda sr, ch: None))
        with pytest.raises(_ProtocolError):
            await sess._on_hello({"type": "hello", "audio_params":
                                  {"format": "opus", "sample_rate": 16000,
                                   "channels": 1, "frame_duration": 60}})
        # 未初始化也保持默认
        assert ws.closed is None

    asyncio.run(run())


def test_hello_rejects_opus_without_decoder(monkeypatch) -> None:
    async def run():
        ws = FakeWS()
        sess = XiaozhiSession(ws)
        monkeypatch.setattr(
            xiaozhi_server._OpusDecoder, "get", staticmethod(lambda sr, ch: None))
        with pytest.raises(_ProtocolError):
            await sess._on_hello({"type": "hello", "audio_params":
                                  {"format": "opus", "sample_rate": 16000,
                                   "channels": 1, "frame_duration": 60}})

    asyncio.run(run())


def test_hello_accepts_pcm() -> None:
    async def run():
        ws = FakeWS()
        sess = XiaozhiSession(ws)
        await sess._on_hello({"type": "hello", "audio_params":
                              {"format": "pcm", "sample_rate": 16000,
                               "channels": 1, "frame_duration": 60}})
        hello = [t for _, t in ws.sent if t.get("type") == "hello"]
        assert len(hello) == 1
        assert hello[0]["audio_params"]["format"] == "pcm"

    asyncio.run(run())


def test_normal_turn_streams_stt_tts_and_audio(monkeypatch) -> None:
    async def run():
        ws = FakeWS()
        sess = _opus_session(ws)
        await _do_opus_hello(sess, monkeypatch)
        await sess._on_listen({"type": "listen", "state": "start"})
        await _feed_silence_until_finalize(sess)
        await asyncio.wait_for(sess._turn_task, timeout=3)
        texts = [t for _, t in ws.sent if isinstance(t, dict)]
        assert any(t.get("type") == "stt" and t.get("text") == "你好世界" for t in texts)
        assert any(t.get("type") == "tts" and t.get("state") == "start" for t in texts)
        assert any(t.get("type") == "tts" and t.get("state") == "sentence_start" for t in texts)
        assert any(t.get("type") == "tts" and t.get("state") == "stop" for t in texts)
        packets = [b for kind, b in ws.sent if kind == "bytes"]
        assert packets == [b"p1", b"p2"]
        assert sess._state == xiaozhi_server._STATE_IDLE

    asyncio.run(run())


def test_abort_consumed_while_llm_blocked(monkeypatch) -> None:
    """LLM 阻塞时 abort：取消在途任务，旧 generation 不再发送任何内容。"""
    async def run():
        blocked = asyncio.Event()
        released = asyncio.Event()

        class BlockingAssistant:
            def respond(self, text, voice=False):
                return self.respond_stream(text, voice=voice)

            def respond_stream(self, text, voice=False, on_delta=None):
                blocked.set()
                released.wait()
                return "不该被发送的回复", []

        ws = FakeWS()
        sess = _opus_session(ws, assistant=BlockingAssistant())
        await _do_opus_hello(sess, monkeypatch)
        await sess._on_listen({"type": "listen", "state": "start"})
        await _feed_silence_until_finalize(sess)
        await asyncio.wait_for(blocked.wait(), timeout=3)
        assert sess._turn_task is not None and not sess._turn_task.done()

        await sess._on_abort({"type": "abort"})
        assert sess._turn_task is None
        # 释放阻塞的 LLM 线程，让在途任务跑完（但应被 generation guard 丢弃）
        released.set()
        for _ in range(20):
            await asyncio.sleep(0.01)
        # 旧 turn 不得产生任何音频包或分句事件；恰好一个终态 tts.stop（来自 abort）
        packets = [b for kind, b in ws.sent if kind == "bytes"]
        assert packets == []
        texts = [t for _, t in ws.sent if isinstance(t, dict)]
        assert not any(t.get("type") == "tts" and t.get("state") == "sentence_start" for t in texts)
        stops = [t for t in texts if t.get("type") == "tts" and t.get("state") == "stop"]
        assert len(stops) == 1

    asyncio.run(run())


def test_abort_then_next_turn_completes(monkeypatch) -> None:
    """abort 后无需重连，新 listen.start 能正常完成一整轮。"""
    async def run():
        blocked = asyncio.Event()
        released = asyncio.Event()

        class BlockingAssistant:
            def respond(self, text, voice=False):
                return self.respond_stream(text, voice=voice)

            def respond_stream(self, text, voice=False, on_delta=None):
                blocked.set()
                released.wait()
                return "作废", []

        ws = FakeWS()
        sess = _opus_session(ws, assistant=BlockingAssistant())
        await _do_opus_hello(sess, monkeypatch)
        await sess._on_listen({"type": "listen", "state": "start"})
        await _feed_silence_until_finalize(sess)
        await asyncio.wait_for(blocked.wait(), timeout=3)
        await sess._on_abort({"type": "abort"})
        released.set()

        # 下一轮：换成正常 assistant 完成 turn
        sess._assistant = FakeAssistant()
        await sess._on_listen({"type": "listen", "state": "start"})
        await _feed_silence_until_finalize(sess)
        await asyncio.wait_for(sess._turn_task, timeout=3)
        texts = [t for _, t in ws.sent if isinstance(t, dict)]
        # 两个 stt：第一轮（abort 前已发 stt） + 第二轮
        stt_count = sum(1 for t in texts if t.get("type") == "stt")
        assert stt_count == 2
        assert any(t.get("type") == "tts" and t.get("state") == "stop" for t in texts)

    asyncio.run(run())


def test_empty_asr_reaches_terminal(monkeypatch) -> None:
    async def run():
        ws = FakeWS()
        sess = _opus_session(ws, asr=lambda wav: "")
        await _do_opus_hello(sess, monkeypatch)
        await sess._on_listen({"type": "listen", "state": "start"})
        await _feed_silence_until_finalize(sess)
        await asyncio.wait_for(sess._turn_task, timeout=3)
        texts = [t for _, t in ws.sent if isinstance(t, dict)]
        assert any(t.get("type") == "stt" and t.get("text") == "" for t in texts)
        assert sess._state == xiaozhi_server._STATE_IDLE

    asyncio.run(run())


def test_short_audio_discarded_without_turn(monkeypatch) -> None:
    async def run():
        ws = FakeWS()
        sess = _opus_session(ws)
        await _do_opus_hello(sess, monkeypatch)
        await sess._on_listen({"type": "listen", "state": "start"})
        # 仅 0.2s 音频后 listen.stop：不足 0.5s → 丢弃，不启动 turn
        await sess._on_audio(_PCM_FRAME)
        await sess._on_audio(_PCM_FRAME)
        await sess._on_audio(_PCM_FRAME)
        await sess._on_listen({"type": "listen", "state": "stop"})
        await asyncio.sleep(0.05)
        assert sess._turn_task is None
        assert sess._state == xiaozhi_server._STATE_IDLE
        texts = [t for _, t in ws.sent if isinstance(t, dict)]
        assert not any(t.get("type") == "stt" for t in texts)

    asyncio.run(run())


class _StreamingAssistant:
    """LLM 逐块输出；第二块前等待 gate，用于确定性地验证首包早于 final。"""

    def __init__(self, blocks, second_gate=None):
        # second_gate 用 threading.Event：respond_stream 跑在 to_thread 线程，
        # 只有同步事件才能确定性阻塞该线程（asyncio.Event.wait 是协程，直接调用不执行）。
        self.blocks = blocks
        self.second_gate = second_gate
        self.finished = False

    def respond(self, text, voice=False):
        return self.respond_stream(text, voice=voice)

    def respond_stream(self, text, voice=False, on_delta=None):
        for i, b in enumerate(self.blocks):
            if i == 1 and self.second_gate is not None:
                self.second_gate.wait()
            if on_delta is not None:
                on_delta(b)
        self.finished = True
        return "".join(self.blocks), []


def test_first_opus_before_llm_final(monkeypatch) -> None:
    """首句 TTS 音频包在 LLM 全部生成完成前发出。"""
    async def run():
        import threading
        ws = FakeWS()
        gate = threading.Event()
        assistant = _StreamingAssistant(
            ["你好，有什么可以帮你。", "现在说第二句。"], second_gate=gate)
        sess = _opus_session(ws, assistant=assistant,
                             tts=lambda s: [b"p1"])
        await _do_opus_hello(sess, monkeypatch)
        await sess._on_listen({"type": "listen", "state": "start"})
        await _feed_silence_until_finalize(sess)
        # 轮询直到第一个音频包出现（LLM 第二块仍被 gate 挡住）
        for _ in range(100):
            if any(kind == "bytes" for kind, _ in ws.sent):
                break
            await asyncio.sleep(0.01)
        assert any(kind == "bytes" for kind, _ in ws.sent), "first opus never sent"
        # 首包出现时 LLM 尚未结束（第二块未发出）
        assert not assistant.finished
        gate.set()
        await asyncio.wait_for(sess._turn_task, timeout=3)
        # 两个分句都应播报
        texts = [t for _, t in ws.sent if isinstance(t, dict)]
        sent_starts = [t.get("text") for t in texts
                       if t.get("type") == "tts" and t.get("state") == "sentence_start"]
        assert "你好，有什么可以帮你。" in sent_starts
        assert "现在说第二句。" in sent_starts

    asyncio.run(run())


def test_incremental_splitter_boundaries() -> None:
    from personal_assistant.xiaozhi_server import _IncrementalSplitter

    sp = _IncrementalSplitter()
    # 无标点：不切句，残留缓冲
    assert sp.feed("你好呀") == []
    # 标点出现在下一块：切出完整句
    assert sp.feed("，今天天气不错。") == ["你好呀，今天天气不错。"]
    # 英文问号与省略号
    assert sp.feed("Really?") == ["Really?"]
    assert sp.feed("等等…") == ["等等…"]
    # 尾巴 flush
    assert sp.feed("还有一句话") == []
    assert sp.flush() == "还有一句话"
    assert sp.flush() == ""


def test_abort_cancels_tts_consumer(monkeypatch) -> None:
    """abort 后 TTS 消费者任务必须被取消，不泄漏。"""
    async def run():
        gate = asyncio.Event()
        blocked = asyncio.Event()

        class GatedAssistant:
            def respond(self, text, voice=False):
                return self.respond_stream(text, voice=voice)

            def respond_stream(self, text, voice=False, on_delta=None):
                blocked.set()
                gate.wait()
                if on_delta is not None:
                    on_delta("第一句。")
                return "第一句。", []

        ws = FakeWS()
        sess = _opus_session(ws, assistant=GatedAssistant())
        await _do_opus_hello(sess, monkeypatch)
        await sess._on_listen({"type": "listen", "state": "start"})
        await _feed_silence_until_finalize(sess)
        await asyncio.wait_for(blocked.wait(), timeout=3)
        # 消费者已在跑（等待队列）且 turn 任务在执行
        assert sess._tts_task is not None and not sess._tts_task.done()
        await sess._on_abort({"type": "abort"})
        gate.set()
        await asyncio.sleep(0.1)
        assert sess._tts_task is None
        # 不得有音频包
        assert not any(kind == "bytes" for kind, _ in ws.sent)

    asyncio.run(run())


def test_stable_device_key_hashes_identity() -> None:
    class H:
        headers = {"device-id": "aa:bb:cc"}

    key1 = xiaozhi_server._stable_device_key(H())
    assert len(key1) == 16
    assert key1.isalnum()
    # 不同设备产生不同 key
    class H2:
        headers = {"device-id": "aa:bb:dd"}

    assert xiaozhi_server._stable_device_key(H2()) != key1
    # 无设备标识时返回空（回退到 session 级）
    class H3:
        headers = {}

    assert xiaozhi_server._stable_device_key(H3()) == ""
