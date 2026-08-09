from __future__ import annotations

import asyncio
import threading
import time

from personal_assistant.omni_service import OmniService


class SlowManager:
    def __init__(self):
        self.running = False
        self.starts = 0
        self.stops = 0

    async def start(self) -> None:
        self.starts += 1
        await asyncio.sleep(0.05)
        self.running = True

    async def stop(self) -> None:
        self.stops += 1
        self.running = False

    async def request(self, method, payload):
        return {"method": method, "payload": payload}


def test_concurrent_start_creates_one_worker_manager() -> None:
    managers: list[SlowManager] = []
    barrier = threading.Barrier(3)

    def factory(_sink):
        manager = SlowManager()
        managers.append(manager)
        return manager

    service = OmniService(manager_factory=factory)
    results = []
    errors = []

    def start() -> None:
        barrier.wait()
        try:
            results.append(service.start_sync())
        except Exception as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)

    threads = [threading.Thread(target=start) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)

    try:
        assert not errors
        assert len(results) == 2
        assert len(managers) == 1
        assert managers[0].starts == 1
        assert all(result["state"] == "ready" for result in results)
    finally:
        service.stop_sync()

def test_worker_fatal_event_marks_service_failed() -> None:
    service = OmniService()
    service._state = "ready"

    asyncio.run(service._emit({"type": "worker.fatal", "error": "pipe lost"}))

    assert service.status() == {
        "state": "failed",
        "error": "pipe lost",
        "running": False,
        "consumers": [],
    }

def test_request_does_not_auto_restart_failed_worker() -> None:
    factory_calls = []
    service = OmniService(manager_factory=lambda sink: factory_calls.append(sink))
    service._state = "failed"
    service._error = "pipe lost"

    try:
        service.request_sync("ask", {"text": "hello"})
    except RuntimeError as exc:
        assert str(exc) == "local MiniCPM-o worker failed: pipe lost"
    else:  # pragma: no cover - assertion path
        raise AssertionError("failed worker request unexpectedly restarted")
    assert factory_calls == []

def test_explicit_start_cleans_failed_manager_before_recovery() -> None:
    old_manager = SlowManager()
    new_manager = SlowManager()
    service = OmniService(manager_factory=lambda _sink: new_manager)
    service._manager = old_manager
    service._state = "failed"
    service._error = "pipe lost"
    service._ensure_loop()

    try:
        status = service.start_sync()
        assert status["state"] == "ready"
        assert old_manager.stops == 1
        assert new_manager.starts == 1
    finally:
        service.stop_sync()
