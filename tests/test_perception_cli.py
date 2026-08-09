from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from personal_assistant import cli, config


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_perception_start_posts_to_pa_api_with_bearer(monkeypatch, capsys) -> None:
    requests: list[urllib.request.Request] = []

    def urlopen(request, *, timeout):
        assert timeout == 30
        requests.append(request)
        return FakeResponse({"perception": "running"})

    monkeypatch.setenv("PA_API_URL", "http://127.0.0.1:9000/")
    monkeypatch.setenv("PA_API_TOKEN", "secret-token")
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    cli.main(["perception", "start"])

    request = requests[0]
    assert request.full_url == "http://127.0.0.1:9000/perception/start"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert json.loads(capsys.readouterr().out) == {"perception": "running"}


def test_perception_stop_accepts_explicit_server_and_token(monkeypatch) -> None:
    requests: list[urllib.request.Request] = []

    def urlopen(request, *, timeout):
        assert timeout == 30
        requests.append(request)
        return FakeResponse({"perception": "stopped"})

    monkeypatch.delenv("PA_API_URL", raising=False)
    monkeypatch.delenv("PA_API_TOKEN", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    cli.main([
        "perception", "stop",
        "--base-url", "http://localhost:8015",
        "--token", "explicit-token",
    ])

    request = requests[0]
    assert request.full_url == "http://localhost:8015/perception/stop"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer explicit-token"


def test_perception_control_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("PA_API_TOKEN", raising=False)
    monkeypatch.setattr(config, "api_token", lambda: "")

    with pytest.raises(SystemExit, match="PA_API_TOKEN"):
        cli.main(["perception", "start"])


def test_perception_http_error_reports_server_detail(monkeypatch) -> None:
    monkeypatch.setenv("PA_API_TOKEN", "secret-token")

    def urlopen(_request, *, timeout):
        assert timeout == 30
        raise urllib.error.HTTPError(
            "http://127.0.0.1:8004/perception/start",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"detail":"model files are missing"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    with pytest.raises(SystemExit, match="model files are missing"):
        cli.main(["perception", "start"])

def test_perception_windows_wrapper_is_cmd_compatible_and_forwards_arguments() -> None:
    wrapper = config.ROOT / "pa-perception.bat"
    raw = wrapper.read_bytes()
    assert raw.startswith(b"@echo off\r\n")
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode("utf-8")
    assert "chcp 65001 >nul" in text
    assert "python -m personal_assistant.cli perception %*" in text
