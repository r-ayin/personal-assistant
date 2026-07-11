"""auth.py — token 校验（Bearer / WS query / Depends 三统一）。"""
from __future__ import annotations
import os
import hmac
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def _configured_token() -> str:
    token = os.environ.get("PA_API_TOKEN", "")
    if not token:
        print("[auth] 警告: env PA_API_TOKEN 未设置（.env 未注入）")
    return token


def is_auth_enabled() -> bool:
    return bool(_configured_token())


def _check(token: str, expected: str) -> bool:
    """恒定时间比较，防时序攻击。"""
    return bool(token) and hmac.compare_digest(token, expected)


def _extract_bearer(request: Request) -> str:
    h = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    parts = h.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return ""


async def auth_middleware(request: Request, call_next):
    """HTTP 中间件：非 WS 路径校验 Bearer token；WS 路径不经过此中间件。"""
    token = _configured_token()
    if not token:
        return await call_next(request)
    # 放行 WS 升级路径（WebSocket 在端点内自行校验）
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await call_next(request)
    # 校验 Bearer
    if _check(_extract_bearer(request), token):
        return await call_next(request)
    return JSONResponse(status_code=401, content={"detail": "missing or invalid bearer token"},
                        headers={"WWW-Authenticate": "Bearer"})


def verify_http(request: Request):
    """FastAPI Depends 式 HTTP 校验（端点细粒度，路由不统一时用）。"""
    token = _configured_token()
    if not token:
        return True
    if _check(_extract_bearer(request), token):
        return True
    raise HTTPException(401, "missing or invalid bearer token",
                        headers={"WWW-Authenticate": "Bearer"})


def verify_ws_token(websocket) -> bool:
    """WebSocket 校验 ?token= 查询参数。返回 False 时可调用 close(code=1008)。
    /ws/audio（背景音频）走局域网直连，免 token 校验。"""
    token = _configured_token()
    if not token:
        return True
    # /ws/audio 是 LAN-only 背景音频流，免鉴权
    try:
        url = getattr(websocket, "url", None)
        path = str(url) if url else (websocket.scope.get("path", "") if hasattr(websocket, "scope") else "")
        if "/ws/audio" in path:
            return True
    except Exception:
        pass
    try:
        qp = websocket.query_params
        return _check(qp.get("token", ""), token)
    except Exception:
        return False


def generate_token(nbytes: int = 32) -> str:
    """生成随机 token：32 字节 = 64 hex 字符，适合用户首次部署设置。"""
    return secrets.token_hex(nbytes)
