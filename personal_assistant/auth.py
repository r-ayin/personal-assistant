"""Bearer authentication shared by PA HTTP and WebSocket endpoints.

`config.api_token()` is the single token source. Static Web/Android assets and
the health probe stay public; data and control APIs require Bearer auth when a
token is configured. WebSocket clients send the same token in `?token=`.

v0.10 宽限轮换：`cli token rotate` 轮换 token 后，旧 token 以 SHA-256 哈希
登记到退役名单（kv: retired_tokens），在宽限期（auth.token_grace_days，默认 7 天）
内仍被接受——设备无需重新烧录即可过渡，过渡期内随时重配 NVS/重新编译。
`cli token revoke` 可提前吊销。
"""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from . import config
from fastapi import HTTPException, Request, WebSocket, status


def _configured_token() -> str | None:
    """Return the single configured token source used by HTTP and WebSocket auth."""
    return config.api_token() or None


def is_auth_enabled() -> bool:
    return bool(_configured_token())


def _retired_tokens() -> list[dict]:
    """宽限期内的退役 token 名单（仅存哈希）。过期项自动过滤。"""
    from . import storage
    raw = storage.kv_get("retired_tokens")
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except Exception:
        return []
    grace_days = float(config.get("auth.token_grace_days", 7))
    now = datetime.now().astimezone()
    valid = []
    for e in entries:
        try:
            retired_at = datetime.fromisoformat(e["retired_at"])
        except Exception:
            continue
        if retired_at + timedelta(days=float(e.get("grace_days", grace_days))) > now:
            valid.append(e)
    return valid


def _check(token: str | None) -> bool:
    """常量时间比较，防时序侧信道。宽限期内接受退役 token（哈希比对）。"""
    expected = _configured_token()
    if not expected:
        return True  # 开发模式：未配 token 放行
    if not token:
        return False
    if hmac.compare_digest(token, expected):
        return True
    tok_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return any(hmac.compare_digest(tok_hash, e.get("hash", ""))
               for e in _retired_tokens())


def _extract_bearer(request: Request) -> str | None:
    h = request.headers.get("authorization") or request.headers.get("Authorization")
    if not h:
        return None
    parts = h.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


_EXEMPT_ROOTS = ("/health", "/web", "/android", "/favicon", "/ws")


def _is_exempt(path: str) -> bool:
    return any(path == root or path.startswith(root + "/") for root in _EXEMPT_ROOTS)


async def auth_middleware(request: Request, call_next):
    """Authenticate every non-static HTTP route when a token is configured."""
    if _is_exempt(request.url.path) or not is_auth_enabled():
        return await call_next(request)
    if not _check(_extract_bearer(request)):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401,
                            content={"detail": "missing or invalid bearer token"},
                            headers={"WWW-Authenticate": "Bearer"})
    return await call_next(request)


async def verify_http(request: Request) -> None:
    """Dependency form for endpoints that also document their auth requirement."""
    if _is_exempt(request.url.path) or not is_auth_enabled():
        return
    if not _check(_extract_bearer(request)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_ws_token(websocket: WebSocket) -> bool:
    """WebSocket 握手阶段校验 Bearer header 或兼容的 ?token=。"""
    authorization = websocket.headers.get("authorization", "")
    token = ""
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = websocket.query_params.get("token", "")
    if not token and is_auth_enabled():
        return False
    return _check(token) if is_auth_enabled() else True


def generate_token(nbytes: int = 32) -> str:
    """生成随机 token（32 字节 = 64 hex 字符）。供用户首次配置用。"""
    return secrets.token_hex(nbytes)


# ── v0.10 宽限轮换 ────────────────────────────────────────────
def retire_token(token: str, grace_days: float | None = None) -> None:
    """把旧 token 以哈希形式登记到退役名单（宽限期内仍被 _check 接受）。"""
    from . import storage
    if not token:
        return
    entries = []
    raw = storage.kv_get("retired_tokens")
    if raw:
        try:
            entries = json.loads(raw)
        except Exception:
            entries = []
    tok_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if any(e.get("hash") == tok_hash for e in entries):
        return
    entries.append({
        "hash": tok_hash,
        "prefix": token[:8],
        "retired_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "grace_days": float(grace_days if grace_days is not None
                            else config.get("auth.token_grace_days", 7)),
    })
    storage.kv_set("retired_tokens", json.dumps(entries, ensure_ascii=False))


def revoke_token(prefix: str = "", all_tokens: bool = False) -> int:
    """提前吊销退役 token：按前缀匹配删除；all_tokens=True 清空名单。返回删除数。"""
    from . import storage
    raw = storage.kv_get("retired_tokens")
    if not raw:
        return 0
    try:
        entries = json.loads(raw)
    except Exception:
        return 0
    before = len(entries)
    if all_tokens:
        entries = []
    else:
        # 前缀双向匹配：用户可传完整 token 前缀（可能长于存储的 8 位摘要）
        entries = [e for e in entries
                   if not (prefix.startswith(str(e.get("prefix", "")))
                           or str(e.get("prefix", "")).startswith(prefix))]
    storage.kv_set("retired_tokens", json.dumps(entries, ensure_ascii=False))
    return before - len(entries)


def list_tokens() -> dict:
    """当前 token（掩码）+ 退役名单摘要。"""
    cur = _configured_token() or ""
    return {
        "current": (cur[:8] + "…" + cur[-4:]) if len(cur) > 12 else ("(未配置)" if not cur else "***"),
        "auth_enabled": is_auth_enabled(),
        "retired": [
            {"prefix": e.get("prefix", ""), "retired_at": e.get("retired_at", ""),
             "grace_days": e.get("grace_days")}
            for e in _retired_tokens()],
    }
