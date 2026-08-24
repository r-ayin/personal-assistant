"""MiniCPM-o 4.5 本地模型清单与路径解析。"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
import time
import urllib.request
from urllib.parse import quote

from . import config

MODEL_REPO_ID = "openbmb/MiniCPM-o-4_5-gguf"
MODEL_REVISION = "502eec5b03eaee9d0d2ce17a176e3490103c9a63"
MODEL_MARKER = ".pa-minicpm-o-model.json"


@dataclass(frozen=True, slots=True)
class ModelFile:
    relative_path: str
    expected_size: int
    sha256: str


MODEL_FILES = (
    ModelFile(
        "MiniCPM-o-4_5-Q4_K_M.gguf",
        5_026_714_400,
        "1237a97ee081b8abebc47aa7dad565701e8f5f904cdc92f6723ac4281bbc0932",
    ),
    ModelFile(
        "vision/MiniCPM-o-4_5-vision-F16.gguf",
        1_095_113_184,
        "1453678cc4e4fe18de241952962e234f265cb8dda780773526103ab8ba82f421",
    ),
    ModelFile(
        "audio/MiniCPM-o-4_5-audio-F16.gguf",
        660_167_904,
        "d5b188ac7feaf98e17175c3f9bd14bf269301bfd187439fdaa3e3a494fc32ef7",
    ),
)
MODEL_TOTAL_BYTES = sum(item.expected_size for item in MODEL_FILES)


def _configured_path(env_key: str, config_key: str, default: str) -> Path:
    raw = os.environ.get(env_key) or str(config.get(config_key, default))
    path = Path(raw).expanduser()
    return path if path.is_absolute() else config.ROOT / path


def resolve_model_root() -> Path:
    return _configured_path(
        "PA_LOCAL_MODEL_ROOT", "local_omni.model_root", "data/models/MiniCPM-o-4_5-gguf"
    )


def resolve_worker_path() -> Path:
    return _configured_path(
        "PA_NATIVE_WORKER_PATH", "local_omni.worker_path", "native/jarvis-native-worker.exe"
    )


def model_files_are_valid(local_dir: Path, *, verify_hashes: bool = True) -> bool:
    root = Path(local_dir)
    for item in MODEL_FILES:
        path = root / Path(item.relative_path)
        try:
            if not path.is_file() or path.stat().st_size != item.expected_size:
                return False
            if verify_hashes:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                        digest.update(block)
                if digest.hexdigest() != item.sha256:
                    return False
        except OSError:
            return False
    return True


def _marker_value() -> dict[str, object]:
    return {
        "revision": MODEL_REVISION,
        "files": {item.relative_path: item.sha256 for item in MODEL_FILES},
    }

def _download_range_part(
    url: str,
    destination: Path,
    start: int,
    end: int,
    token: str | None,
    retries: int = 12,
) -> Path:
    expected_size = end - start + 1
    if destination.is_file() and destination.stat().st_size == expected_size:
        return destination
    headers = {"Range": f"bytes={start}-{end}", "User-Agent": "personal-assistant/1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(1, retries + 1):
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                content_range = response.headers.get("Content-Range", "")
                if response.status != 206 or not content_range.startswith(f"bytes {start}-{end}/"):
                    raise RuntimeError(
                        f"invalid range response for bytes {start}-{end}: "
                        f"HTTP {response.status}, Content-Range {content_range!r}"
                    )
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(block)
            if temporary.stat().st_size != expected_size:
                raise RuntimeError(
                    f"range bytes {start}-{end} returned {temporary.stat().st_size} bytes; "
                    f"expected {expected_size}"
                )
            temporary.replace(destination)
            return destination
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == retries:
                raise
            time.sleep(min(attempt * 3, 30))
    raise AssertionError("unreachable")


def download_file_ranges(
    url: str,
    destination: Path,
    expected_size: int,
    token: str | None = None,
    *,
    chunk_size: int = 32 * 1024 * 1024,
    workers: int = 6,
) -> None:
    """以固定 Range 分片下载大文件，保留已完成分片并原子合并。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    parts_root = destination.with_name(destination.name + ".parts")
    parts_root.mkdir(parents=True, exist_ok=True)
    ranges = [
        (index, start, min(start + chunk_size, expected_size) - 1)
        for index, start in enumerate(range(0, expected_size, chunk_size))
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as executor:
        futures = [
            executor.submit(
                _download_range_part,
                url,
                parts_root / f"{index:05d}.part",
                start,
                end,
                token,
            )
            for index, start, end in ranges
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    temporary = destination.with_suffix(destination.suffix + ".complete")
    with temporary.open("wb") as output:
        for index, _start, _end in ranges:
            with (parts_root / f"{index:05d}.part").open("rb") as source:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    output.write(block)
    actual_size = temporary.stat().st_size
    if actual_size != expected_size:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"merged model file has {actual_size} bytes; expected {expected_size}"
        )
    temporary.replace(destination)
    shutil.rmtree(parts_root)


def download_models(
    local_dir: Path | None = None,
    *,
    token: str | None = None,
    snapshot_download=None,
    endpoints: tuple[str, ...] = ("https://huggingface.co", "https://hf-mirror.com"),
    range_downloader=None,
) -> str:
    """下载固定 revision 的三个权重并校验；官方源失败后才切镜像。"""
    if snapshot_download is None:
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            snapshot_download = None
    root = Path(local_dir or resolve_model_root())
    if model_marker_is_valid(root) and model_files_are_valid(root, verify_hashes=True):
        return "local-cache"
    root.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    normalized_endpoints: list[str] = []
    for endpoint in endpoints:
        normalized = endpoint.strip().rstrip("/")
        if normalized and normalized not in normalized_endpoints:
            normalized_endpoints.append(normalized)
    if not normalized_endpoints:
        raise ValueError("at least one model download endpoint is required")
    if snapshot_download is not None:
        for endpoint in normalized_endpoints:
            try:
                snapshot_download(
                    repo_id=MODEL_REPO_ID,
                    revision=MODEL_REVISION,
                    local_dir=str(root),
                    allow_patterns=[item.relative_path for item in MODEL_FILES],
                    token=token or None,
                    endpoint=endpoint,
                    etag_timeout=30,
                )
                if not model_files_are_valid(root, verify_hashes=True):
                    raise RuntimeError("downloaded MiniCPM-o files failed size or SHA-256 validation")
                write_model_marker(root)
                return endpoint
            except Exception as exc:
                detail = str(exc)
                if token:
                    detail = detail.replace(token, "[redacted]")
                failures.append(detail)
    if range_downloader is None:
        range_downloader = download_file_ranges
    for endpoint in normalized_endpoints:
        try:
            for item in MODEL_FILES:
                encoded_path = quote(item.relative_path, safe="/")
                url = (
                    f"{endpoint}/{MODEL_REPO_ID}/resolve/{MODEL_REVISION}/"
                    f"{encoded_path}?download=true"
                )
                range_downloader(
                    url,
                    root / item.relative_path,
                    item.expected_size,
                    token=token,
                )
            if not model_files_are_valid(root, verify_hashes=True):
                raise RuntimeError("range-downloaded MiniCPM-o files failed SHA-256 validation")
            write_model_marker(root)
            return endpoint
        except Exception as exc:
            detail = str(exc)
            if token:
                detail = detail.replace(token, "[redacted]")
            failures.append(detail)
    raise RuntimeError("all MiniCPM-o download endpoints failed: " + failures[-1])


def model_marker_is_valid(local_dir: Path) -> bool:
    try:
        value = json.loads((Path(local_dir) / MODEL_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return value == _marker_value()


def write_model_marker(local_dir: Path) -> None:
    root = Path(local_dir)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / MODEL_MARKER
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(_marker_value(), indent=2), encoding="utf-8")
    temporary.replace(destination)
