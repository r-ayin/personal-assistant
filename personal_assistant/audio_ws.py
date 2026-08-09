"""audio_ws.py — WebSocket audio server for ESP32 background audio (port 8004).

ESP32 sends binary WebSocket frames:
  frame format: 1B type + N bytes payload
    type=0 PCM | type=1 segment_end | type=2 ping
"""
import asyncio
import struct
import logging
import io
import wave
import math
from datetime import datetime
from pathlib import Path

import websockets
from websockets.asyncio.server import serve

from . import config, ingest, chat as chat_mod
from .asr import get_transcriber

log = logging.getLogger("pa.audio_ws")

WAKE_WORD = "江江"  # 江江
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


_TRANSCRIBER = None


def _get_transcriber():
    global _TRANSCRIBER
    if _TRANSCRIBER is None:
        _TRANSCRIBER = get_transcriber()
    return _TRANSCRIBER


async def _save_and_detect(
    pcm: bytes,
    inbox_dir: Path,
    assistant: chat_mod.Assistant | None = None,
):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"bgws-{ts}.wav"
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
    print(f"[audio_ws] segment: {name} dur={dur:.1f}s size={len(pcm)}B", flush=True)
    if dur < 0.3:
        return

    try:
        transcriber = _get_transcriber()
        loop = asyncio.get_event_loop()
        segs = await loop.run_in_executor(None, lambda: transcriber.transcribe(str(inbox_dir / name)))
        text = " ".join(s.text for s in segs if s.text and s.text.strip()).strip()
        print(f"[audio_ws] ASR: {text or '(no result)'}", flush=True)

        if not text:
            return
        if WAKE_WORD not in text:
            return

        log.info("wake word '%s' detected!", WAKE_WORD)
        try:
            active_assistant = assistant or chat_mod.assistant_for("audio-wake:default")
            reply, evidence = await loop.run_in_executor(
                None, lambda: active_assistant.respond(text)
            )
            from . import storage as _st
            _st.add_chat_log("user", text)
            _st.add_chat_log("assistant", reply, evidence=evidence)
            log.info("wake reply: %.100s", reply)
        except Exception as e:
            log.warning("chat failed: %s", e)
    except Exception as e:
        log.debug("ASR skip (%s): %s", type(e).__name__, str(e)[:80])


async def _handle(websock):
    addr = websock.remote_address
    print(f"[audio_ws] CONNECTED: {addr}", flush=True)
    inbox_dir = config.inbox_dir()
    segmenter = _BgVad()
    assistant = chat_mod.assistant_for(f"audio-ws:{id(websock)}")
    wav_count = 0

    try:
        async for message in websock:
            if isinstance(message, str):
                continue
            if len(message) < 1:
                continue
            frame_type = message[0]
            payload = message[1:]

            if frame_type == FRAME_PCM:
                for seg in segmenter.feed(payload):
                    await _save_and_detect(seg, inbox_dir, assistant)
                    wav_count += 1
            elif frame_type == FRAME_SEGMENT:
                for seg in segmenter.flush():
                    await _save_and_detect(seg, inbox_dir, assistant)
                    wav_count += 1
            elif frame_type == FRAME_PING:
                try:
                    await websock.send(b'\x02')
                except Exception:
                    pass
    except websockets.exceptions.ConnectionClosed:
        print(f"[audio_ws] DISCONNECTED: {addr}", flush=True)
    except Exception as e:
        print(f"[audio_ws] ERROR {addr}: {e}", flush=True)

    for seg in segmenter.flush():
        await _save_and_detect(seg, inbox_dir, assistant)
        wav_count += 1
    if wav_count > 0:
        log.info("ws session ended: %d segs from %s", wav_count, addr)
        await asyncio.to_thread(ingest.scan_inbox)


async def start_server(host="0.0.0.0", port=8004):
    print(f"[audio_ws] ON ws://{host}:{port} | wake='{WAKE_WORD}'", flush=True)
    server = await serve(_handle, host, port)
    await server.serve_forever()
