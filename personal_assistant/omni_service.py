"""MiniCPM-o Worker 的进程级运行服务。"""
from __future__ import annotations

import asyncio
import threading
from threading import RLock
from typing import Any, Callable

from .native_omni import OmniWorkerManager


class OmniService:
    """在专用事件循环中拥有 Worker，给同步 PA LLM 提供安全桥接。"""

    def __init__(self, manager_factory: Callable[[Callable], Any] | None = None) -> None:
        self.manager_factory = manager_factory or (
            lambda sink: OmniWorkerManager(event_sink=sink)
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._manager: Any = None
        self._state = "stopped"
        self._error = ""
        self._lock = RLock()
        self._lifecycle_lock = RLock()
        self._event_sinks: list[Callable[[dict[str, Any]], Any]] = []
        self._consumers: set[str] = set()

    def add_event_sink(self, sink: Callable[[dict[str, Any]], Any]) -> None:
        with self._lock:
            if sink not in self._event_sinks:
                self._event_sinks.append(sink)

    async def _emit(self, event: dict[str, Any]) -> None:
        if event.get("type") == "worker.fatal":
            with self._lock:
                if self._state not in {"stopped", "stopping"}:
                    self._state = "failed"
                    self._error = str(event.get("error") or "local MiniCPM-o worker failed")
                    if self._manager is not None:
                        self._manager.running = False
        with self._lock:
            sinks = list(self._event_sinks)
        for sink in sinks:
            result = sink(event)
            if asyncio.iscoroutine(result):
                await result

    def status(self) -> dict[str, Any]:
        with self._lock:
            manager = self._manager
            return {
                "state": self._state,
                "error": self._error,
                "running": bool(manager and getattr(manager, "running", False)),
                "consumers": sorted(self._consumers),
            }

    def start_sync(self) -> dict[str, Any]:
        with self._lifecycle_lock:
            if self._state == "failed" and self._loop and self._manager:
                try:
                    self._submit(self._manager.stop(), timeout=30)
                except Exception as exc:
                    with self._lock:
                        self._error = f"failed to clean previous worker: {exc}"
                    raise RuntimeError(self._error) from exc
                self._manager = None
            with self._lock:
                if self._state == "ready":
                    return self.status()
                self._state = "starting"
                self._error = ""
            self._ensure_loop()
            try:
                self._submit(self._start(), timeout=620)
            except Exception as exc:
                if self._loop and self._manager:
                    try:
                        self._submit(self._manager.stop(), timeout=30)
                    except Exception:
                        pass
                self._manager = None
                with self._lock:
                    self._state = "failed"
                    self._error = str(exc)
                self._stop_loop()
                raise
            with self._lock:
                self._state = "ready"
            return self.status()

    async def _start(self) -> None:
        self._manager = self.manager_factory(self._emit)
        await self._manager.start()

    def stop_sync(self) -> dict[str, Any]:
        with self._lifecycle_lock:
            with self._lock:
                self._consumers.clear()
                if self._state == "stopped":
                    return self.status()
                self._state = "stopping"
            try:
                if self._loop and self._manager:
                    self._submit(self._manager.stop(), timeout=30)
            finally:
                self._manager = None
                self._stop_loop()
                with self._lock:
                    self._state = "stopped"
                    self._error = ""
            return self.status()

    def consumers(self) -> list[str]:
        with self._lock:
            return sorted(self._consumers)

    def acquire_sync(self, owner: str) -> dict[str, Any]:
        owner = owner.strip()
        if not owner:
            raise ValueError("consumer owner must not be empty")
        with self._lifecycle_lock:
            with self._lock:
                if owner in self._consumers and self._state == "ready":
                    return self.status()
                self._consumers.add(owner)
            try:
                return self.start_sync()
            except Exception:
                with self._lock:
                    self._consumers.discard(owner)
                self.stop_sync()
                raise

    def release_sync(self, owner: str) -> dict[str, Any]:
        with self._lifecycle_lock:
            with self._lock:
                self._consumers.discard(owner)
                has_consumers = bool(self._consumers)
            if has_consumers:
                return self.status()
            return self.stop_sync()

    def request_sync(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        status = self.status()
        if status["state"] == "stopped":
            raise RuntimeError("local MiniCPM-o worker has no active consumer")
        if status["state"] != "ready":
            detail = f": {status['error']}" if status["error"] else ""
            raise RuntimeError(f"local MiniCPM-o worker {status['state']}{detail}")
        timeout = max(0.1, min(600.0, float(payload.get("_timeout_seconds", 600))))
        try:
            return self._submit(self._manager.request(method, payload), timeout=timeout + 1)
        except FutureTimeoutError as exc:
            raise RuntimeError("local MiniCPM-o request timed out") from exc

    def _ensure_loop(self) -> None:
        if self._loop and self._thread and self._thread.is_alive():
            return
        ready = threading.Event()

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            ready.set()
            loop.run_forever()
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

        self._thread = threading.Thread(target=run, name="pa-omni-runtime", daemon=True)
        self._thread.start()
        if not ready.wait(5):
            raise RuntimeError("local MiniCPM-o event loop failed to start")

    def _submit(self, coroutine, *, timeout: float):
        loop = self._loop
        if loop is None or not loop.is_running():
            raise RuntimeError("local MiniCPM-o service loop is not running")
        return asyncio.run_coroutine_threadsafe(coroutine, loop).result(timeout=timeout)

    def _stop_loop(self) -> None:
        loop, thread = self._loop, self._thread
        self._loop = None
        self._thread = None
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5)


_SERVICE: OmniService | None = None
_SERVICE_LOCK = threading.Lock()


def get_omni_service() -> OmniService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = OmniService()
        return _SERVICE
