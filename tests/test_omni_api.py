from __future__ import annotations

from fastapi.testclient import TestClient

from personal_assistant import api, config


class FakeService:
    def __init__(self):
        self.state = "stopped"
        self.calls: list[tuple[str, dict]] = []
        self.owners: set[str] = set()

    def status(self):
        return {
            "state": self.state,
            "running": self.state == "ready",
            "error": "",
            "consumers": sorted(self.owners),
        }

    def start_sync(self):
        self.state = "ready"
        return self.status()

    def stop_sync(self):
        self.state = "stopped"
        self.owners.clear()
        return self.status()

    def acquire_sync(self, owner):
        self.owners.add(owner)
        self.state = "ready"
        return self.status()

    def release_sync(self, owner):
        self.owners.discard(owner)
        if not self.owners:
            self.state = "stopped"
        return self.status()

    def consumers(self):
        return sorted(self.owners)

    def request_sync(self, method, payload):
        if self.state != "ready":
            raise RuntimeError("worker is not ready")
        self.calls.append((method, payload))
        return {"ok": True}



def _auth_headers():
    return {"Authorization": "Bearer omni-test-token"}


def test_local_model_and_perception_control_endpoints(monkeypatch) -> None:
    service = FakeService()
    monkeypatch.setattr(api, "get_omni_service", lambda: service)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)

    with TestClient(api.app) as client:
        assert client.get("/local-model/status", headers=_auth_headers()).json()["state"] == "stopped"
        assert client.post("/local-model/start", headers=_auth_headers()).json()["state"] == "ready"
        assert service.consumers() == ["manual"]
        assert client.post("/perception/start", headers=_auth_headers()).json()["perception"] == "running"
        assert service.calls[-1] == ("start_monitoring", {})
        assert service.consumers() == ["manual", "perception"]
        assert client.post("/perception/stop", headers=_auth_headers()).json()["perception"] == "stopped"
        assert service.calls[-1] == ("stop_monitoring", {})
        assert service.state == "ready"
        assert service.consumers() == ["manual"]
        assert client.post("/local-model/stop", headers=_auth_headers()).json()["state"] == "stopped"
def test_local_model_control_requires_bearer(monkeypatch) -> None:
    monkeypatch.setattr(api, "get_omni_service", lambda: FakeService())
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")

    with TestClient(api.app) as client:
        for path in (
            "/local-model/start",
            "/local-model/stop",
            "/perception/start",
            "/perception/stop",
        ):
            assert client.post(path).status_code == 401




def test_perception_stop_does_not_start_stopped_model(monkeypatch) -> None:
    service = FakeService()
    monkeypatch.setattr(api, "get_omni_service", lambda: service)
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")

    with TestClient(api.app) as client:
        response = client.post("/perception/stop", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["perception"] == "stopped"
    assert service.state == "stopped"
    assert service.calls == []


def test_local_model_start_failure_is_503(monkeypatch) -> None:
    class FailingService(FakeService):
        def acquire_sync(self, owner):
            raise RuntimeError("model files are missing")

    monkeypatch.setattr(api, "get_omni_service", lambda: FailingService())
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    with TestClient(api.app) as client:
        response = client.post("/local-model/start", headers=_auth_headers())
    assert response.status_code == 503
    assert response.json()["detail"] == "model files are missing"


def test_perception_stop_releases_worker_without_other_consumers(monkeypatch) -> None:
    service = FakeService()
    service.acquire_sync("perception")
    monkeypatch.setattr(api, "get_omni_service", lambda: service)
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")

    with TestClient(api.app) as client:
        response = client.post("/perception/stop", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["local_model"]["state"] == "stopped"
    assert service.calls == [("stop_monitoring", {})]


def test_minicpm_backend_lease_survives_perception_stop(monkeypatch) -> None:
    service = FakeService()
    monkeypatch.setattr(api, "get_omni_service", lambda: service)
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    config.clear_override()
    try:
        with TestClient(api.app) as client:
            selected = client.post("/settings/llm", json={"backend": "minicpm_o"}, headers=_auth_headers())
            assert selected.status_code == 200
            assert service.consumers() == ["chat-backend"]
            client.post("/perception/start", headers=_auth_headers())
            stopped = client.post("/perception/stop", headers=_auth_headers())
            assert stopped.json()["local_model"]["state"] == "ready"
            assert service.consumers() == ["chat-backend"]
            changed = client.post("/settings/llm", json={"backend": "stub"}, headers=_auth_headers())
            assert changed.status_code == 200
            assert service.state == "stopped"
    finally:
        config.clear_override()


def test_llm_settings_accept_minicpm_backend(monkeypatch) -> None:
    service = FakeService()
    monkeypatch.setattr(api, "get_omni_service", lambda: service)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    config.clear_override()
    try:
        with TestClient(api.app) as client:
            response = client.post("/settings/llm", json={"backend": "minicpm_o"}, headers=_auth_headers())
        assert response.status_code == 200
        assert response.json()["backend"] == "minicpm_o"
        assert response.json()["effective"]["local_only"] is True
    finally:
        config.clear_override()


def test_omni_event_bridge_uses_pa_event_names(monkeypatch) -> None:
    sent: list[tuple[str, dict]] = []
    derived: list[tuple[str, dict]] = []

    async def broadcast(kind, payload):
        sent.append((kind, payload))
        return 1

    async def publish(kind, payload):
        derived.append((kind, payload))
        return {"kind": kind}

    monkeypatch.setattr(api.ws_manager.manager, "broadcast", broadcast)
    monkeypatch.setattr(api.barrage, "publish", publish)
    monkeypatch.setattr(
        api.omni_processor,
        "handle",
        lambda event: [("scene_changed", {"scene": "game"}),
                       ("game_barrage", {"text": "注意威胁"})],
    )

    import asyncio
    asyncio.run(api._handle_omni_event({"type": "perception.completed"}))

    assert sent == [
        ("scene_changed", {"scene": "game"}),
        ("game_barrage", {"text": "注意威胁"}),
    ]
    assert derived == [("game_barrage", {"text": "注意威胁"})]


def test_personality_api_versions_and_previews_without_saving(tmp_path, monkeypatch) -> None:
    database = tmp_path / "personality-api.db"
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: database)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    value = {
        "preset_id": "lively",
        "name": "阿简",
        "user_address": "你",
        "directness": 3,
        "humor": 5,
        "initiative": "active",
        "reply_length": "short",
        "barrage_style": "light",
        "taboos": [],
        "custom_instruction": "",
    }

    with TestClient(api.app) as client:
        initial = client.get("/assistant/personality", headers=_auth_headers())
        assert initial.status_code == 200
        assert initial.json()["version"] == 0

        preview = client.post(
            "/assistant/personality/preview", json=value, headers=_auth_headers()
        )
        assert preview.status_code == 200
        assert set(preview.json()) == {"chat", "reminder", "perception"}
        assert client.get("/assistant/personality", headers=_auth_headers()).json()["version"] == 0

        created = client.put(
            "/assistant/personality",
            json={**value, "expected_version": 0},
            headers=_auth_headers(),
        )
        assert created.status_code == 200
        assert created.json()["version"] == 1

        stale = client.put(
            "/assistant/personality",
            json={**value, "expected_version": 0},
            headers=_auth_headers(),
        )
        assert stale.status_code == 409


def test_profile_api_exposes_inferred_effective_and_feedback(tmp_path, monkeypatch) -> None:
    database = tmp_path / "profile-api.db"
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: database)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    api.storage.save_persona_version({"preferences": ["咖啡"]}, "依据 memory:m1")

    with TestClient(api.app) as client:
        created = client.post(
            "/profile/feedback",
            json={
                "dimension": "preferences",
                "value": "茶",
                "action": "add",
                "evidence_kind": "user_statement",
                "evidence": "用户明确纠正",
            },
            headers=_auth_headers(),
        )
        assert created.status_code == 200
        profile = client.get("/profile", headers=_auth_headers()).json()
        assert profile["inferred"]["preferences"] == ["咖啡"]
        assert profile["effective"]["preferences"] == ["咖啡", "茶"]
        assert profile["version"] == 1
        assert profile["change_summary"] == "依据 memory:m1"
        assert profile["feedback"][0]["evidence"] == "用户明确纠正"

        deleted = client.delete(
            f"/profile/feedback/{created.json()['id']}", headers=_auth_headers()
        )
        assert deleted.status_code == 200
        assert deleted.json()["active"] is False


def test_profile_feedback_rejects_non_user_evidence(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: tmp_path / "invalid.db")
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)

    with TestClient(api.app) as client:
        response = client.post(
            "/profile/feedback",
            json={
                "dimension": "preferences",
                "value": "茶",
                "action": "add",
                "evidence_kind": "model_guess",
                "evidence": "猜测",
            },
            headers=_auth_headers(),
        )
    assert response.status_code == 422



def test_barrage_settings_status_and_test_event(tmp_path, monkeypatch) -> None:
    database = tmp_path / "barrage-api.db"
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: database)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    emitted: list[tuple[str, dict]] = []

    async def emit(event_type, payload):
        emitted.append((event_type, payload))
        return 1

    monkeypatch.setattr(api.barrage, "_emit", emit)
    with TestClient(api.app) as client:
        initial = client.get("/barrage/settings", headers=_auth_headers())
        assert initial.status_code == 200
        assert initial.json()["enabled"] is True
        updated = client.put(
            "/barrage/settings",
            json={"quiet_mode": True, "opacity": 0.7},
            headers=_auth_headers(),
        )
        assert updated.status_code == 200
        assert updated.json()["quiet_mode"] is True
        assert updated.json()["font_size"] == 24
        status = client.get("/barrage/status", headers=_auth_headers()).json()
        assert status["settings"]["opacity"] == 0.7
        blocked = client.post("/barrage/test", headers=_auth_headers())
        assert blocked.status_code == 409
        client.put(
            "/barrage/settings", json={"quiet_mode": False}, headers=_auth_headers()
        )
        tested = client.post("/barrage/test", headers=_auth_headers())
        assert tested.status_code == 200

    assert emitted[0][0] == "barrage"
    assert emitted[0][1]["kind"] == "test"
    assert emitted[0][1]["priority"] == "low"


def test_business_event_keeps_original_broadcast_and_derives_barrage(monkeypatch) -> None:
    broadcasts: list[tuple[str, dict]] = []
    published: list[tuple[str, dict]] = []

    async def broadcast(kind, payload):
        broadcasts.append((kind, payload))
        return 1

    async def publish(kind, payload):
        published.append((kind, payload))
        return {"kind": kind}

    monkeypatch.setattr(api.ws_manager.manager, "broadcast", broadcast)
    monkeypatch.setattr(api.barrage, "publish", publish)

    import asyncio
    asyncio.run(api._broadcast_business_event("assistant_message", {"text": "该休息一下了"}))
    asyncio.run(api._broadcast_business_event("chat_reply", {"text": "页面回复"}))

    assert broadcasts == [
        ("assistant_message", {"text": "该休息一下了"}),
        ("chat_reply", {"text": "页面回复"}),
    ]
    assert published == [("assistant_message", {"text": "该休息一下了"})]



def test_barrage_settings_update_targets_overlay_clients(tmp_path, monkeypatch) -> None:
    database = tmp_path / "barrage-settings-sync.db"
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: database)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    sent: list[tuple[str, dict, set[str] | None]] = []

    async def broadcast(kind, payload, roles=None):
        sent.append((kind, payload, roles))
        return 1

    monkeypatch.setattr(api.ws_manager.manager, "broadcast", broadcast)
    with TestClient(api.app) as client:
        response = client.put(
            "/barrage/settings",
            json={"opacity": 0.66},
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    assert sent == [("barrage_settings", response.json(), {"overlay"})]


def test_barrage_status_treats_expired_pause_as_inactive(tmp_path, monkeypatch) -> None:
    database = tmp_path / "barrage-expired-pause.db"
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: database)
    monkeypatch.setattr(api.config, "api_token", lambda: "omni-test-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    api.barrage.save_settings({
        **api.barrage.DEFAULT_SETTINGS,
        "paused_until": "2020-01-01T00:00:00+00:00",
    })

    with TestClient(api.app) as client:
        status = client.get("/barrage/status", headers=_auth_headers()).json()

    assert status["paused"] is False



def test_lifespan_acquires_chat_backend_for_persisted_minicpm(monkeypatch, tmp_path) -> None:
    service = FakeService()
    monkeypatch.setattr(api, "get_omni_service", lambda: service)
    monkeypatch.setattr(api.storage.config, "sqlite_path", lambda: tmp_path / "startup-lease.db")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    monkeypatch.setitem(api.config.CONFIG["llm"], "backend", "minicpm_o")
    api.config.clear_override()
    try:
        with TestClient(api.app):
            assert service.consumers() == ["chat-backend"]
    finally:
        api.config.clear_override()
        monkeypatch.setitem(api.config.CONFIG["llm"], "backend", "stub")

