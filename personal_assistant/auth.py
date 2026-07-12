"""auth.py — Bearer token 鉴权（手机/电脑从公网访问 ECS/电脑后端的前置安全层）。

约束：stdlib + fastapi，零三方 SDK。
- PA_API_TOKEN 环境变量（或 config security.api_token）配置 token。
- 未配置 token 时降级为"开发模式"放行（打印警告）——dev 盒/localhost 无需鉴权。
- 配置后：所有 HTTP 端点校验 Authorization: Bearer <token>；/health 豁免（健康探针）。
- WebSocket 端点在握手阶段校验 query param ?token=<token>（浏览器 WS 不能设 header）。
"""
from __future__ import annotations
import os
import hmac
import secrets

from fastapi import HTTPException, Request, WebSocket, status


def _configured_token() -> str | None:
    """从 env PA_API_TOKEN 取（不入仓的 .env 注入）。"""
    return os.environ.get("PA_API_TOKEN") or None


def is_auth_enabled() -> bool:
    return bool(_configured_token())


def _check(token: str | None) -> bool:
    """常量时间比较，防时序侧信道。"""
    expected = _configured_token()
    if not expected:
        return True  # 开发模式：未配 token 放行
    if not token:
        return False
    return hmac.compare_digest(token, expected)


def _extract_bearer(request: Request) -> str | None:
    h = request.headers.get("authorization") or request.headers.get("Authorization")
    if not h:
        return None
    parts = h.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


# 豁免路径：健康探针 + 前端静态资源（页面本身不含敏感数据，数据走鉴权 API）。
# /web /android 是静态挂载，访问页面不需要 token；但页面里的 fetch/WS 调用要带 token。
# /ws/* 不走 HTTP 中间件（WS 升级绕过 HTTP middleware），由 verify_ws_token 校验 query ?token=。
_EXEMPT_PREFIXES = ("/health", "/web", "/android", "/favicon", "/ws/")


async def auth_middleware(request: Request, call_next):
    """HTTP 中间件：非豁免路径校验 Bearer token。WS 不经过此中间件。"""
    if request.url.path.startswith(_EXEMPT_PREFIXES) or not is_auth_enabled():
        return await call_next(request)
    if not _check(_extract_bearer(request)):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401,
                            content={"detail": "missing or invalid bearer token"},
                            headers={"WWW-Authenticate": "Bearer"})
    return await call_next(request)


async def verify_http(request: Request) -> None:
    """（保留）FastAPI Depends 形式，供需要细粒度注入的路由用。正常走中间件即可。"""
    if request.url.path.startswith(_EXEMPT_PREFIXES) or not is_auth_enabled():
        return
    if not _check(_extract_bearer(request)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_ws_token(websocket: WebSocket) -> bool:
    """WebSocket 握手阶段校验 ?token=。返回 False 时由调用方 close(code=1008)。"""
    if not is_auth_enabled():
        return True
    token = websocket.query_params.get("token") or ""
    return _check(token)


def generate_token(nbytes: int = 32) -> str:
    """生成随机 token（32 字节 = 64 hex 字符）。供用户首次配置用。"""
    return secrets.token_hex(nbytes)
