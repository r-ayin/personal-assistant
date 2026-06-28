"""config.py — 加载 .env + config/default.json，${VAR} 替换，零三方依赖。"""
from __future__ import annotations
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "default.json"
ENV_PATH = ROOT / ".env"


def load_env(path: Path = ENV_PATH) -> None:
    """极简 .env 解析：KEY=VALUE，已存在的环境变量不覆盖。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def _substitute(value, env: dict[str, str]):
    if isinstance(value, str):
        out = value
        for _ in range(10):  # 嵌套替换上限
            changed = False
            for k, v in env.items():
                token = "${" + k + "}"
                if token in out:
                    out = out.replace(token, v if v is not None else "")
                    changed = True
            if not changed:
                break
        return out
    if isinstance(value, dict):
        return {k: _substitute(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, env) for v in value]
    return value


def load_config(path: Path = CONFIG_PATH) -> dict:
    load_env()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg = _substitute(cfg, dict(os.environ))
    # 环境覆盖后端选择（便于不改动 default.json 临时切换）
    for env_key, section in (("PA_LLM_BACKEND", "llm"), ("PA_ASR_BACKEND", "asr"),
                             ("PA_EMBEDDER", "embedder")):
        val = os.environ.get(env_key)
        if val and section in cfg:
            cfg[section]["backend"] = val
    # 环境覆盖 LLM 5 旋钮（注入当前激活后端，与 PA_LLM_BACKEND 同模式）
    backend = cfg.get("llm", {}).get("backend")
    if backend and isinstance(cfg.get("llm", {}).get(backend), dict):
        for env_key, field, cast in (("PA_LLM_MODEL", "model", str),
                                     ("PA_LLM_BASE_URL", "base_url", str),
                                     ("PA_LLM_API_KEY", "api_key", str),
                                     ("PA_LLM_MAX_TOKENS", "max_tokens", int),
                                     ("PA_LLM_THINKING", "thinking_effort", str),
                                     ("PA_LLM_THINKING_FORMAT", "thinking_format", str)):
            val = os.environ.get(env_key)
            if val:
                try:
                    cfg["llm"][backend][field] = cast(val)
                except (ValueError, TypeError):
                    cfg["llm"][backend][field] = val
    return cfg


CONFIG = load_config()


# ── 运行态覆盖层（供 POST /settings/llm 写、get_llm() 读）──────────
_RUNTIME: dict[str, object] = {}


def set_override(path: str, value) -> None:
    """写运行态覆盖（点分路径，如 'llm.openai_compat.model'）。"""
    _RUNTIME[path] = value


def set_overrides(items: dict) -> None:
    """批量写覆盖。"""
    _RUNTIME.update(items)


def clear_override(path: str | None = None) -> None:
    if path:
        _RUNTIME.pop(path, None)
    else:
        _RUNTIME.clear()


def overrides() -> dict:
    """返回当前运行态覆盖快照（api_key 明文由调用方负责掩码）。"""
    return dict(_RUNTIME)


def get(path: str, default=None):
    """点分路径取配置：get('llm.backend')。先查运行态覆盖，再查 CONFIG。"""
    if path in _RUNTIME:
        return _RUNTIME[path]
    cur = CONFIG
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def sqlite_path() -> Path:
    return ROOT / get("storage.sqlite_path", "data/db/personal_assistant.db")


def duckdb_path() -> Path:
    return ROOT / get("storage.duckdb_path", "data/db/analytics.duckdb")


def persona_path() -> Path:
    return ROOT / get("distill.profile_path", "data/persona/profile.json")


def inbox_dir() -> Path:
    return ROOT / "data" / "inbox"


def ensure_dirs() -> None:
    for p in [sqlite_path().parent, duckdb_path().parent, persona_path().parent, inbox_dir()]:
        p.mkdir(parents=True, exist_ok=True)
