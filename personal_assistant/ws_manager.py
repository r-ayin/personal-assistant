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


@dataclass
class ConnectionManager:
    active: set[WebSocket] = field(default_factory=set)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _heartbeat_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
        log.info("ws connected: %s (total=%d)", ws.client, len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)
        log.info("ws disconnected (total=%d)", len(self.active))

    async def broadcast(self, event_type: str, payload: dict) -> int:
        """广播事件到所有连接。返回成功投递数。失败的连接被清理。"""
        from . import storage  # 延迟导入，避免循环
        msg = json.dumps({
            "type": event_type,
            "data": payload,
            "ts": storage.now_iso(),
        }, ensure_ascii=False)
        if not self.active:
            return 0
        dead: list[WebSocket] = []
        ok = 0
        for ws in list(self.active):
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
                for ws in list(self.active):
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
        for ws in list(self.active):
            try:
                await ws.close()
            except Exception:
                pass
        self.active.clear()


# 单例
manager = ConnectionManager()
