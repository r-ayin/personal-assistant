"""audio_ws.py — WebSocket 音频服务器（端口 8003，用 websockets 库）。"""
from __future__ import annotations
import asyncio
import logging
import struct
import math
from datetime import datetime
from pathlib import Path
import websockets
from . import config, ingest

log = logging.getLogger("pa.audio_ws")

FRAME_PCM = 0
FRAME_SEGMENT = 1
FRAME_PING = 2


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


async def _save_seg(pcm: bytes, inbox_dir: Path) -> str | None:
    import wave, io
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"bg-{ts}.wav"
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    try:
        (inbox_dir / name).write_bytes(wav_io.getvalue())
        log.info("bg segment saved: %s (%dB)", name, len(pcm))
        return name
    except Exception as e:
        log.warning("save error: %s", e)
        return None


async def handler(ws):
    inbox_dir = config.inbox_dir()
    segmenter = _BgVad()
    wav_count = 0
    log.info("audio_ws client connected")

    try:
        async for msg in ws:
            if isinstance(msg, str) or not msg:
                continue
            frame_type = msg[0]
            if frame_type == FRAME_PCM:
                for seg in segmenter.feed(msg[1:]):
                    await _save_seg(seg, inbox_dir)
                    wav_count += 1
            elif frame_type == FRAME_SEGMENT:
                for seg in segmenter.flush():
                    await _save_seg(seg, inbox_dir)
                    wav_count += 1
            elif frame_type == FRAME_PING:
                try:
                    await ws.send(b"\x02")
                except Exception:
                    pass
    except websockets.ConnectionClosed:
        log.info("audio_ws client disconnected (%d segs)", wav_count)

    for seg in segmenter.flush():
        await _save_seg(seg, inbox_dir)
        wav_count += 1
    if wav_count > 0:
        log.info("audio_ws done: %d segs, triggering ingest", wav_count)
        await asyncio.to_thread(ingest.scan_inbox)


async def start_server(host="0.0.0.0", port=8003):
    async with websockets.serve(handler, host, port, max_size=65536, ping_interval=30, ping_timeout=10, open_timeout=30):
        log.info("audio_ws on %s:%d", host, port)
        await asyncio.Future()
