"""audio_tcp.py — 原始 TCP 音频服务器（端口 8004）。

ESP32 → TCP → VAD 切段 → WAV 保存 → ASR 转写 → "江江"唤醒检测 → 对话。

协议：1B type + 4B LE length + payload
  type=0 PCM | type=1 segment_end | type=2 ping
"""

from __future__ import annotations
import asyncio
import logging
import struct
import math
from datetime import datetime
from pathlib import Path

from . import config, ingest, chat as chat_mod
from .asr import get_transcriber
from .ws_manager import manager as ws_manager

log = logging.getLogger("pa.audio_tcp")

WAKE_WORD = "江江"

class _BgVad:
    def __init__(self, threshold=350, holdout_ms=500, min_utt_ms=300):
        self.threshold = threshold
        self.holdout = holdout_ms
        self.min_utt = min_utt_ms
        self._buf = bytearray()
        self._speaking = False
        self._silence = 0
        self._speech = 0
        self._chunk_n = 512

    def feed(self, pcm: bytes):
        out = []
        n = len(pcm) // 2
        for i in range(0, n, self._chunk_n):
            chunk = pcm[i * 2:(i + self._chunk_n) * 2]
            if len(chunk) < 2:
                break
            samples = struct.unpack(f"<{len(chunk) // 2}h", chunk)
            rms = int(math.sqrt(sum(s * s for s in samples) / len(samples)))
            voice = rms >= self.threshold
            if not self._speaking:
                if voice:
                    self._buf.extend(chunk)
                    if len(self._buf) >= self._chunk_n * 2 * 2:
                        self._speaking = True
                        self._speech = len(self._buf) // 2
                        self._silence = 0
                else:
                    self._buf = bytearray()
            else:
                self._buf.extend(chunk)
                self._speech += self._chunk_n
                if voice:
                    self._silence = 0
                else:
                    self._silence += 1
                    ms = self._silence * (self._chunk_n * 1000 // 16000)
                    if ms >= self.holdout:
                        utt_ms = self._speech * 1000 // 16000
                        if utt_ms >= self.min_utt:
                            out.append(bytes(self._buf))
                        self._buf = bytearray()
                        self._speaking = False
                        self._speech = 0
                        self._silence = 0
        return out

    def flush(self):
        out = []
        if self._speaking:
            utt_ms = self._speech * 1000 // 16000
            if utt_ms >= self.min_utt:
                out.append(bytes(self._buf))
        self._buf = bytearray()
        return out


# 全局 ASR 转写器（延迟加载）
_TRANSCRIBER = None


def _get_transcriber():
    global _TRANSCRIBER
    if _TRANSCRIBER is None:
        _TRANSCRIBER = get_transcriber()
    return _TRANSCRIBER


async def _save_and_detect(pcm: bytes, inbox_dir: Path):
    """保存 WAV + ASR + 唤醒词检测。"""
    import wave, io
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"bgtcp-{ts}.wav"
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    try:
        (inbox_dir / name).write_bytes(wav_io.getvalue())
    except Exception as e:
        log.warning("save error: %s", e)
        return

    dur = len(pcm) / 32000
    print(f"[audio_tcp] segment: {name} dur={dur:.1f}s size={len(pcm)}B", flush=True)
    if dur < 0.3:
        return  # 太短，跳过 ASR

    # ASR 转写
    try:
        transcriber = _get_transcriber()
        loop = asyncio.get_event_loop()
        segs = await loop.run_in_executor(None, lambda: transcriber.transcribe(str(inbox_dir / name)))

        text = " ".join(s.text for s in segs if s.text and s.text.strip()).strip()
        print(f"[audio_tcp] ASR: {text or '(无结果)'}", flush=True)

        if not text:
            return

        if WAKE_WORD not in text:
            return

        log.info("唤醒词 '%s' 检测到！", WAKE_WORD)
        try:
            assistant = chat_mod.Assistant()
            reply = await loop.run_in_executor(None, lambda: assistant.respond(text))

            from . import storage as _st
            _st.add_chat_log("user", text)
            _st.add_chat_log("assistant", reply)

            await ws_manager.broadcast("transcription", {
                "text": text, "wake_word": True, "source": "esp32"
            })
            await ws_manager.broadcast("chat_reply", {
                "reply": reply, "evidence": [], "wake_trigger": True
            })
            log.info("唤醒回复: %.100s", reply)
        except Exception as e:
            log.warning("对话失败: %s", e)

    except Exception as e:
        log.debug("ASR skip (%s): %s", type(e).__name__, str(e)[:80])


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info('peername')
    log.info("tcp connected: %s", addr)
    inbox_dir = config.inbox_dir()
    segmenter = _BgVad()
    wav_count = 0
    buf = bytearray()

    try:
        while True:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=300)
            if not chunk:
                break
            buf.extend(chunk)
            while len(buf) >= 5:
                frame_type = buf[0]
                frame_len = struct.unpack('<I', buf[1:5])[0]
                if frame_len > 65536:
                    buf.clear()
                    break
                if len(buf) < 5 + frame_len:
                    break
                payload = bytes(buf[5:5 + frame_len])
                buf = buf[5 + frame_len:]

                if frame_type == 0:  # PCM
                    for seg in segmenter.feed(payload):
                        await _save_and_detect(seg, inbox_dir)
                        wav_count += 1
                elif frame_type == 1:  # segment end
                    for seg in segmenter.flush():
                        await _save_and_detect(seg, inbox_dir)
                        wav_count += 1
                elif frame_type == 2:  # ping
                    try:
                        writer.write(b'\x02')
                        await writer.drain()
                    except Exception:
                        pass
    except asyncio.TimeoutError:
        log.info("tcp timeout: %s", addr)
    except ConnectionResetError:
        pass
    except Exception as e:
        log.warning("tcp error %s: %s", addr, e)

    for seg in segmenter.flush():
        await _save_and_detect(seg, inbox_dir)
        wav_count += 1
    if wav_count > 0:
        log.info("tcp session ended: %d segs from %s", wav_count, addr)
        await asyncio.to_thread(ingest.scan_inbox)

    try:
        writer.close()
    except Exception:
        pass


async def start_server(host="0.0.0.0", port=8004):
    server = await asyncio.start_server(_handle, host, port)
    print(f"[audio_tcp] ON {host}:{port} | wake='{WAKE_WORD}'", flush=True)
    async with server:
        await server.serve_forever()
