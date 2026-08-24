from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from personal_assistant import local_omni


def _small_manifest(monkeypatch: pytest.MonkeyPatch) -> tuple[bytes, local_omni.ModelFile]:
    payload = b"portable-model"
    entry = local_omni.ModelFile(
        "vision/model.gguf", len(payload), hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(local_omni, "MODEL_FILES", (entry,))
    return payload, entry


def test_pinned_manifest_matches_jarvis_release() -> None:
    assert local_omni.MODEL_REPO_ID == "openbmb/MiniCPM-o-4_5-gguf"
    assert local_omni.MODEL_REVISION == "502eec5b03eaee9d0d2ce17a176e3490103c9a63"
    assert [(item.relative_path, item.expected_size) for item in local_omni.MODEL_FILES] == [
        ("MiniCPM-o-4_5-Q4_K_M.gguf", 5_026_714_400),
        ("vision/MiniCPM-o-4_5-vision-F16.gguf", 1_095_113_184),
        ("audio/MiniCPM-o-4_5-audio-F16.gguf", 660_167_904),
    ]
    assert local_omni.MODEL_TOTAL_BYTES == 6_781_995_488


def test_model_validation_checks_missing_size_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, entry = _small_manifest(monkeypatch)
    model = tmp_path / entry.relative_path
    assert not local_omni.model_files_are_valid(tmp_path)

    model.parent.mkdir(parents=True)
    model.write_bytes(payload + b"x")
    assert not local_omni.model_files_are_valid(tmp_path, verify_hashes=False)

    model.write_bytes(b"x" * len(payload))
    assert local_omni.model_files_are_valid(tmp_path, verify_hashes=False)
    assert not local_omni.model_files_are_valid(tmp_path, verify_hashes=True)

    model.write_bytes(payload)
    assert local_omni.model_files_are_valid(tmp_path, verify_hashes=True)


def test_model_marker_uses_pinned_revision_and_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, entry = _small_manifest(monkeypatch)
    assert not local_omni.model_marker_is_valid(tmp_path)
    local_omni.write_model_marker(tmp_path)

    assert local_omni.model_marker_is_valid(tmp_path)
    marker = json.loads((tmp_path / local_omni.MODEL_MARKER).read_text(encoding="utf-8"))
    assert marker == {
        "revision": local_omni.MODEL_REVISION,
        "files": {entry.relative_path: entry.sha256},
    }

    marker["revision"] = "moving-main"
    (tmp_path / local_omni.MODEL_MARKER).write_text(json.dumps(marker), encoding="utf-8")
    assert not local_omni.model_marker_is_valid(tmp_path)


def test_environment_paths_override_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configured_model = tmp_path / "configured-model"
    configured_worker = tmp_path / "configured-worker.exe"
    environment_model = tmp_path / "environment-model"
    environment_worker = tmp_path / "environment-worker.exe"
    monkeypatch.setattr(
        local_omni.config,
        "get",
        lambda path, default=None: {
            "local_omni.model_root": str(configured_model),
            "local_omni.worker_path": str(configured_worker),
        }.get(path, default),
    )

    assert local_omni.resolve_model_root() == configured_model
    assert local_omni.resolve_worker_path() == configured_worker

    monkeypatch.setenv("PA_LOCAL_MODEL_ROOT", str(environment_model))
    monkeypatch.setenv("PA_NATIVE_WORKER_PATH", str(environment_worker))
    assert local_omni.resolve_model_root() == environment_model
    assert local_omni.resolve_worker_path() == environment_worker

def test_download_models_pins_revision_and_writes_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, entry = _small_manifest(monkeypatch)
    calls = []

    def snapshot_download(**kwargs):
        calls.append(kwargs)
        target = Path(kwargs["local_dir"]) / entry.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    endpoint = local_omni.download_models(
        tmp_path,
        snapshot_download=snapshot_download,
        endpoints=("https://official.example/", "https://mirror.example"),
    )

    assert endpoint == "https://official.example"
    assert calls[0]["repo_id"] == local_omni.MODEL_REPO_ID
    assert calls[0]["revision"] == local_omni.MODEL_REVISION
    assert calls[0]["allow_patterns"] == [entry.relative_path]
    assert local_omni.model_marker_is_valid(tmp_path)


def test_download_models_uses_mirror_and_redacts_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, entry = _small_manifest(monkeypatch)
    token = "private-token"
    calls = []

    def snapshot_download(**kwargs):
        calls.append(kwargs["endpoint"])
        if len(calls) == 1:
            raise RuntimeError(f"rejected {token}")
        target = Path(kwargs["local_dir"]) / entry.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    endpoint = local_omni.download_models(
        tmp_path,
        token=token,
        snapshot_download=snapshot_download,
        endpoints=("https://official.example", "https://mirror.example"),
    )

    assert endpoint == "https://mirror.example"
    assert calls == ["https://official.example", "https://mirror.example"]

def test_download_models_falls_back_to_pinned_http_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, entry = _small_manifest(monkeypatch)
    calls = []

    def snapshot_download(**_kwargs):
        raise RuntimeError("xet transport failed")

    def range_downloader(url, destination, expected_size, token=None):
        calls.append((url, destination, expected_size, token))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    endpoint = local_omni.download_models(
        tmp_path,
        snapshot_download=snapshot_download,
        range_downloader=range_downloader,
        endpoints=("https://models.example",),
    )

    assert endpoint == "https://models.example"
    assert calls == [(
        "https://models.example/openbmb/MiniCPM-o-4_5-gguf/resolve/"
        f"{local_omni.MODEL_REVISION}/vision/model.gguf?download=true",
        tmp_path / entry.relative_path,
        len(payload),
        None,
    )]
    assert local_omni.model_marker_is_valid(tmp_path)

def test_download_models_uses_ranges_without_huggingface_hub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, entry = _small_manifest(monkeypatch)
    monkeypatch.setitem(__import__("sys").modules, "huggingface_hub", None)

    def range_downloader(_url, destination, _expected_size, token=None):
        assert token is None
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    assert local_omni.download_models(
        tmp_path,
        range_downloader=range_downloader,
        endpoints=("https://models.example",),
    ) == "https://models.example"


def test_range_merge_reports_wrong_size_without_masking_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def short_part(_url, destination, _start, _end, _token):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"x")
        return destination

    monkeypatch.setattr(local_omni, "_download_range_part", short_part)
    with pytest.raises(RuntimeError, match="has 1 bytes; expected 2"):
        local_omni.download_file_ranges(
            "https://models.example/model.gguf",
            tmp_path / "model.gguf",
            2,
            chunk_size=2,
            workers=1,
        )

def test_local_model_cli_status_reports_resolved_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from argparse import Namespace
    from personal_assistant import cli

    model_root = tmp_path / "models"
    worker_path = tmp_path / "worker.exe"
    monkeypatch.setattr(local_omni, "resolve_model_root", lambda: model_root)
    monkeypatch.setattr(local_omni, "resolve_worker_path", lambda: worker_path)

    cli.cmd_local_model(Namespace(action="status"))

    status = json.loads(capsys.readouterr().out)
    assert status["model_root"] == str(model_root)
    assert status["worker_path"] == str(worker_path)

def test_range_download_replaces_same_size_untrusted_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "model.gguf"
    destination.write_bytes(b"bad")
    calls = []

    def replacement(_url, part, _start, _end, _token):
        calls.append(part)
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_bytes(b"new")
        return part

    monkeypatch.setattr(local_omni, "_download_range_part", replacement)
    local_omni.download_file_ranges(
        "https://models.example/model.gguf",
        destination,
        3,
        chunk_size=3,
        workers=1,
    )

    assert calls
    assert destination.read_bytes() == b"new"

def test_range_download_removes_parts_after_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "model.gguf"

    def complete_part(_url, part, _start, _end, _token):
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_bytes(b"ok")
        return part

    monkeypatch.setattr(local_omni, "_download_range_part", complete_part)
    local_omni.download_file_ranges(
        "https://models.example/model.gguf",
        destination,
        2,
        chunk_size=2,
        workers=1,
    )

    assert destination.read_bytes() == b"ok"
    assert not destination.with_name(destination.name + ".parts").exists()

def test_download_models_reuses_fully_verified_local_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload, entry = _small_manifest(monkeypatch)
    target = tmp_path / entry.relative_path
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    local_omni.write_model_marker(tmp_path)

    def unexpected_call(**_kwargs):
        raise AssertionError("verified local model should not use network")

    assert local_omni.download_models(
        tmp_path,
        snapshot_download=unexpected_call,
        range_downloader=unexpected_call,
    ) == "local-cache"
