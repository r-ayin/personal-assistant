from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from typing import Any

import pytest

from personal_assistant import local_omni
from personal_assistant.native_omni import (
    HEADER,
    Frame,
    InProcessOmniClient,
    MessageType,
    NamedPipeOmniClient,
    OmniWorkerManager,
    ProtocolError,
    StatusCode,
    decode_frame,
    encode_frame,
    json_payload,
)


def test_protocol_v1_header_round_trip_is_jarvis_compatible() -> None:
    frame = Frame(
        MessageType.SUBMIT,
        request_id=0x0102030405060708,
        payload="你好，Jarvis".encode(),
        flags=StatusCode.OK,
    )

    encoded = encode_frame(frame)

    assert HEADER.size == 32
    assert encoded[:4] == struct.pack("<I", 0x56524A41)
    assert decode_frame(encoded) == frame


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda raw: raw[:-1] + bytes([raw[-1] ^ 1]), "checksum"),
        (
            lambda raw: raw[:4] + struct.pack("<H", 2) + raw[6:],
            "unsupported protocol version 2",
        ),
        (
            lambda raw: raw[:20] + struct.pack("<I", 100) + raw[24:],
            "frame length mismatch",
        ),
    ],
)
def test_protocol_rejects_crc_version_and_size_errors(mutate, message: str) -> None:
    encoded = encode_frame(Frame(MessageType.HELLO, 7, b"payload"))

    with pytest.raises(ProtocolError, match=message):
        decode_frame(mutate(encoded))


def test_protocol_enums_match_jarvis_v1() -> None:
    assert {item.name: item.value for item in MessageType} == {
        "HELLO": 1,
        "START": 2,
        "STOP": 3,
        "SUBMIT": 4,
        "CANCEL": 5,
        "RESULT": 6,
        "STATUS": 7,
        "ERROR": 8,
        "SHUTDOWN": 9,
        "CONFIGURE_GAME": 10,
        "START_DUPLEX": 11,
        "STOP_DUPLEX": 12,
    }
    assert {item.name: item.value for item in StatusCode} == {
        "OK": 0,
        "MALFORMED": 1,
        "UNSUPPORTED_VERSION": 2,
        "UNAVAILABLE": 3,
        "CANCELLED": 4,
        "INTERNAL_ERROR": 5,
    }


@pytest.mark.asyncio
async def test_explicit_fake_client_handles_requests_and_events() -> None:
    client = InProcessOmniClient()

    await client.start()
    assert await client.request("ping", {}) == {"ok": True, "result": "pong"}
    assert await client.request("ask", {"text": "hi"}) == {
        "ok": True,
        "method": "ask",
        "result": {"text": "hi"},
    }
    await client.emit({"type": "perception.changed", "value": 1})

    events = client.events()
    assert await anext(events) == {"type": "worker.ready", "inference_provider": "fake"}
    assert await anext(events) == {"type": "perception.changed", "value": 1}
    await client.stop()
    with pytest.raises(StopAsyncIteration):
        await anext(events)


def test_native_event_envelope_decodes_to_typed_event() -> None:
    envelope = json_payload(
        {"native_event": "duplex.transcript", "text": "hello", "final": True}
    ).decode()
    frame = Frame(
        MessageType.RESULT,
        request_id=0xFFFFFFFFFFFFFFFF,
        payload=envelope.encode(),
    )

    decoded = NamedPipeOmniClient._decode_payload(frame)

    assert NamedPipeOmniClient._parse_native_event(frame.request_id, decoded) == {
        "type": "duplex.transcript",
        "text": "hello",
        "final": True,
    }


@pytest.mark.asyncio
async def test_pipe_reader_failure_rejects_pending_requests(monkeypatch) -> None:
    client = NamedPipeOmniClient(r"\\.\pipe\PA.Test")
    client.running = True
    client._stream = object()
    pending = asyncio.get_running_loop().create_future()
    client._pending[7] = pending
    monkeypatch.setattr(
        client,
        "_windows_bytes_available",
        lambda: (_ for _ in ()).throw(EOFError("pipe closed")),
    )

    await client._read_loop()

    with pytest.raises(RuntimeError, match="native pipe reader stopped"):
        await pending
    assert client.running is False


@pytest.mark.asyncio
async def test_manager_reports_missing_worker_before_starting_client(tmp_path: Path) -> None:
    client = RecordingClient()
    manager = OmniWorkerManager(
        client=client,
        worker_path=tmp_path / "missing-worker.exe",
        model_root=tmp_path / "models",
    )

    with pytest.raises(RuntimeError, match="native worker executable not found"):
        await manager.start()
    assert client.starts == 0


@pytest.mark.asyncio
async def test_manager_reports_missing_model_marker_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = tmp_path / "worker.exe"
    worker.touch()
    monkeypatch.setattr(local_omni, "model_files_are_valid", lambda *_args, **_kwargs: False)
    manager = OmniWorkerManager(
        client=RecordingClient(), worker_path=worker, model_root=tmp_path / "models"
    )

    with pytest.raises(RuntimeError, match="model files are missing or invalid"):
        await manager.start()

    monkeypatch.setattr(local_omni, "model_files_are_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(local_omni, "model_marker_is_valid", lambda *_args: False)
    with pytest.raises(RuntimeError, match="model marker is missing or invalid"):
        await manager.start()


@pytest.mark.asyncio
async def test_manager_start_stop_are_idempotent_and_pump_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = tmp_path / "worker.exe"
    worker.touch()
    reference_audio = tmp_path / "default_ref_audio.wav"
    reference_audio.touch()
    model_root = tmp_path / "models"
    model_root.mkdir()
    monkeypatch.setattr(local_omni, "model_files_are_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(local_omni, "model_marker_is_valid", lambda *_args: True)
    client = RecordingClient()
    process = RecordingProcess()
    process_calls: list[tuple[list[str], dict[str, Any]]] = []
    waits: list[tuple[RecordingProcess, str, float]] = []
    received: list[dict[str, Any]] = []

    def process_factory(command: list[str], **kwargs: Any) -> RecordingProcess:
        process_calls.append((command, kwargs))
        return process

    async def wait_for_pipe(
        child: RecordingProcess, pipe_name: str, timeout: float
    ) -> None:
        waits.append((child, pipe_name, timeout))

    manager = OmniWorkerManager(
        client=client,
        worker_path=worker,
        model_root=model_root,
        pipe_name=r"\\.\pipe\PA.Test",
        process_factory=process_factory,
        wait_for_pipe=wait_for_pipe,
        event_sink=received.append,
    )

    await manager.start()
    await manager.start()
    await client.emit({"type": "worker.ready"})
    await asyncio.sleep(0)
    await manager.stop()
    await manager.stop()

    assert process_calls[0][0] == [str(worker), r"\\.\pipe\PA.Test", str(model_root)]
    assert process_calls[0][1]["env"]["JARVIS_REF_AUDIO_PATH"] == str(reference_audio.resolve())
    assert waits == [(process, r"\\.\pipe\PA.Test", manager.startup_timeout)]
    assert client.starts == 1
    assert client.stops == 1
    assert received == [{"type": "worker.ready"}]
    assert process.terminates == 1


@pytest.mark.asyncio
async def test_manager_terminates_process_when_pipe_or_client_start_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = tmp_path / "worker.exe"
    worker.touch()
    model_root = tmp_path / "models"
    model_root.mkdir()
    monkeypatch.setattr(local_omni, "model_files_are_valid", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(local_omni, "model_marker_is_valid", lambda *_args: True)
    process = RecordingProcess()

    async def failing_wait(*_args: Any) -> None:
        raise RuntimeError("pipe initialization failed")

    manager = OmniWorkerManager(
        client=RecordingClient(),
        worker_path=worker,
        model_root=model_root,
        process_factory=lambda *_args, **_kwargs: process,
        wait_for_pipe=failing_wait,
    )

    with pytest.raises(RuntimeError, match="pipe initialization failed"):
        await manager.start()
    assert process.terminates == 1


class RecordingClient(InProcessOmniClient):
    def __init__(self) -> None:
        super().__init__()
        self.starts = 0
        self.stops = 0

    async def start(self) -> None:
        self.starts += 1
        self.running = True

    async def stop(self) -> None:
        if self.running:
            self.stops += 1
        await super().stop()


class RecordingProcess:
    returncode: int | None = None

    def __init__(self) -> None:
        self.terminates = 0
        self.waits = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminates += 1
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        self.waits += 1
        return self.returncode or 0

    def kill(self) -> None:
        self.returncode = -9
