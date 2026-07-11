"""xiaozhi_server.py — /ws/xiaozhi 端点，xiaozhi-esp32 设备接入（唤醒词+对话）。"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger("pa.xiaozhi")


def _split_sentences(text: str) -> list[str]:
    """按中文/英文句末标点切句（含省略号）。"""
    return [s.strip() for s in re.split(r"[^…。！？!?\n]*[…。！？!?\n]*", text) if s.strip()]


class _OpusDecoder:
    """lazy 封装 opuslib，不可用时返回 None。"""

    def __init__(self):
        self._decoder = None

    def ensure(self, sample_rate: int = 16000, channels: int = 1) -> bool:
        if self._decoder is not None:
            return True
        try:
            import opuslib
            self._decoder = opuslib.Decoder(sample_rate, channels)
            return True
        except ImportError:
            log.warning("opuslib 未装（OPUS 解码不用），format=pcm 可绕过。GPU 盒装 opuslib 即可启用。")
            return False
        except Exception as e:
            log.warning("opus decode 失败: %s", e)
            return False

    def decode(self, data: bytes, frame_size: int = 960) -> bytes | None:
        if self._decoder is None:
            return None
        try:
            return self._decoder.decode(data, frame_size)
        except Exception as e:
            log.warning("opus decode 失败: %s", e)
            return None


class XiaozhiSession:
    """管理设备连接的会话状态。"""

    def __init__(self):
        self.session_id: str = ""
        self.audio_params: dict = {}
        self.sentence_start: int = 0
        self.frame_duration: int = 60


async def xiaozhi_endpoint(ws: WebSocket):
    """/ws/xiaozhi 的 xiaozhi-esp32 设备接入点。"""
    # 基础校验
    qp = ws.query_params
    token = qp.get("token", "")
    auth_header = ws.headers.get("authorization") or ws.headers.get("Authorization") or ""
    if not token and not auth_header:
        await ws.close(code=1008)
        return

    await ws.accept()
    session = XiaozhiSession()
    decoder = _OpusDecoder()

    log.info("xiaozhi device connected: %s", ws.client)

    try:
        while True:
            raw = await ws.receive_json()
            mtype = raw.get("type", "")

            if mtype == "hello":
                session.session_id = raw.get("session_id", "")
                session.audio_params = raw.get("audio_params", {})
                decoder.ensure(
                    session.audio_params.get("sample_rate", 16000),
                    session.audio_params.get("channels", 1),
                )
                log.info("xiaozhi hello: session=%s format=%s",
                         session.session_id, session.audio_params.get("format", "pcm"))
                await ws.send_json({"type": "hello", "session_id": session.session_id})

            elif mtype == "audio":
                audio_data = raw.get("audio", b"")
                if decoder._decoder and audio_data:
                    pcm = decoder.decode(audio_data)
                    if pcm:
                        # 转发到 LLM/对话处理（由上层业务实现）
                        pass

            elif mtype == "text":
                text = raw.get("text", "")
                log.info("xiaozhi text: %.60s", text)

            elif mtype == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        log.info("xiaozhi device disconnected: %s", ws.client)
    except Exception as e:
        log.warning("xiaozhi endpoint error: %s", e)
