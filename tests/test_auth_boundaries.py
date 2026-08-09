from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_assistant import auth


def test_configured_token_protects_http_and_exempts_health(monkeypatch) -> None:
    monkeypatch.delenv("PA_API_TOKEN", raising=False)
    monkeypatch.setattr(auth.config, "api_token", lambda: "config-token")
    app = FastAPI()
    app.middleware("http")(auth.auth_middleware)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/private")
    def private():
        return {"secret": True}

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/private").status_code == 401
        assert client.get(
            "/private", headers={"Authorization": "Bearer config-token"}
        ).status_code == 200
        assert client.get("/webhook").status_code == 401


def test_configured_token_protects_websocket_fallback(monkeypatch) -> None:
    monkeypatch.delenv("PA_API_TOKEN", raising=False)
    monkeypatch.setattr(auth.config, "api_token", lambda: "config-token")

    accepted_query = SimpleNamespace(
        headers={}, query_params={"token": "config-token"}
    )
    accepted_header = SimpleNamespace(
        headers={"authorization": "Bearer config-token"}, query_params={}
    )
    rejected = SimpleNamespace(headers={}, query_params={"token": "wrong"})

    assert auth.verify_ws_token(accepted_query) is True
    assert auth.verify_ws_token(accepted_header) is True
    assert auth.verify_ws_token(rejected) is False


def test_real_app_protects_data_apis_when_token_is_configured(monkeypatch) -> None:
    from personal_assistant import api

    monkeypatch.setattr(api.config, "api_token", lambda: "config-token")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    with TestClient(api.app) as client:
        assert client.get("/health").status_code == 200
        # /web/ 是静态豁免路径：已构建时返回 200；未构建时 404 而非 401，
        # 两者都证明静态资源不被 Bearer 门禁拦截。
        assert client.get("/web/").status_code in (200, 404)
        assert client.get("/segments").status_code == 401
        assert client.get(
            "/segments", headers={"Authorization": "Bearer config-token"}
        ).status_code == 200


def test_real_app_allows_local_development_without_a_token(monkeypatch) -> None:
    from personal_assistant import api

    monkeypatch.setattr(api.config, "api_token", lambda: "")
    monkeypatch.setattr(api.xiaozhi_server, "warmup_asr", lambda: None)
    with TestClient(api.app) as client:
        assert client.get("/assistant/personality").status_code == 200
