from __future__ import annotations

from fastapi.testclient import TestClient

from personal_assistant import api, chat
from personal_assistant.llm import LLMResult


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer session-test-token"}


def test_chat_endpoint_returns_usage_and_reuses_conversation_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api.config, "api_token", lambda: "session-test-token")
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: tmp_path / "chat-session.db")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    chat.CONVERSATIONS.clear()

    class DetailedLLM:
        supports_message_history = True
        requests: list[list[dict]] = []

        def chat_messages_detailed(self, _system, messages, temperature=0.3):
            self.requests.append([dict(message) for message in messages])
            return LLMResult(
                text=f"回复{len(self.requests)}",
                provider="deepseek",
                model="test-model",
                input_tokens=100,
                output_tokens=10,
                total_tokens=110,
                cache_hit_tokens=80,
                cache_miss_tokens=20,
            )

    model = DetailedLLM()
    monkeypatch.setattr(chat, "get_llm", lambda: model)
    monkeypatch.setattr(chat, "get_embedder", lambda: object())
    monkeypatch.setattr(chat.recall, "hybrid_recall", lambda *_a, **_k: type("R", (), {"items": []})())
    monkeypatch.setattr(chat.memory, "search", lambda *_a, **_k: [])
    monkeypatch.setattr(chat, "recent_perception_segments", lambda **_k: [])

    with TestClient(api.app) as client:
        first = client.post("/chat", json={"message": "第一问"}, headers=_headers())
        assert first.status_code == 200
        first_body = first.json()
        conversation_id = first_body["conversation_id"]
        assert conversation_id.startswith("rest-")
        assert first_body["metadata"]["llm"]["cache_hit_rate"] == 0.8
        assert first_body["metadata"]["system_prompt_sha256"]

        second = client.post(
            "/chat",
            json={"message": "第二问", "conversation_id": conversation_id},
            headers=_headers(),
        )
        assert second.status_code == 200
        assert second.json()["conversation_id"] == conversation_id

    assert len(model.requests) == 2
    assert model.requests[1][:2] == [
        model.requests[0][0],
        {"role": "assistant", "content": "回复1"},
    ]
    chat.CONVERSATIONS.clear()


def test_chat_endpoint_keeps_conversations_isolated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api.config, "api_token", lambda: "session-test-token")
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: tmp_path / "chat-isolation.db")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    chat.CONVERSATIONS.clear()

    class DetailedLLM:
        supports_message_history = True
        requests: list[list[dict]] = []

        def chat_messages_detailed(self, _system, messages, temperature=0.3):
            self.requests.append([dict(message) for message in messages])
            return LLMResult(text="独立回复")

    model = DetailedLLM()
    monkeypatch.setattr(chat, "get_llm", lambda: model)
    monkeypatch.setattr(chat, "get_embedder", lambda: object())
    monkeypatch.setattr(chat.recall, "hybrid_recall", lambda *_a, **_k: type("R", (), {"items": []})())
    monkeypatch.setattr(chat.memory, "search", lambda *_a, **_k: [])
    monkeypatch.setattr(chat, "recent_perception_segments", lambda **_k: [])

    with TestClient(api.app) as client:
        client.post("/chat", json={"message": "A 的秘密", "conversation_id": "A"}, headers=_headers())
        client.post("/chat", json={"message": "B 的秘密", "conversation_id": "B"}, headers=_headers())

    assert len(model.requests[0]) == len(model.requests[1]) == 1
    assert "A 的秘密" in model.requests[0][0]["content"]
    assert "A 的秘密" not in model.requests[1][0]["content"]
    assert "B 的秘密" in model.requests[1][0]["content"]
    chat.CONVERSATIONS.clear()
