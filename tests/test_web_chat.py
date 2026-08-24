"""test_web_chat.py — 对话实时联网搜索：auto 触发 / off 禁用 / 超时降级 / 注入格式。

不真联网：monkeypatch web.get_searcher 注入假搜索器。
"""
from __future__ import annotations

import json

from personal_assistant import chat, web


class _FakeSearcher:
    def __init__(self, results):
        self.results = results

    def search(self, query: str, n: int = 5):
        return self.results


def _mk_assistant(monkeypatch, results=None):
    monkeypatch.setattr(chat.distill, "current_profile", lambda: {"preferences": ["安静"]})
    monkeypatch.setattr(chat.storage, "latest_narrative", lambda: "")
    monkeypatch.setattr(chat.scenes, "navigation", lambda: "")
    if results is not None:
        monkeypatch.setattr(web, "get_searcher", lambda: _FakeSearcher(results))
    return chat.Assistant(llm=object(), embedder=object(), history=chat.ConversationHistory())


def test_auto_search_triggers_on_realtime_keyword(monkeypatch) -> None:
    chat._WEB_CACHE.clear()
    hits = []
    calls = []

    class Spy:
        def search(self, query, n=5):
            calls.append(query)
            return [{"title": "今日天气", "url": "https://x/1", "snippet": "晴 24℃"}]

    monkeypatch.setattr(chat.config, "get", lambda k, d=None: "auto" if k == "chat.web_search" else d)
    monkeypatch.setattr(chat, "_WEB_CACHE", {})
    monkeypatch.setattr(web, "get_searcher", lambda: Spy())
    assistant = _mk_assistant(monkeypatch)

    out = assistant._web_search_results("今天天气怎么样")
    assert calls, "实时性关键词应触发联网"
    assert out and out[0]["title"] == "今日天气"
    # 缓存：二次调用不再触发
    assistant._web_search_results("今天天气怎么样")
    assert len(calls) == 1


def test_off_mode_never_searches(monkeypatch) -> None:
    called = []

    class Spy:
        def search(self, query, n=5):
            called.append(query)
            return []

    monkeypatch.setattr(chat.config, "get", lambda k, d=None: "off" if k == "chat.web_search" else d)
    monkeypatch.setattr(web, "get_searcher", lambda: Spy())
    assistant = _mk_assistant(monkeypatch)

    assert assistant._web_search_results("今天天气怎么样") == []
    assert not called


def test_no_keyword_skips_search(monkeypatch) -> None:
    called = []

    class Spy:
        def search(self, query, n=5):
            called.append(query)
            return []

    monkeypatch.setattr(chat.config, "get", lambda k, d=None: "auto" if k == "chat.web_search" else d)
    monkeypatch.setattr(web, "get_searcher", lambda: Spy())
    assistant = _mk_assistant(monkeypatch)

    assert assistant._web_search_results("帮我写一首诗") == []
    assert not called


def test_timeout_falls_back_silently(monkeypatch) -> None:
    import time

    class Slow:
        def search(self, query, n=5):
            time.sleep(2.0)
            return [{"title": "太慢", "url": "", "snippet": ""}]

    monkeypatch.setattr(chat.config, "get", lambda k, d=None: "auto" if k == "chat.web_search" else d)
    monkeypatch.setattr(web, "get_searcher", lambda: Slow())
    monkeypatch.setattr(chat, "_WEB_SEARCH_TIMEOUT", 0.3)
    assistant = _mk_assistant(monkeypatch)

    assert assistant._web_search_results("今天新闻") == []  # 超时静默返回空


def test_user_prompt_injects_web_results(monkeypatch) -> None:
    assistant = _mk_assistant(monkeypatch)
    prompt = assistant._user_prompt(
        "今天天气怎么样", [],
        web_results=[{"title": "今日天气", "url": "https://x/1", "snippet": "晴 24℃"}],
        include_history=False,
    )
    assert "<web-search-results>" in prompt
    assert "今日天气" in prompt
    assert "</web-search-results>" in prompt


def test_system_prompt_has_web_rule(monkeypatch) -> None:
    assistant = _mk_assistant(monkeypatch)
    prompt = assistant._system_prompt("hi", [], voice=False)
    assert "联网规则" in prompt
    assert "<web-search-results>" in prompt
