"""test_audio_upload.py — 固件录音上传链路（/ws/audio → RMS VAD → WAV → inbox → 摄入）。

v0.12 纯文字化后，固件只保留「录音 + 上传」，服务器端链路为：
  PCM 帧（type=0，Byte0=类型，1+ = 16kHz 16bit mono）→ RMS VAD 切段
  → WAV 落 inbox（bg-*.wav）→ scan_inbox 转写摄入。
本测试覆盖：鉴权、VAD 切段落盘、WAV 摄入三步。
"""
from __future__ import annotations

import math
import struct

from fastapi.testclient import TestClient

from personal_assistant import api, config, ingest


def _pcm_sine(ms: int, freq: float = 440.0, amp: int = 9000) -> bytes:
    """指定时长的正弦波（16kHz 16bit mono），幅度远超 VAD 阈值 350。"""
    n = int(16000 * ms / 1000)
    return b"".join(
        struct.pack("<h", int(amp * math.sin(2 * math.pi * freq * i / 16000)))
        for i in range(n)
    )


def _pcm_silence(ms: int) -> bytes:
    return b"\x00\x00" * int(16000 * ms / 1000)


def test_ws_audio_pcm_frames_land_as_wav(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "inbox_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "api_token", lambda: "audio-test-token")

    client = TestClient(api.app)
    loud = _pcm_sine(100)      # 100ms 响帧
    quiet = _pcm_silence(100)  # 100ms 静音帧

    with client.websocket_connect("/ws/audio?token=audio-test-token") as ws:
        for _ in range(8):     # 800ms 语音（> min_utt 300ms）
            ws.send_bytes(b"\x00" + loud)
        for _ in range(10):    # 1000ms 静音（> holdout 500ms）触发切段
            ws.send_bytes(b"\x00" + quiet)
        ws.send_bytes(b"\x01")  # segment_end flush

    wavs = list(tmp_path.glob("bg-*.wav"))
    assert wavs, "VAD 切段后应有 WAV 文件落入 inbox"
    assert wavs[0].stat().st_size > 44, "WAV 应含有效数据（>44 字节头）"


def test_ws_audio_rejects_bad_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "inbox_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "api_token", lambda: "audio-test-token")

    client = TestClient(api.app)
    closed = False
    try:
        with client.websocket_connect("/ws/audio?token=wrong-token") as ws:
            ws.receive_bytes()
    except Exception:
        closed = True
    assert closed, "错误 token 的 WS 握手应被拒绝（1008 关闭）"


def test_inbox_upload_neutralizes_path_traversal(tmp_path, monkeypatch) -> None:
    """红队回归：../../ 文件名不得逃出 inbox（basename + 白名单 + resolve 容器校验）。"""
    monkeypatch.setattr(config, "inbox_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "api_token", lambda: "up-test-token")

    client = TestClient(api.app)
    headers = {"Authorization": "Bearer up-test-token"}
    r = client.post("/inbox/upload?filename=../../escape-traversal.txt",
                    content=b"x", headers=headers)
    outside = tmp_path.parent.parent / "escape-traversal.txt"
    try:
        assert not outside.exists(), "路径穿越文件不得落在 inbox 之外"
        if r.status_code == 200:
            body = r.json()
            assert ".." not in body["saved"]
            assert (tmp_path / "escape-traversal.txt").exists()
    finally:
        if outside.exists():
            outside.unlink()


def test_uploaded_wav_is_ingested(tmp_path, monkeypatch) -> None:
    """WAV 落 inbox 后，scan_inbox 能摄入（转写走 stub 后端）。"""
    monkeypatch.setattr(config, "inbox_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "sqlite_path", lambda: tmp_path / "pa.db")
    monkeypatch.setattr(config, "duckdb_path", lambda: tmp_path / "pa.duckdb")
    monkeypatch.setattr(config, "persona_path", lambda: tmp_path / "profile.json")

    # 直接走服务器的 WAV 保存函数（与 /ws/audio 同一入口；async）
    import asyncio
    pcm = _pcm_sine(500)
    name = asyncio.run(api._save_bg_segment(pcm, tmp_path, "esp32-test"))
    assert name and (tmp_path / name).exists()

    r = ingest.scan_inbox()
    assert r.get("files", 0) >= 1, f"含 WAV 的 inbox 应被摄入: {r}"
