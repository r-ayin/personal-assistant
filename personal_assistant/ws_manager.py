"""ws_manager.py — WebSocket 连接管理器（广播/发送/心跳），stdlib + fastapi.WebSocket。"""
from __future__ import annotations
import asyncio
import json
import logging
from fastapi import WebSocket

log = logging.getLogger("pa.ws_manager")

# 事件类型（常量，避免魔法字符串）
EV_TRANSCRIPTION = "transcription"
EV_INTERVENTION = "intervention"
EV_CHAT_REPLY = "chat_reply"


class _ConnectionManager:
    """维护活跃 WS 连接集合，支持 broadcast(type, payload) 推送 JSON。"""

    def __init__(self):
        self.active: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket):
        async with self._lock:
            self.active.add(ws)
        log.info("ws connected: %s (total=%d)", getattr(ws, "client", ""), len(self.active))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self.active.discard(ws)
        log.info("ws disconnected (total=%d)", len(self.active))

    async def send_to(self, ws: WebSocket, mtype: str, payload: dict):
        """发送 JSON 到指定连接。"""
        try:
            await ws.send_json({"type": mtype, "data": payload})
        except Exception as e:
            log.debug("send_to drop: %s", e)

    async def broadcast(self, mtype: str, payload: dict):
        """向所有活跃连接广播 JSON text frame。"""
        dead: list[WebSocket] = []
        async with self._lock:
            for ws in list(self.active):
                try:
                    await ws.send_json({"type": mtype, "data": payload})
                except Exception as e:
                    log.debug("broadcast drop: %s", e)
                    dead.append(ws)
            for ws in dead:
                self.active.discard(ws)

    def start_heartbeat(self):
        """后台 ping / 惰性清理（每 30s）。"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            log.warning("no event loop; heartbeat skipped, rely on lazy cleanup")
            return

        async def _ping():
            while True:
                await asyncio.sleep(30)
                async with self._lock:
                    dead = [ws for ws in list(self.active) if not self._pong(ws)]
                    for ws in dead:
                        self.active.discard(ws)
                if dead:
                    log.debug("heartbeat cleaned %d stale connections", len(dead))

        self._heartbeat_task = asyncio.create_task(_ping())

    @staticmethod
    def _pong(ws: WebSocket) -> bool:
        try:
            import contextlib
            with contextlib.suppress(Exception):
                return ws.client_state.name == "CONNECTED"
        except Exception:
            return False


manager = _ConnectionManager()
