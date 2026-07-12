"""xiaozhi_server.py — 实现 xiaozhi-esp32 WebSocket 服务端协议（设备↔电脑对话）。

协议见 https://github.com/78/xiaozhi-esp32/blob/main/docs/websocket.md
- hello 握手协商 audio_params（opus/pcm, 16kHz, frame_duration 60ms）
- 设备发 listen{state:start/stop/detect} 标记语音边界（设备端 ESP-SR 唤醒词+VAD 已做）
- 设备发二进制 OPUS/PCM 帧 → 服务端解码 → 累积 → listen stop 时整段 ASR
- 服务端发 stt{text}（转写）→ LLM → tts{state:start/sentence_start:text/stop}（逐句回答）
- 同时把 stt/tts 事件经 ws_manager 广播到手机 live.html（实时转录 + AI 回答两流）

OPUS 解码用 opuslib（lazy import；GPU 电脑 pip install opuslib + libopus）。
dev 盒无 opuslib → 用 format=pcm 的假客户端测协议；真 xiaozhi 固件发 opus 需 GPU 电脑。
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import struct
import wave
import io
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from . import auth, storage, ws_manager
from . import chat as _chat

log = logging.getLogger("pa.xiaozhi")

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit
CHANNELS = 1


def _split_sentences(text: str) -> list[str]:
    """按中英文句末标点切成句（保留标点）。"""
    parts = re.findall(r'[^。！？!?…\n]*[。！？!?…\n]*', text)
    out = [p for p in (x.strip() for x in parts) if p]
    return out or [text]


class _OpusDecoder:
    """lazy 包装 opuslib；不可用返回 None。"""
    _cache = None
    _tried = False

    @classmethod
    def get(cls, sample_rate: int, channels: int):
        if not cls._tried:
            cls._tried = True
            try:
                import opuslib  # noqa
                cls._cache = ("opuslib", opuslib)
            except ImportError:
                log.warning("opuslib 未装（OPUS 解码不可用）；format=opus 的真 xiaozhi 固件需 GPU 电脑装 opuslib。dev 用 format=pcm 测。")
                cls._cache = None
        if cls._cache is None:
            return None
        _, lib = cls._cache
        return lib.Decoder(sample_rate, channels)


class XiaozhiSession:
    """单个设备连接的会话状态机。"""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.session_id = f"s-{datetime.now().strftime('%H%M%S%f')[:12]}"
        self.audio_format = "pcm"      # 设备 hello 声明
        self.sample_rate = SAMPLE_RATE
        self.channels = CHANNELS
        self.frame_duration = 60
        self._opus = None              # opuslib.Decoder（lazy）
        self._pcm_buf = bytearray()    # 当前 listen 段累积的 PCM
        self._listening = False
        self._aborted = False

    async def _send_json(self, obj: dict) -> None:
        obj.setdefault("session_id", self.session_id)
        try:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))
        except Exception as e:
            log.debug("send_json drop: %s", e)

    async def _on_hello(self, msg: dict) -> None:
        ap = msg.get("audio_params", {}) or {}
        self.audio_format = ap.get("format", "pcm")
        self.sample_rate = int(ap.get("sample_rate", SAMPLE_RATE))
        self.channels = int(ap.get("channels", CHANNELS))
        self.frame_duration = int(ap.get("frame_duration", 60))
        if self.audio_format == "opus":
            self._opus = _OpusDecoder.get(self.sample_rate, self.channels)
            if self._opus is None:
                # 服务端无 OPUS 解码器 → 协商 pcm（dev 兼容；真固件仍发 opus 则需装 opuslib）
                self.audio_format = "pcm"
        # 回 hello
        await self._send_json({
            "type": "hello", "transport": "websocket",
            "session_id": self.session_id,
            "audio_params": {
                "format": self.audio_format, "sample_rate": self.sample_rate,
                "channels": self.channels, "frame_duration": self.frame_duration,
            },
        })
        log.info("xiaozhi hello: session=%s format=%s", self.session_id, self.audio_format)

    async def _on_listen(self, msg: dict) -> None:
        state = msg.get("state")
        if state == "start":
            self._listening = True
            self._pcm_buf = bytearray()
            self._aborted = False
        elif state == "stop":
            self._listening = False
            await self._finalize_utterance()
        elif state == "detect":
            # 唤醒词检测，等同 start
            self._listening = True
            self._pcm_buf = bytearray()

    async def _on_audio(self, data: bytes) -> None:
        if not self._listening:
            return  # 非 listen 段的帧丢弃
        if self.audio_format == "opus":
            if self._opus is None:
                return
            try:
                pcm = self._opus.decode(data, frame_size=int(self.sample_rate * self.frame_duration / 1000))
                self._pcm_buf.extend(pcm)
            except Exception as e:
                log.warning("opus decode 失败: %s", e)
        else:
            # PCM 16-bit LE
            self._pcm_buf.extend(data)

    async def _finalize_utterance(self) -> None:
        if self._aborted:
            return
        pcm = bytes(self._pcm_buf)
        self._pcm_buf = bytearray()
        if len(pcm) < SAMPLE_RATE * SAMPLE_WIDTH // 2:  # < 0.5s 丢弃
            return
        # PCM → wav bytes → ASR
        wav_bytes = self._to_wav(pcm)
        text = await asyncio.to_thread(self._asr, wav_bytes)
        if not text:
            return
        # stt 事件 → 设备 + 手机
        await self._send_json({"type": "stt", "text": text})
        await ws_manager.manager.broadcast(ws_manager.EV_TRANSCRIPTION,
                                           {"text": text, "speaker": "user",
                                            "is_partial": False})
        # LLM 回答（chat.Assistant：人格档案 + 记忆检索）
        await asyncio.to_thread(storage.add_chat_log, "user", text)
        reply, evidence = await asyncio.to_thread(_chat.Assistant().respond, text)
        await asyncio.to_thread(storage.add_chat_log, "assistant", reply, evidence=evidence)
        # tts 逐句事件 → 设备 + 手机
        await self._send_json({"type": "tts", "state": "start"})
        sentences = _split_sentences(reply)
        for i, s in enumerate(sentences):
            if self._aborted:
                break
            is_last = (i == len(sentences) - 1)
            await self._send_json({"type": "tts", "state": "sentence_start", "text": s})
            await ws_manager.manager.broadcast(ws_manager.EV_CHAT_REPLY,
                                               {"text": s, "evidence": evidence or [],
                                                "is_partial": not is_last})
            await asyncio.sleep(0)  # 让事件循环喘息
        await self._send_json({"type": "tts", "state": "stop"})

    def _asr(self, wav_bytes: bytes) -> str:
        """调 Transcriber 转写 wav bytes → 文本。stub/dev 返回样例。"""
        from . import config, asr
        import tempfile, os
        archive = config.ROOT / "data" / "inbox" / "archive"
        archive.mkdir(parents=True, exist_ok=True)  # 先建目录再 mkstemp
        fd, path = tempfile.mkstemp(suffix=".wav", dir=str(archive))
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(wav_bytes)
            transcriber = asr.get_transcriber()
            segs = transcriber.transcribe(path)
            return "".join(s.text for s in segs).strip()
        except Exception as e:
            log.warning("ASR 失败: %s", e)
            return ""
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    @staticmethod
    def _to_wav(pcm: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        return buf.getvalue()

    async def _on_abort(self, msg: dict) -> None:
        self._aborted = True
        self._pcm_buf = bytearray()


async def xiaozhi_endpoint(ws: WebSocket):
    """/ws/xiaozhi — xiaozhi-esp32 设备接入点。"""
    # 鉴权：Authorization header（xiaozhi 固件用 Bearer header）或 ?token=
    token = ws.query_params.get("token", "")
    if not token:
        authz = ws.headers.get("authorization") or ws.headers.get("Authorization") or ""
        if authz.lower().startswith("bearer "):
            token = authz[7:].strip()
    # 用 auth._check 校验（同 PA_API_TOKEN）
    if auth.is_auth_enabled() and not auth._check(token):
        await ws.close(code=1008)
        return
    await ws.accept()
    sess = XiaozhiSession(ws)
    log.info("xiaozhi device connected: %s", ws.client)
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if "bytes" in msg and msg["bytes"] is not None:
                await sess._on_audio(msg["bytes"])
            elif "text" in msg and msg["text"] is not None:
                try:
                    obj = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                t = obj.get("type")
                if t == "hello":
                    await sess._on_hello(obj)
                elif t == "listen":
                    await sess._on_listen(obj)
                elif t == "abort":
                    await sess._on_abort(obj)
                # mcp/system 暂不处理
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("xiaozhi endpoint error: %s", e)
    finally:
        log.info("xiaozhi device disconnected: %s", sess.session_id)
