"""ws_manager.py — WebSocket 连接管理器（下行推送：实时转录/提醒/干预/AI 回答）。

约束：stdlib + fastapi.WebSocket，零三方 SDK。
- ConnectionManager 维护活跃连接集合，broadcast(type, payload) 广播 JSON text frame。
- 心跳：每 30s ping，失败即清理（uvicorn 单 worker 下 WS 长连接需保活）。
- 单例 manager 供 api.py 与 reminders/proactive 后台巡检共用。
"""
from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

log = logging.getLogger("pa.ws")

# 事件类型枚举（前端按 type 分流渲染）
EV_TRANSCRIPTION = "transcription"   # 实时转写句 {text, speaker, is_partial, ts}
EV_CHAT_REPLY = "chat_reply"         # AI 回答 {text, evidence[], is_partial, ts}
EV_REMINDER = "reminder"             # 到点提醒 {what, when_raw, id, ts}
EV_INTERVENTION = "intervention"     # 主动干预 {kind, message, evidence, id, ts}
EV_HEALTH = "health"                 # 健康快照
EV_DEVICE = "device"                 # 设备状态
EV_RECORD = "record"                 # "我帮你记下了X" {kind: event|reminder, title/what, when_dt, when_raw, ts}
EV_LOCAL_MODEL_STATUS = "local_model_status"
EV_PERCEPTION = "perception"
EV_SCENE_CHANGED = "scene_changed"
EV_ASSISTANT_MESSAGE = "assistant_message"
EV_GAME_BARRAGE = "game_barrage"
EV_COURSE_NOTE = "course_note"
EV_SCREEN_IDLE = "screen_idle"
EV_BARRAGE = "barrage"

_ROLE_EVENT_TYPES = {
    "overlay": {EV_BARRAGE, "barrage_settings", "hello"},
}

@dataclass(frozen=True)
class ClientInfo:
    role: str
    version: int
    connected_at: str


@dataclass
class ConnectionManager:
    _clients: dict[WebSocket, ClientInfo] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _heartbeat_task: asyncio.Task | None = None

    @property
    def active(self) -> set[WebSocket]:
        return set(self._clients)

    async def connect(self, ws: WebSocket, *, role: str = "page", version: int = 1) -> None:
        from . import storage

        await ws.accept()
        async with self._lock:
            self._clients[ws] = ClientInfo(
                role=role, version=version, connected_at=storage.now_iso()
            )
        log.info("ws connected: %s role=%s (total=%d)", ws.client, role, len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)
        log.info("ws disconnected (total=%d)", len(self._clients))

    def presence(self) -> dict[str, int]:
        counts = {"page": 0, "overlay": 0, "device": 0}
        for info in self._clients.values():
            counts[info.role] = counts.get(info.role, 0) + 1
        return counts

    async def broadcast(
        self, event_type: str, payload: dict, roles: set[str] | None = None
    ) -> int:
        """Broadcast to selected roles, or every connected client when roles is None."""
        from . import storage

        msg = json.dumps({
            "type": event_type,
            "data": payload,
            "ts": storage.now_iso(),
        }, ensure_ascii=False)
        recipients = [
            ws for ws, info in list(self._clients.items())
            if (roles is None or info.role in roles)
            and event_type in _ROLE_EVENT_TYPES.get(info.role, {event_type})
        ]
        if not recipients:
            return 0
        dead: list[WebSocket] = []
        ok = 0
        for ws in recipients:
            try:
                await ws.send_text(msg)
                ok += 1
            except Exception as e:
                log.debug("broadcast drop: %s", e)
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
        return ok

    async def send_to(self, ws: WebSocket, event_type: str, payload: dict) -> bool:
        """单连接投递（如回某条 chat 请求）。"""
        info = self._clients.get(ws)
        if info and event_type not in _ROLE_EVENT_TYPES.get(info.role, {event_type}):
            return False
        from . import storage
        msg = json.dumps({"type": event_type, "data": payload, "ts": storage.now_iso()},
                         ensure_ascii=False)
        try:
            await ws.send_text(msg)
            return True
        except Exception as e:
            log.debug("send_to drop: %s", e)
            self.disconnect(ws)
            return False

    def start_heartbeat(self, interval: float = 30.0) -> None:
        """启动后台 ping 任务（在 FastAPI lifespan 里调）。"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def _beat():
            while True:
                await asyncio.sleep(interval)
                dead: list[WebSocket] = []
                for ws in list(self._clients):
                    try:
                        await ws.send_bytes(b"")  # 零字节探活；uvicorn 会发 pong
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    self.disconnect(ws)

        try:
            self._heartbeat_task = asyncio.create_task(_beat())
        except RuntimeError:
            # 无事件循环（非 lifespan 上下文）——跳过，靠广播时惰性清理即可
            log.warning("no event loop; heartbeat skipped, rely on lazy cleanup")

    async def shutdown(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        for ws in list(self._clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()


# 单例
manager = ConnectionManager()
