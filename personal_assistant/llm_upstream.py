"""llm_upstream.py — 全项目 LLM 上游的统一配置与一键同步。

项目里有两套互不相通的 LLM 配置，同一个上游要在两处各写一遍、写法还不一样：

  融合记忆系统（项目根 .env）
      INFO_LLM_PROVIDER / INFO_LLM_BASE_URL / INFO_LLM_KEY / INFO_LLM_MODEL
      MOMENT_LLM_BASE_URL / MOMENT_LLM_KEY / MOMENT_LLM_MODEL
      读取方：llm_client.py（时刻层、memcore/extract）、wiki_build.py（信息层）、
              cockpit-analyze.py、moment_system.py

  personal-assistant（本目录 .env + config/default.json）
      PA_LLM_BACKEND / PA_LLM_BASE_URL / PA_LLM_API_KEY / PA_LLM_MODEL
      读取方：config.load_config() 把 PA_LLM_* 注入当前激活后端的字段，
              get_llm() 再供 chat / proactive / calendar / reminders / recommend / ingest 使用

**两侧 base_url 语义不同，不能把同一个值抄两遍**：
  融合侧 —— llm_client._endpoint、wiki_build._anthropic_messages_url 与
            _openai_chat_url 都遵循「已是完整调用地址就原样用」，所以写完整地址
  PA 侧   —— OpenAICompatLLM 自己拼 /chat/completions、AnthropicProxyLLM 自己拼
            /v1/messages，所以要写去掉协议后缀的 base

用户只填一份「协议 + 完整调用地址 + key + model」，本模块负责推导两侧写法、
原子落盘（带时间戳备份）、并写运行态覆盖让 PA 立即生效——PA 的 CONFIG 在 import
时只加载一次且 uvicorn reload=False，不这样做就必须重启后端。
"""
from __future__ import annotations

import json
import os
import shutil
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from . import config

PROTOCOLS = ("openai", "anthropic")

# 各协议的完整调用地址后缀
SUFFIX = {"openai": "/chat/completions", "anthropic": "/v1/messages"}

# 协议 -> PA 的 backend 名（见 llm.get_llm 的分派）
PA_BACKEND = {"openai": "openai_compat", "anthropic": "anthropic_proxy"}

# 融合侧要同步的键；MOMENT_LLM_* 写成与 INFO_LLM_* 相同的值，
# 不依赖 llm_client 的回退链，省得将来回退规则一变就静默走空。
_FUSED_KEYS = ("INFO_LLM_PROVIDER", "INFO_LLM_BASE_URL", "INFO_LLM_KEY", "INFO_LLM_MODEL",
               "MOMENT_LLM_BASE_URL", "MOMENT_LLM_KEY", "MOMENT_LLM_MODEL")

_PA_KEYS = ("PA_LLM_BACKEND", "PA_LLM_BASE_URL", "PA_LLM_API_KEY", "PA_LLM_MODEL")

_BACKUP_KEEP = 5


# ── 路径：一律由 config.ROOT 推导，绝不接受调用方传入，避免任意文件写 ──────
def pa_env_path() -> Path:
    return config.ROOT / ".env"


def fused_env_path() -> Path:
    # memory_bridge.MEMORY_ROOT 同款约定：PA 位于项目根内部，父目录即融合系统根
    return Path(config.ROOT).parent / ".env"


# ── 归一化 ────────────────────────────────────────────────────────────
def infer_protocol(endpoint: str) -> str:
    """从完整调用地址推断协议。"""
    e = (endpoint or "").rstrip("/").lower()
    if e.endswith("/v1/messages") or e.endswith("/messages"):
        return "anthropic"
    if e.endswith("/chat/completions") or e.endswith("/completions"):
        return "openai"
    # 退一步按 URL 里的字样猜，与 wiki_build._llm_config 的既有推断保持一致
    if "anthropic" in e:
        return "anthropic"
    return "openai"


def normalize(protocol: str, endpoint: str) -> dict:
    """把「协议 + 完整调用地址」推导成两侧各自需要的写法。"""
    protocol = (protocol or "").strip().lower()
    if protocol not in PROTOCOLS:
        protocol = infer_protocol(endpoint)
    ep = (endpoint or "").strip().rstrip("/")
    if not ep:
        raise ValueError("endpoint 不能为空")

    suffix = SUFFIX[protocol]
    if not ep.endswith(suffix):
        # 用户填的是 base 而不是完整地址：按协议补全，保证融合侧拿到的一定是完整地址
        if protocol == "anthropic" and ep.endswith("/v1/anthropic"):
            ep = ep + "/v1/messages"
        else:
            ep = ep + ("/v1/chat/completions" if protocol == "openai" else "/v1/messages")

    # PA 侧要的是去掉后缀的 base（它自己会拼）
    pa_base = ep[: -len(suffix)] if ep.endswith(suffix) else ep
    return {
        "protocol": protocol,
        "endpoint": ep,
        "fused_base_url": ep,
        "pa_backend": PA_BACKEND[protocol],
        "pa_base_url": pa_base.rstrip("/"),
    }


def existing_key() -> str:
    """两侧 .env 里已存的密钥（PA 侧优先）。

    前端不回显明文密钥，所以「留空」表示沿用现有那把；探测和同步都走这里。
    """
    return (_read_env(pa_env_path()).get("PA_LLM_API_KEY")
            or _read_env(fused_env_path()).get("INFO_LLM_KEY") or "")


def mask(key: str) -> str:
    """密钥掩码：只留长度和尾 4 位，够人工确认是哪一把，不泄露内容。"""
    k = key or ""
    if not k:
        return ""
    if len(k) <= 8:
        return "*" * len(k)
    return f"<{len(k)} 字符, 尾 {k[-4:]}>"


# ── .env 读写：保留注释与顺序，原子替换，带时间戳备份 ────────────────────
def _read_env(path: Path) -> dict:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _write_env(path: Path, updates: dict[str, str], header: str) -> None:
    """只改动 updates 里的键，其余行（含注释）原样保留。"""
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    remaining = dict(updates)
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k = stripped.partition("=")[0].strip()
        if k in remaining:
            lines[i] = f"{k}={remaining.pop(k)}"

    if remaining:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"# {header}")
        for k, v in remaining.items():
            lines.append(f"{k}={v}")

    path.parent.mkdir(parents=True, exist_ok=True)
    _backup(path)
    tmp = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)   # 里面有密钥
    except OSError:
        pass


def _backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(path.name + f".bak-{stamp}")
    shutil.copy2(path, bak)
    # 只留最近几份，别把目录堆满
    olds = sorted(path.parent.glob(path.name + ".bak-*"))
    for old in olds[:-_BACKUP_KEEP]:
        try:
            old.unlink()
        except OSError:
            pass


# ── 对外：读当前状态 ──────────────────────────────────────────────────
def read_state() -> dict:
    """两侧的当前配置（密钥掩码）+ 是否一致。供 GET /settings/llm-upstream。"""
    pa = _read_env(pa_env_path())
    fused = _read_env(fused_env_path())
    eff = _effective_pa()

    # PA 侧优先读 .env 的 PA_LLM_*；但部署机上这几个键常常不存在——
    # LLM 配置来自 config/default.json 里的 ${DEEPSEEK_API_KEY} 之类占位符，
    # 所以缺失时回退到"进程内真正生效"的配置，否则面板会误显示成未配置。
    pa_backend = pa.get("PA_LLM_BACKEND") or (eff.get("backend") or "")
    pa_base = pa.get("PA_LLM_BASE_URL") or (eff.get("base_url") or "")
    pa_model = pa.get("PA_LLM_MODEL") or (eff.get("model") or "")
    pa_key_raw = pa.get("PA_LLM_API_KEY", "")
    pa_key_masked = mask(pa_key_raw) or (eff.get("api_key_masked") or "")

    f_provider = fused.get("INFO_LLM_PROVIDER", "")
    f_base = fused.get("INFO_LLM_BASE_URL", "")
    f_key = fused.get("INFO_LLM_KEY", "")
    f_model = fused.get("INFO_LLM_MODEL", "")

    # PA 侧存的是 base，融合侧存的是完整地址；补齐后缀后才可比
    pa_endpoint = ""
    if pa_base and pa_backend:
        proto = ("anthropic" if pa_backend in ("anthropic_proxy", "glm_anthropic", "deepseek_anthropic")
                 else "openai")
        pa_endpoint = pa_base.rstrip("/") + SUFFIX.get(proto, "")

    same_endpoint = bool(pa_endpoint and f_base) and pa_endpoint.rstrip("/") == f_base.rstrip("/")
    same_model = bool(pa_model) and (pa_model == f_model)
    # 密钥只在两侧都拿得到原文时才比；一侧来自 default.json 占位符时无从比对
    key_match = (pa_key_raw == f_key) if (pa_key_raw and f_key) else None

    consistent = same_endpoint and same_model and key_match is not False
    if consistent and key_match is None:
        note = "地址与模型一致；密钥无法比对（PA 侧来自 default.json 占位符，非 .env）"
    elif consistent:
        note = "两侧一致"
    elif not pa_endpoint and not f_base:
        note = "两侧都还没配 LLM 上游——填好下面的表单点一键同步"
    else:
        bits = []
        if not same_endpoint:
            bits.append("调用地址不一致" if (pa_endpoint and f_base) else "有一侧没配地址")
        if not same_model:
            bits.append("模型不一致" if (pa_model and f_model) else "有一侧没配模型")
        if key_match is False:
            bits.append("密钥不一致")
        note = "、".join(bits) + "——用下面的一键同步统一"

    return {
        "protocols": list(PROTOCOLS),
        "pa": {
            "env_file": str(pa_env_path()),
            "backend": pa_backend,
            "endpoint": pa_endpoint,
            "base_url": pa_base,
            "api_key_masked": pa_key_masked,
            "has_api_key": bool(pa_key_masked),
            "model": pa_model,
            "from_env": bool(pa.get("PA_LLM_BACKEND")),
            "effective": eff,
        },
        "fused": {
            "env_file": str(fused_env_path()),
            "env_exists": fused_env_path().exists(),
            "provider": f_provider,
            "endpoint": f_base,
            "api_key_masked": mask(f_key),
            "has_api_key": bool(f_key),
            "model": f_model,
            "moment_endpoint": fused.get("MOMENT_LLM_BASE_URL", ""),
            "moment_model": fused.get("MOMENT_LLM_MODEL", ""),
        },
        "consistent": consistent,
        "key_match": key_match,
        "note": note,
    }


def _effective_pa() -> dict:
    """PA 进程内当前真正生效的 LLM 配置（含运行态覆盖），key 掩码。"""
    try:
        from . import llm
        eff = llm.effective_llm_config()
    except Exception as e:  # pragma: no cover - 配置异常不该拖垮整个接口
        return {"error": str(e)}
    return eff


# ── 对外：连通性探测 ──────────────────────────────────────────────────
def _ssl_context():
    """与 llm_client 一致：保留证书链校验，关掉 X509_STRICT 以兼容企业代理 CA。"""
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def probe(protocol: str, endpoint: str, api_key: str, model: str,
          timeout: float = 25.0) -> dict:
    """用最小请求探一次上游，返回是否可用 + 延迟 + 错误详情。不落盘。"""
    try:
        n = normalize(protocol, endpoint)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    proto, url = n["protocol"], n["endpoint"]

    headers = {"Content-Type": "application/json"}
    if proto == "openai":
        body = {"model": model, "max_tokens": 8,
                "messages": [{"role": "user", "content": "ping"}]}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    else:
        body = {"model": model, "max_tokens": 8,
                "messages": [{"role": "user", "content": "ping"}]}
        headers["anthropic-version"] = "2023-06-01"
        if api_key:
            headers["x-api-key"] = api_key
            headers["Authorization"] = f"Bearer {api_key}"

    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return {"ok": False, "protocol": proto, "url": url, "status": e.code,
                "latency_ms": int((time.time() - t0) * 1000),
                "error": f"HTTP {e.code}", "detail": detail}
    except Exception as e:
        return {"ok": False, "protocol": proto, "url": url,
                "latency_ms": int((time.time() - t0) * 1000),
                "error": f"{type(e).__name__}: {e}"}

    reply = ""
    try:
        data = json.loads(raw)
        if proto == "openai":
            reply = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        else:
            reply = "".join(p.get("text", "") for p in data.get("content", [])
                            if p.get("type") == "text")
    except Exception:
        reply = raw[:120]

    return {"ok": 200 <= status < 300 and bool(reply.strip()),
            "protocol": proto, "url": url, "status": status,
            "latency_ms": int((time.time() - t0) * 1000),
            "reply_head": reply.strip()[:80],
            "error": "" if reply.strip() else "HTTP 200 但回复为空"}


# ── 对外：一键同步 ────────────────────────────────────────────────────
def apply(protocol: str, endpoint: str, api_key: str | None, model: str,
          max_tokens: int | None = None) -> dict:
    """把一份上游配置同步到融合系统与 PA 两侧并落盘，PA 侧立即生效（免重启）。

    api_key 传空/None 表示「沿用现有密钥」，这样前端不必回显明文也能只改地址或模型。
    """
    n = normalize(protocol, endpoint)
    proto = n["protocol"]

    key = (api_key or "").strip() or existing_key()
    if not key:
        raise ValueError("api_key 为空，且两侧 .env 里也没有可沿用的密钥")
    model = (model or "").strip()
    if not model:
        raise ValueError("model 不能为空")

    # 1) 融合侧：写完整调用地址（llm_client / wiki_build 都支持原样使用）
    fused_updates = {
        "INFO_LLM_PROVIDER": proto,
        "INFO_LLM_BASE_URL": n["fused_base_url"],
        "INFO_LLM_KEY": key,
        "INFO_LLM_MODEL": model,
        "MOMENT_LLM_BASE_URL": n["fused_base_url"],
        "MOMENT_LLM_KEY": key,
        "MOMENT_LLM_MODEL": model,
    }
    _write_env(fused_env_path(), fused_updates,
               "由 PA 设置页「一键同步」写入（LLM 上游统一配置）")

    # 2) PA 侧：写去掉协议后缀的 base（OpenAICompatLLM / AnthropicProxyLLM 自己拼后缀）
    pa_updates = {
        "PA_LLM_BACKEND": n["pa_backend"],
        "PA_LLM_BASE_URL": n["pa_base_url"],
        "PA_LLM_API_KEY": key,
        "PA_LLM_MODEL": model,
    }
    _write_env(pa_env_path(), pa_updates,
               "由设置页「一键同步」写入（LLM 上游统一配置）")

    # 3) 运行态立即生效：PA 的 CONFIG 只在 import 时加载一次，且 uvicorn reload=False，
    #    只改 .env 的话必须重启进程才能生效——这里同时写 _RUNTIME 覆盖层免重启。
    backend = n["pa_backend"]
    config.set_override("llm.backend", backend)
    config.set_override(f"llm.{backend}.base_url", n["pa_base_url"])
    config.set_override(f"llm.{backend}.api_key", key)
    config.set_override(f"llm.{backend}.model", model)
    if max_tokens:
        config.set_override(f"llm.{backend}.max_tokens", int(max_tokens))

    # 4) 同步进 os.environ：memory_bridge 用 subprocess 调融合系统脚本，
    #    子进程继承的是本进程环境，这样 PA 触发的 wiki 重建也能读到 INFO_LLM_*。
    os.environ["PA_LLM_BACKEND"] = n["pa_backend"]
    os.environ["PA_LLM_BASE_URL"] = n["pa_base_url"]
    os.environ["PA_LLM_API_KEY"] = key
    os.environ["PA_LLM_MODEL"] = model
    for k, v in fused_updates.items():
        os.environ[k] = v

    state = read_state()
    state["applied"] = {
        "protocol": proto,
        "endpoint": n["endpoint"],
        "pa_backend": backend,
        "pa_base_url": n["pa_base_url"],
        "fused_keys": sorted(_FUSED_KEYS),
        "pa_keys": sorted(_PA_KEYS),
        "model": model,
        "api_key_masked": mask(key),
        "pa_effective_immediately": True,
        "fused_effective": "下次 cycle.sh / 脚本运行时生效（融合侧无常驻进程）",
    }
    return state
