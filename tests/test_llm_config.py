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
