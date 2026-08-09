"""test_llm_config.py — LLM 思考程度映射 + 可配 max_tokens + 运行态覆盖（零网络）。

monkeypatch llm._post_json 捕获请求体，断言各 provider/档位字段与官方文档调研一致。
cli: `python3 -m personal_assistant.cli test`（test_e2e 调 run()）或直接 pytest。
"""
from __future__ import annotations
import json

from personal_assistant import llm, config


# ── 捕获 _post_json，返回伪响应 ─────────────────────────────────
CAPTURED: list[dict] = []


def _fake_post(url, headers, body, timeout=60.0):
    CAPTURED.append({"url": url, "headers": headers, "body": body})
    if "/chat/completions" in url:
        return {"choices": [{"message": {"content": "ok"}}]}
    return {"content": [{"type": "text", "text": "ok"}]}


def _new_openai(fmt, effort, max_tokens=4096):
    return llm.OpenAICompatLLM("http://x/v1", "k", "m", max_tokens, effort, fmt)


def _new_anthropic(effort, max_tokens=4096):
    return llm.AnthropicProxyLLM("http://x", "k", "m", max_tokens, effort, "anthropic")


def _chat_and_body(client):
    CAPTURED.clear()
    client.chat("sys", "hi")
    assert CAPTURED, "no HTTP call captured"
    return CAPTURED[-1]["body"]


def test_openai_reasoning_uses_max_completion_tokens():
    llm._post_json = _fake_post
    b = _chat_and_body(_new_openai("openai", "high"))
    assert b["reasoning_effort"] == "high"
    assert "max_completion_tokens" in b and "max_tokens" not in b
    assert b["temperature"] == 1


def test_openai_off_omits_reasoning():
    llm._post_json = _fake_post
    b = _chat_and_body(_new_openai("openai", "off"))
    assert "reasoning_effort" not in b
    assert "max_tokens" in b and "max_completion_tokens" not in b


def test_glm_openai_compat_only_on_off():
    llm._post_json = _fake_post
    b = _chat_and_body(_new_openai("glm", "中"))
    assert b["thinking"] == {"type": "enabled"}      # 无 budget，塌缩为开
    assert "budget_tokens" not in b["thinking"]
    b2 = _chat_and_body(_new_openai("glm", "off"))
    assert b2["thinking"] == {"type": "disabled"}    # GLM 默认开，off 须显式 disable


def test_qwen_thinking_budget():
    llm._post_json = _fake_post
    b = _chat_and_body(_new_openai("qwen", "低", max_tokens=16384))
    assert b["enable_thinking"] is True
    assert b["thinking_budget"] == 4096
    b2 = _chat_and_body(_new_openai("qwen", "off", max_tokens=16384))
    assert b2["enable_thinking"] is False


def test_anthropic_budget_within_max_tokens():
    llm._post_json = _fake_post
    b = _chat_and_body(_new_anthropic("高", max_tokens=8192))
    assert b["thinking"]["type"] == "enabled"
    bud = b["thinking"]["budget_tokens"]
    assert bud >= 1024 and bud < 8192              # min 1024, < max_tokens
    assert bud == 7168                             # min(24576, 8192-1024)


def test_anthropic_off_omits_thinking():
    llm._post_json = _fake_post
    b = _chat_and_body(_new_anthropic("off"))
    assert "thinking" not in b


def test_chinese_effort_normalized():
    llm._post_json = _fake_post
    b = _chat_and_body(_new_openai("openai", "高"))
    assert b["reasoning_effort"] == "high"          # 中文 高 → high


def test_set_override_affects_get_llm():
    config.clear_override()
    config.set_override("llm.backend", "openai_compat")
    config.set_override("llm.openai_compat.thinking_effort", "中")
    config.set_override("llm.openai_compat.max_tokens", 2048)
    c = llm.get_llm()
    assert isinstance(c, llm.OpenAICompatLLM)
    assert c.thinking_effort == "中"
    assert c.max_tokens == 2048
    config.clear_override()


def test_effective_config_masks_key():
    config.clear_override()
    config.set_override("llm.backend", "openai_compat")
    config.set_override("llm.openai_compat.api_key", "sk-abcdef12345678")
    eff = llm.effective_llm_config()
    assert eff["api_key_masked"].startswith("sk-a") and eff["api_key_masked"].endswith("5678")
    assert "sk-abcdef12345678" not in json.dumps(eff, ensure_ascii=False)
    config.clear_override()


def test_budget_clamps_below_max_tokens():
    # max_tokens 小时，高 档 budget 被 clamp 到 max_tokens-1024
    llm._post_json = _fake_post
    b = _chat_and_body(_new_anthropic("高", max_tokens=4096))
    assert b["thinking"]["budget_tokens"] == 3072   # min(24576, 4096-1024)


# ── 详细结果、messages 与 provider usage 归一化 ───────────────────
def test_llm_result_cache_hit_rate_is_serializable():
    result = llm.LLMResult(text="ok", cache_hit_tokens=30, cache_miss_tokens=10)
    assert result.cache_hit_rate == 0.75
    encoded = json.loads(json.dumps(result.to_dict()))
    assert encoded["cache_hit_rate"] == 0.75
    assert encoded["text"] == "ok"


def test_openai_detailed_sends_complete_messages_array():
    captured = []

    def fake_post(url, headers, body, timeout=60.0):
        captured.append(body)
        return {"id": "req-openai", "model": "served-model",
                "choices": [{"message": {"content": "answer"}}]}

    llm._post_json = fake_post
    client = _new_openai("openai", "off")
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer-1"},
        {"role": "user", "content": "next"},
    ]
    result = client.chat_messages_detailed("sys", messages, temperature=0.6)

    assert captured[0]["messages"] == [
        {"role": "system", "content": "sys"}, *messages,
    ]
    assert captured[0]["temperature"] == 0.6
    assert result.text == "answer"
    assert result.request_id == "req-openai"
    assert result.model == "served-model"
    assert result.provider == "openai_compat"
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_deepseek_usage_normalizes_explicit_cache_hit_and_miss():
    def fake_post(url, headers, body, timeout=60.0):
        return {
            "id": "req-deepseek",
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_cache_hit_tokens": 75,
                "prompt_cache_miss_tokens": 25,
            },
        }

    llm._post_json = fake_post
    result = llm.OpenAICompatLLM(
        "http://x/v1", "k", "deepseek-chat", provider="deepseek"
    ).chat_detailed("sys", "hello")

    assert result.provider == "deepseek"
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.total_tokens == 120
    assert result.cache_hit_tokens == 75
    assert result.cache_miss_tokens == 25
    assert result.cache_hit_rate == 0.75
    assert result.cache_read_input_tokens is None
    assert result.cache_write_input_tokens is None


def test_openai_usage_normalizes_cached_tokens_without_estimating_miss():
    def fake_post(url, headers, body, timeout=60.0):
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 8,
                "prompt_tokens_details": {"cached_tokens": 60},
            },
        }

    llm._post_json = fake_post
    result = _new_openai("openai", "off").chat_detailed("sys", "hello")

    assert result.input_tokens == 80
    assert result.output_tokens == 8
    assert result.total_tokens is None
    assert result.cache_hit_tokens == 60
    assert result.cache_miss_tokens is None
    assert result.cache_hit_rate is None


def test_anthropic_detailed_sends_messages_and_normalizes_cache_usage():
    captured = []

    def fake_post(url, headers, body, timeout=60.0):
        captured.append(body)
        return {
            "id": "msg-1",
            "model": "claude-served",
            "content": [{"type": "text", "text": "hello"},
                        {"type": "thinking", "thinking": "hidden"},
                        {"type": "text", "text": " world"}],
            "usage": {
                "input_tokens": 40,
                "output_tokens": 7,
                "cache_read_input_tokens": 30,
                "cache_creation_input_tokens": 10,
            },
        }

    llm._post_json = fake_post
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "next"},
    ]
    result = _new_anthropic("off").chat_messages_detailed("sys", messages)

    assert captured[0]["system"] == "sys"
    assert captured[0]["messages"] == messages
    assert result.text == "hello world"
    assert result.request_id == "msg-1"
    assert result.model == "claude-served"
    assert result.input_tokens == 40
    assert result.output_tokens == 7
    assert result.total_tokens is None
    assert result.cache_read_input_tokens == 30
    assert result.cache_write_input_tokens == 10
    assert result.cache_hit_tokens is None
    assert result.cache_miss_tokens is None
    assert result.cache_hit_rate is None


def test_unknown_usage_fields_remain_none():
    def fake_post(url, headers, body, timeout=60.0):
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}

    llm._post_json = fake_post
    result = _new_openai("openai", "off").chat_detailed("sys", "hello")
    assert result.input_tokens is None
    assert result.output_tokens is None
    assert result.total_tokens is None
    assert result.cache_hit_tokens is None
    assert result.cache_miss_tokens is None


def test_old_chat_contract_delegates_to_detailed_text():
    def fake_post(url, headers, body, timeout=60.0):
        return {"choices": [{"message": {"content": "legacy string"}}]}

    llm._post_json = fake_post
    result = _new_openai("openai", "off").chat("sys", "hello")
    assert result == "legacy string"
    assert isinstance(result, str)


def test_base_detailed_fallback_and_message_history_capability():
    class LegacyLLM(llm.LLMClient):
        def chat(self, system, user, temperature=0.3):
            return f"{system}|{user}|{temperature}"

    result = LegacyLLM().chat_detailed("sys", "hello", temperature=0.4)
    assert result.text == "sys|hello|0.4"
    assert result.provider is None
    assert result.input_tokens is None
    assert result.latency_ms is not None

    assert llm.LLMClient.supports_message_history is False
    assert llm.StubLLM.supports_message_history is False
    assert llm.MiniCPMOLLM.supports_message_history is False
    assert llm.OpenAICompatLLM.supports_message_history is True
    assert llm.AnthropicProxyLLM.supports_message_history is True


def test_stub_and_minicpm_detailed_fallbacks_use_legacy_chat():
    stub = llm.StubLLM()
    stub_result = stub.chat_detailed("sys", "hello")
    assert isinstance(stub_result, llm.LLMResult)
    assert stub_result.text == stub.chat("sys", "hello")
    assert stub_result.input_tokens is None

    calls = []

    def requester(method, payload):
        calls.append((method, payload))
        return {"text": "local answer"}

    minicpm = llm.MiniCPMOLLM(requester=requester)
    minicpm_result = minicpm.chat_detailed("sys", "hello")
    assert minicpm_result.text == "local answer"
    assert minicpm_result.provider is None
    assert calls[0][0] == "ask"


def run() -> bool:
    """函数式入口，供 cli test 或直接调用。"""
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  ✅ {t.__name__}")
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
        except Exception as e:
            print(f"  💥 {t.__name__}: {type(e).__name__}: {e}")
    print(f"llm_config: {passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
