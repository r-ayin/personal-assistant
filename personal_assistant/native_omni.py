"""MiniCPM-o native Worker 协议与生命周期。

协议和命名管道实现改编自 LYiHub/pub-local-jarvis（MIT License，
Copyright (c) 2026 AI Jarvis contributors），保持其 protocol v1 兼容性。
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import os
import struct
import subprocess
import threading
import time
import zlib
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import IntEnum
from itertools import count
from pathlib import Path
from typing import Any

from . import config, local_omni

MAGIC = 0x56524A41
PROTOCOL_VERSION = 1
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
HEADER = struct.Struct("<IHHIQIII")


class ProtocolError(ValueError):
    pass


class MessageType(IntEnum):
    HELLO = 1
    START = 2
    STOP = 3
    SUBMIT = 4
    CANCEL = 5
    RESULT = 6
    STATUS = 7
    ERROR = 8
    SHUTDOWN = 9
    CONFIGURE_GAME = 10
    START_DUPLEX = 11
    STOP_DUPLEX = 12


class StatusCode(IntEnum):
    OK = 0
    MALFORMED = 1
    UNSUPPORTED_VERSION = 2
    UNAVAILABLE = 3
    CANCELLED = 4
    INTERNAL_ERROR = 5


@dataclass(frozen=True, slots=True)
class Frame:
    message_type: MessageType
    request_id: int = 0
    payload: bytes = b""
    flags: int = 0
    version: int = PROTOCOL_VERSION


def json_payload(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def encode_frame(frame: Frame, max_frame_bytes: int = MAX_PAYLOAD_BYTES) -> bytes:
    if not 0 <= frame.request_id <= 0xFFFFFFFFFFFFFFFF:
        raise ProtocolError("request ID is outside uint64 range")
    if len(frame.payload) > min(max_frame_bytes, MAX_PAYLOAD_BYTES):
        raise ProtocolError("frame payload exceeds configured maximum")
    checksum = zlib.crc32(frame.payload) & 0xFFFFFFFF
    return HEADER.pack(
        MAGIC,
        frame.version,
        int(frame.message_type),
        int(frame.flags),
        frame.request_id,
        len(frame.payload),
        checksum,
        0,
    ) + frame.payload


def decode_frame(
    data: bytes,
    expected_version: int = PROTOCOL_VERSION,
    max_frame_bytes: int = MAX_PAYLOAD_BYTES,
) -> Frame:
    if len(data) < HEADER.size:
        raise ProtocolError("incomplete frame header")
    magic, version, message_type, flags, request_id, length, checksum, reserved = (
        HEADER.unpack_from(data)
    )
    if magic != MAGIC:
        raise ProtocolError("invalid frame magic")
    if version != expected_version:
        raise ProtocolError(f"unsupported protocol version {version}")
    if reserved != 0:
        raise ProtocolError("reserved header field must be zero")
    if length > min(max_frame_bytes, MAX_PAYLOAD_BYTES):
        raise ProtocolError("frame payload exceeds configured maximum")
    if len(data) != HEADER.size + length:
        raise ProtocolError("frame length mismatch")
    payload = data[HEADER.size:]
    if zlib.crc32(payload) & 0xFFFFFFFF != checksum:
        raise ProtocolError("payload checksum mismatch")
    try:
        kind = MessageType(message_type)
    except ValueError as exc:
        raise ProtocolError(f"unknown message type {message_type}") from exc
    return Frame(kind, request_id, payload, flags, version)


class NativeOmniClient(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def events(self) -> AsyncIterator[dict[str, Any]]: ...


class InProcessOmniClient(NativeOmniClient):
    """显式测试客户端；它不执行模型推理，也不会被真实配置自动选中。"""

    def __init__(self) -> None:
        self.running = False
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        await self.emit({"type": "worker.ready", "inference_provider": "fake"})

    async def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        await self._events.put(None)

    async def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.running:
            raise RuntimeError("native worker is not running")
        if method == "ping":
            return {"ok": True, "result": "pong"}
        return {"ok": True, "method": method, "result": payload}

    async def emit(self, event: dict[str, Any]) -> None:
        await self._events.put(event)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event


class NamedPipeOmniClient(NativeOmniClient):
    """Windows 命名管道客户端，与 AI Jarvis C++ Worker protocol v1 兼容。"""

    _METHODS = {
        "start_monitoring": MessageType.START,
        "resume_monitoring": MessageType.START,
        "pause_monitoring": MessageType.STOP,
        "stop_monitoring": MessageType.STOP,
        "ask": MessageType.SUBMIT,
        "cancel": MessageType.CANCEL,
        "shutdown": MessageType.SHUTDOWN,
        "ping": MessageType.HELLO,
        "set_game_profile": MessageType.CONFIGURE_GAME,
        "start_duplex": MessageType.START_DUPLEX,
        "stop_duplex": MessageType.STOP_DUPLEX,
    }

    def __init__(self, pipe_name: str, *, timeout: float = 600.0) -> None:
        self.pipe_name = pipe_name
        self.timeout = timeout
        self.running = False
        self._stream: Any = None
        self._ids = count(1)
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._result_requests: set[int] = set()
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._write_lock = asyncio.Lock()
        self._windows_io_lock = threading.Lock()

    async def start(self) -> None:
        if self.running:
            return
        if os.name != "nt":
            raise RuntimeError("named-pipe MiniCPM-o mode is available only on Windows")
        self._stream = await asyncio.to_thread(open, self.pipe_name, "r+b", buffering=0)
        self.running = True
        self._reader_task = asyncio.create_task(self._read_loop(), name="pa-omni-pipe-reader")
        await self.request("ping", {})

    async def stop(self) -> None:
        if not self.running and self._stream is None:
            return
        self.running = False
        if self._stream is not None:
            with suppress(Exception):
                await asyncio.to_thread(self._stream.close)
            self._stream = None
        if self._reader_task:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._reader_task
            self._reader_task = None
        error = RuntimeError("native pipe closed")
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()
        self._result_requests.clear()
        await self._events.put(None)

    async def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.running or self._stream is None:
            raise RuntimeError("native worker is not running")
        try:
            message_type = self._METHODS[method]
        except KeyError as exc:
            raise ValueError(f"unsupported native command: {method}") from exc
        request_id = next(self._ids)
        if message_type == MessageType.SUBMIT:
            body: Any = str(payload.get("text", ""))
        elif message_type == MessageType.CONFIGURE_GAME:
            body = f"{str(payload.get('name', ''))[:80]}\0{str(payload.get('prompt', ''))[:8000]}"
        elif message_type == MessageType.START_DUPLEX:
            body = (
                f"{str(payload.get('session_id', ''))[:128]}\0"
                f"{str(payload.get('instruction', ''))[:2000]}"
            )
        else:
            body = payload
        raw = body.encode("utf-8") if isinstance(body, str) else json_payload(body)
        frame = encode_frame(Frame(message_type, request_id, raw))
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        if message_type == MessageType.SUBMIT:
            self._result_requests.add(request_id)
        async with self._write_lock:
            await asyncio.to_thread(self._write_exact, frame)
        try:
            timeout = max(0.1, min(600.0, float(payload.get("_timeout_seconds", self.timeout))))
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(request_id, None)
            self._result_requests.discard(request_id)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            event = await self._events.get()
            if event is None:
                return
            yield event

    async def _read_loop(self) -> None:
        try:
            while self.running and self._stream is not None:
                available = await asyncio.to_thread(self._windows_bytes_available)
                if available < HEADER.size:
                    await asyncio.sleep(0.01)
                    continue
                header = await asyncio.to_thread(self._read_exact, HEADER.size)
                length = HEADER.unpack(header)[5]
                payload = await asyncio.to_thread(self._read_exact, length)
                frame = decode_frame(header + payload)
                data = self._decode_payload(frame)
                pending = self._pending.get(frame.request_id)
                if frame.message_type == MessageType.ERROR and pending:
                    pending.set_exception(RuntimeError(str(data.get("error", "native worker error"))))
                elif frame.message_type == MessageType.STATUS and pending:
                    if frame.request_id in self._result_requests and frame.flags == StatusCode.CANCELLED:
                        pending.set_exception(RuntimeError("native inference was cancelled"))
                    elif frame.request_id not in self._result_requests:
                        pending.set_result(data)
                elif frame.message_type == MessageType.RESULT and pending:
                    pending.set_result(data)
                    await self._events.put(
                        {"type": "answer.completed", "request_id": frame.request_id, **data}
                    )
                elif frame.message_type == MessageType.RESULT:
                    native_event = self._parse_native_event(frame.request_id, data)
                    await self._events.put(
                        native_event
                        or {
                            "type": "perception.completed"
                            if frame.request_id >= (1 << 63)
                            else "answer.completed",
                            "request_id": frame.request_id,
                            **data,
                        }
                    )
                else:
                    await self._events.put(
                        {"type": "native.event", "request_id": frame.request_id, **data}
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self.running:
                await self._events.put({"type": "worker.fatal", "error": str(exc)})
        finally:
            error = RuntimeError("native pipe reader stopped")
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(error)
            await self._events.put(None)
            self.running = False

    def _windows_pipe_handle(self) -> int:
        import msvcrt

        return int(msvcrt.get_osfhandle(self._stream.fileno()))

    def _read_exact(self, size: int) -> bytes:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        data = bytearray()
        with self._windows_io_lock:
            while len(data) < size:
                remaining = size - len(data)
                buffer = ctypes.create_string_buffer(remaining)
                transferred = ctypes.c_ulong()
                if not kernel32.ReadFile(
                    ctypes.c_void_p(self._windows_pipe_handle()),
                    buffer,
                    remaining,
                    ctypes.byref(transferred),
                    None,
                ):
                    error = ctypes.get_last_error()
                    if error in {109, 232}:
                        raise EOFError("native pipe closed")
                    raise OSError(error, "ReadFile failed for native pipe")
                if transferred.value == 0:
                    raise EOFError("native pipe closed")
                data.extend(buffer.raw[: transferred.value])
        return bytes(data)

    def _write_exact(self, data: bytes) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        offset = 0
        with self._windows_io_lock:
            while offset < len(data):
                chunk = data[offset:]
                buffer = ctypes.create_string_buffer(chunk)
                transferred = ctypes.c_ulong()
                if not kernel32.WriteFile(
                    ctypes.c_void_p(self._windows_pipe_handle()),
                    buffer,
                    len(chunk),
                    ctypes.byref(transferred),
                    None,
                ):
                    raise OSError(ctypes.get_last_error(), "WriteFile failed for native pipe")
                if transferred.value == 0:
                    raise EOFError("native pipe closed")
                offset += transferred.value

    def _windows_bytes_available(self) -> int:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        available = ctypes.c_ulong()
        with self._windows_io_lock:
            if not kernel32.PeekNamedPipe(
                ctypes.c_void_p(self._windows_pipe_handle()),
                None,
                0,
                None,
                ctypes.byref(available),
                None,
            ):
                error = ctypes.get_last_error()
                if error in {109, 232}:
                    raise EOFError("native pipe closed")
                raise OSError(error, "PeekNamedPipe failed for native pipe")
        return int(available.value)

    @staticmethod
    def _decode_payload(frame: Frame) -> dict[str, Any]:
        if not frame.payload:
            return {"ok": True}
        if frame.message_type == MessageType.RESULT:
            return {"ok": True, "text": frame.payload.decode("utf-8", errors="replace")}
        try:
            value = json.loads(frame.payload.decode("utf-8"))
            return value if isinstance(value, dict) else {"value": value}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": True, "text": frame.payload.decode("utf-8", errors="replace")}

    @staticmethod
    def _parse_native_event(request_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        if request_id != 0xFFFFFFFFFFFFFFFF:
            return None
        text = data.get("text")
        if not isinstance(text, str):
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict):
            return None
        topic = value.pop("native_event", None)
        return {"type": topic, **value} if isinstance(topic, str) and topic else None


class OmniWorkerManager:
    """拥有一个原生 Worker 和事件泵；失败时不执行后端回退。"""

    def __init__(
        self,
        *,
        client: NativeOmniClient | None = None,
        worker_path: Path | None = None,
        model_root: Path | None = None,
        pipe_name: str | None = None,
        process_factory: Callable[..., Any] = subprocess.Popen,
        wait_for_pipe: Callable[..., Any] | None = None,
        event_sink: Callable[[dict[str, Any]], Any] | None = None,
        startup_timeout: float = 600.0,
    ) -> None:
        self.worker_path = Path(worker_path or local_omni.resolve_worker_path())
        self.model_root = Path(model_root or local_omni.resolve_model_root())
        self.pipe_name = pipe_name or str(
            os.environ.get("PA_NATIVE_PIPE_NAME")
            or config.get("local_omni.pipe_name", r"\\.\pipe\PersonalAssistant.Omni.v1")
        )
        self.startup_timeout = startup_timeout
        self.client = client or NamedPipeOmniClient(
            self.pipe_name,
            timeout=float(config.get("local_omni.request_timeout_seconds", 600)),
        )
        self.process_factory = process_factory
        self.wait_for_pipe = wait_for_pipe or self._wait_for_pipe
        self.event_sink = event_sink
        self.process: Any = None
        self._pump_task: asyncio.Task[None] | None = None
        self.running = False

    async def start(self) -> None:
        if self.running:
            return
        if not self.worker_path.is_file():
            raise RuntimeError(f"native worker executable not found: {self.worker_path}")
        verify_hashes = bool(config.get("local_omni.verify_hashes", True))
        if not local_omni.model_files_are_valid(self.model_root, verify_hashes=verify_hashes):
            raise RuntimeError(f"model files are missing or invalid: {self.model_root}")
        if not local_omni.model_marker_is_valid(self.model_root):
            raise RuntimeError(f"model marker is missing or invalid: {self.model_root}")
        try:
            worker_environment = os.environ.copy()
            reference_audio = self.worker_path.parent / "default_ref_audio.wav"
            if reference_audio.is_file():
                worker_environment["JARVIS_REF_AUDIO_PATH"] = str(reference_audio.resolve())
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = self.process_factory(
                [str(self.worker_path), self.pipe_name, str(self.model_root)],
                cwd=str(self.model_root.parent),
                env=worker_environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            result = self.wait_for_pipe(self.process, self.pipe_name, self.startup_timeout)
            if asyncio.iscoroutine(result):
                await result
            await self.client.start()
            self.running = True
            self._pump_task = asyncio.create_task(self._pump_events(), name="pa-omni-event-pump")
        except Exception:
            await self._terminate_process()
            raise

    async def stop(self) -> None:
        if not self.running and self.process is None:
            return
        self.running = False
        await self.client.stop()
        if self._pump_task:
            with suppress(asyncio.CancelledError):
                await self._pump_task
            self._pump_task = None
        await self._terminate_process()

    async def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.running:
            raise RuntimeError("local MiniCPM-o worker is not running")
        return await self.client.request(method, payload)

    async def _pump_events(self) -> None:
        async for event in self.client.events():
            if self.event_sink is None:
                continue
            result = self.event_sink(event)
            if asyncio.iscoroutine(result):
                await result

    async def _terminate_process(self) -> None:
        process, self.process = self.process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            await asyncio.to_thread(process.wait, 5)
        except (subprocess.TimeoutExpired, TimeoutError):
            process.kill()
            await asyncio.to_thread(process.wait)

    @staticmethod
    async def _wait_for_pipe(process: Any, pipe_name: str, timeout: float) -> None:
        if os.name != "nt":
            raise RuntimeError("MiniCPM-o native worker requires Windows named pipes")
        wait_named_pipe = ctypes.windll.kernel32.WaitNamedPipeW
        wait_named_pipe.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"native worker exited during startup with code {process.returncode}"
                )
            if wait_named_pipe(pipe_name, 1000):
                return
            await asyncio.sleep(0.1)
        raise RuntimeError("native worker did not expose its pipe before startup timeout")
