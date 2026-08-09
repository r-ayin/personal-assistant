"""conftest.py — 测试默认后端：stub（离线、确定性、零网络）。

裸 `python -m pytest`（Stop gate/CI 等无人值守场景）不依赖调用方设置环境变量。
显式覆盖仍然有效（如 PA_LLM_BACKEND=anthropic_proxy 跑真 LLM）：
仅未设置时填充；config.load_env() 用 setdefault，环境变量优先于 .env。
"""
import os

_STUB_DEFAULTS = {
    "PA_LLM_BACKEND": "stub",
    "PA_ASR_BACKEND": "stub",
    "PA_SPEAKER_BACKEND": "text",
    "PA_EMBEDDER": "hashing",
}
for _k, _v in _STUB_DEFAULTS.items():
    os.environ.setdefault(_k, _v)
