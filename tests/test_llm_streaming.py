"""test_llm_streaming.py — OpenAI 兼容 SSE 流式增量与 usage 归一化测试。

不联网：monkeypatch _stream_sse 注入假 SSE 块；覆盖：
- 增量文本逐块回调 on_delta
- 完整文本拼接 + usage 归一化
- 无 usage 时字段保持 None（不伪造）
- 基类默认实现退化为单块回调
"""
from __future__ import annotations

import pytest

from personal_assistant import llm


class _FakeClient(llm.LLMClient):
    supports_message_history = True

    def __init__(self, text="hello"):
        self._text = text

    def chat(self, system, user, temperature=0.3):
        return self._text

    def chat_messages_detailed(self, system, messages, temperature=0.3):
        return llm.LLMResult(text=self._text, provider="fake", model="m")


def test_base_stream_falls_back_to_single_block() -> None:
    client = _FakeClient("hello world")
    deltas: list[str] = []
    result = client.chat_messages_stream(
        "sys", [{"role": "user", "content": "hi"}], on_delta=deltas.append)
    assert result.text == "hello world"
    assert deltas == ["hello world"]


def test_openai_stream_calls_delta_and_merges_usage(monkeypatch) -> None:
    chunks = [
        {"choices": [{"delta": {"content": "你"}}]},
        {"choices": [{"delta": {"content": "好"}}]},
        {"choices": []},
        {"usage": {"prompt_tokens": 10, "completion_tokens": 5,
                   "total_tokens": 15, "prompt_cache_hit_tokens": 7,
                   "prompt_cache_miss_tokens": 3}},
    ]
    monkeypatch.setattr(llm, "_stream_sse", lambda *a, **k: iter(chunks))
    client = llm.OpenAICompatLLM(
        base_url="https://fake.invalid", api_key="k", model="m",
        thinking_effort="off", thinking_format="glm", provider="deepseek")
    deltas: list[str] = []
    result = client.chat_messages_stream(
        "sys", [{"role": "user", "content": "hi"}], on_delta=deltas.append)
    assert result.text == "你好"
    assert deltas == ["你", "好"]
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.cache_hit_tokens == 7
    assert result.cache_miss_tokens == 3
    assert result.cache_hit_rate == 7 / 10


def test_openai_stream_without_usage_keeps_unknown(monkeypatch) -> None:
    chunks = [{"choices": [{"delta": {"content": "hi"}}]}, {"choices": []}]
    monkeypatch.setattr(llm, "_stream_sse", lambda *a, **k: iter(chunks))
    client = llm.OpenAICompatLLM(
        base_url="https://fake.invalid", api_key="k", model="m",
        thinking_effort="off", thinking_format="glm", provider="deepseek")
    result = client.chat_messages_stream("sys", [{"role": "user", "content": "hi"}])
    assert result.text == "hi"
    assert result.input_tokens is None
    assert result.output_tokens is None


def test_openai_stream_retries_without_stream_options(monkeypatch) -> None:
    """不支持 stream_options 的代理：首次 HTTPError 后去 options 重试成功。"""
    import urllib.error

    calls: list[dict] = []

    def fake_sse(url, headers, body):
        calls.append(body)
        if "stream_options" in body:
            raise urllib.error.HTTPError(url, 400, "bad request", None, None)
        return iter([{"choices": [{"delta": {"content": "retry-ok"}}]}, {"choices": []}])

    monkeypatch.setattr(llm, "_stream_sse", fake_sse)
    client = llm.OpenAICompatLLM(
        base_url="https://fake.invalid", api_key="k", model="m",
        thinking_effort="off", thinking_format="glm", provider="deepseek")
    result = client.chat_messages_stream("sys", [{"role": "user", "content": "hi"}])
    assert result.text == "retry-ok"
    assert len(calls) == 2
    assert "stream_options" not in calls[1]


def test_sse_parser_skips_non_data_lines() -> None:
    """_stream_sse 只解析 data: 行并跳过 [DONE]。"""
    raw = (
        b"event: message\n"
        b'data: {"choices":[{"delta":{"content":"a"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    class FakeResp:
        def __iter__(self):
            return iter([raw])

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=90):
        return FakeResp()

    monkeypatch_setup = pytest.MonkeyPatch()
    monkeypatch_setup.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    try:
        out = list(llm._stream_sse(
            "https://fake.invalid/chat/completions", {}, {"model": "m"}))
    finally:
        monkeypatch_setup.undo()
    assert out == [{"choices": [{"delta": {"content": "a"}}]}]
