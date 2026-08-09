"""test_real_backends.py — 真实 ASR/声纹后端可加载性测试。

仅在有 CUDA + 模型/依赖可用时运行；否则自动 skip。
不依赖网络，不污染其他测试。
"""
from __future__ import annotations
import os
import pytest


@pytest.mark.skipif(os.environ.get("PA_SKIP_REAL_BACKENDS"), reason="PA_SKIP_REAL_BACKENDS set")
def test_faster_whisper_can_load():
    """验证 faster-whisper 后端能 lazy import 并加载模型。"""
    try:
        from faster_whisper import WhisperModel
        import torch
    except ImportError as e:
        pytest.skip(f"dependency missing: {e}")
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")
    model = WhisperModel("small", device="cuda", compute_type="float16")
    assert model is not None


@pytest.mark.skipif(os.environ.get("PA_SKIP_REAL_BACKENDS"), reason="PA_SKIP_REAL_BACKENDS set")
def test_pyannote_can_load():
    """验证 pyannote.audio 能 import（不实际加载模型，避免无 HF token 时失败）。"""
    try:
        from pyannote.audio import Pipeline
    except ImportError as e:
        pytest.skip(f"dependency missing: {e}")
    assert Pipeline is not None


def test_speaker_backend_env_override():
    """验证 PA_SPEAKER_BACKEND 环境覆盖生效。"""
    from personal_assistant import config
    import os
    old = os.environ.get("PA_SPEAKER_BACKEND")
    os.environ["PA_SPEAKER_BACKEND"] = "pyannote"
    try:
        cfg = config.load_config()
        assert cfg["speaker"]["backend"] == "pyannote"
    finally:
        if old is None:
            os.environ.pop("PA_SPEAKER_BACKEND", None)
        else:
            os.environ["PA_SPEAKER_BACKEND"] = old
