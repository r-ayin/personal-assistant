from __future__ import annotations

import asyncio
import json

import pytest
from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

from personal_assistant import api, ws_manager


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.accepted = False
        self.closed: list[int | None] = []
        self.client = "fake-client"

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def send_bytes(self, _message: bytes) -> None:
        return None

    async def close(self, code: int | None = None) -> None:
        self.closed.append(code)


def test_barrage_targets_only_overlay_clients() -> None:
    async def scenario() -> None:
        manager = ws_manager.ConnectionManager()
        page_ws = FakeWebSocket()
        overlay_ws = FakeWebSocket()
        await manager.connect(page_ws, role="page", version=1)
        await manager.connect(overlay_ws, role="overlay", version=1)

        delivered = await manager.broadcast(
            "barrage", {"text": "请休息一下"}, roles={"overlay"}
        )

        assert delivered == 1
        assert page_ws.sent == []
        assert overlay_ws.sent[0]["type"] == "barrage"
        assert manager.presence() == {"page": 1, "overlay": 1, "device": 0}
        assert manager.active == {page_ws, overlay_ws}
        await manager.shutdown()

    asyncio.run(scenario())

def test_overlay_never_receives_page_or_device_business_events() -> None:
    async def scenario() -> None:
        manager = ws_manager.ConnectionManager()
        page_ws = FakeWebSocket()
        overlay_ws = FakeWebSocket()
        device_ws = FakeWebSocket()
        await manager.connect(page_ws, role="page", version=1)
        await manager.connect(overlay_ws, role="overlay", version=1)
        await manager.connect(device_ws, role="device", version=1)

        delivered = await manager.broadcast(
            ws_manager.EV_CHAT_REPLY,
            {"text": "页面回复", "evidence": ["private-memory"]},
        )
        await manager.broadcast(
            ws_manager.EV_REMINDER,
            {"what": "完整提醒业务载荷", "source_segment": "private-memory"},
        )

        assert delivered == 2
        assert [message["type"] for message in page_ws.sent] == ["chat_reply", "reminder"]
        assert [message["type"] for message in device_ws.sent] == ["chat_reply", "reminder"]
        assert overlay_ws.sent == []
        await manager.shutdown()

    asyncio.run(scenario())

def test_direct_send_cannot_bypass_overlay_event_whitelist() -> None:
    async def scenario() -> None:
        manager = ws_manager.ConnectionManager()
        overlay_ws = FakeWebSocket()
        await manager.connect(overlay_ws, role="overlay", version=1)

        assert await manager.send_to(overlay_ws, "hello", {"version": 1}) is True
        assert await manager.send_to(
            overlay_ws, ws_manager.EV_CHAT_REPLY, {"text": "private"}
        ) is False
        assert [message["type"] for message in overlay_ws.sent] == ["hello"]
        await manager.shutdown()

    asyncio.run(scenario())


def test_invalid_overlay_token_is_rejected_with_policy_code(monkeypatch) -> None:
    monkeypatch.setenv("PA_API_TOKEN", "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)

    with TestClient(api.app) as client:
        with client.websocket_connect(
            "/ws/live?client=overlay&version=1&token=wrong"
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_json()

    assert exc_info.value.code == 1008


def test_disconnect_removes_role_metadata() -> None:
    async def scenario() -> None:
        manager = ws_manager.ConnectionManager()
        overlay_ws = FakeWebSocket()
        await manager.connect(overlay_ws, role="overlay", version=1)
        manager.disconnect(overlay_ws)
        assert manager.presence()["overlay"] == 0
        assert manager.active == set()

    asyncio.run(scenario())


def test_incompatible_overlay_protocol_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("PA_API_TOKEN", "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)

    with TestClient(api.app) as client:
        with client.websocket_connect(
            "/ws/live?client=overlay&version=2&token=omni-test-token"
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_json()

    assert exc_info.value.code == 1008

def test_overlay_receives_hello_and_current_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PA_API_TOKEN", "omni-test-token")
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: tmp_path / "overlay.db")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)

    with TestClient(api.app) as client:
        with client.websocket_connect(
            "/ws/live?client=overlay&version=1&token=omni-test-token"
        ) as ws:
            hello = ws.receive_json()
            settings = ws.receive_json()

    assert hello["type"] == "hello"
    assert hello["data"] == {"client": "overlay", "version": 1}
    assert settings["type"] == "barrage_settings"
    assert settings["data"]["enabled"] is True
