"""test_ws.py — WebSocket 端点连通性测试（需 PA_LLM_BACKEND=stub 且服务运行中）。"""
from __future__ import annotations
import asyncio
import json
import os

import pytest
import httpx

PA_PORT = 8005  # 测试端口（避免与 8004 冲突）
BASE = f"http://127.0.0.1:{PA_PORT}"

# PA_API_TOKEN 从环境变量读取（不硬编码入库）
TOKEN = os.environ.get("PA_API_TOKEN", "")


def _server_alive() -> bool:
    try:
        r = httpx.get(f"{BASE}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="module", autouse=True)
def check_server():
    if not TOKEN:
        pytest.skip("需 PA_API_TOKEN 环境变量")
    if not _server_alive():
        pytest.skip(f"PA server not running on {BASE} (start: python -m personal_assistant.cli serve --port {PA_PORT})")


@pytest.mark.asyncio
async def test_ws_live_connect():
    """验证 /ws/live 可正常连接并接收 pong 响应。"""
    try:
        from websockets import connect as ws_connect
    except ImportError:
        pytest.skip("websockets not installed")

    async with ws_connect(f"ws://127.0.0.1:{PA_PORT}/ws/live?token={TOKEN}") as ws:
        # ws_manager 握手后先广播 hello，消费后再发 ping
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert hello.get("type") == "hello", f"expected hello, got {hello}"
        await ws.send(json.dumps({"type": "ping"}))
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(resp)
        assert data.get("type") == "pong", f"expected pong, got {data}"


@pytest.mark.asyncio
async def test_ws_audio_connect():
    """验证 /ws/audio 可正常连接（无需 token 透传）。"""
    try:
        from websockets import connect as ws_connect
    except ImportError:
        pytest.skip("websockets not installed")

    async with ws_connect(f"ws://127.0.0.1:{PA_PORT}/ws/audio?token={TOKEN}") as ws:
        # 发送 ping
        await ws.send(b"\x02")  # type=2 ping
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        assert resp == b"\x02", f"expected pong byte, got {resp}"


@pytest.mark.asyncio
async def test_ws_xiaozhi_connect():
    """验证 /ws/xiaozhi 可正常连接和握手。"""
    try:
        from websockets import connect as ws_connect
    except ImportError:
        pytest.skip("websockets not installed")

    async with ws_connect(f"ws://127.0.0.1:{PA_PORT}/ws/xiaozhi?token={TOKEN}") as ws:
        # 发送 hello 握手
        await ws.send(json.dumps({
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "audio_params": {"format": "pcm", "sample_rate": 16000, "channels": 1, "frame_duration": 60}
        }))
        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(resp)
        assert data.get("type") == "hello", f"expected hello, got {data}"
        assert data.get("transport") == "websocket"
