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
    return cfg


CONFIG = load_config()


def get(path: str, default=None):
    """点分路径取配置：get('llm.backend')."""
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
