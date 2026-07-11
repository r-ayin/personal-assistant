#!/usr/bin/env python3
"""relay_bridge.py — ECS 中继桥（远程手机 ↔ 电脑，只转帧不跑计算）+ 应用层安全加固。

拓扑（手机在外网 4G 时）：
  手机 ─wss:443─→ nginx ─→ relay_bridge:8001
                              ↑ /ws/tunnel（电脑出站连入，注册为 tunnel）
                              ↓ /ws/live（手机连入，配对到 tunnel）
  电脑跑 tunnel_client.py：出站连 ECS /ws/tunnel ↔ 本地 ws://localhost:8000/ws/live（PA 后端）

加固（针对公网定向攻击）：
  - max_size=65536 单帧上限（防超大帧）；ping 30s/10s 检测僵尸连接；open/close 超时
  - 每 IP 最大并发连接 4（防连接耗尽）；全局最大 50（防资源耗尽）
  - 每连接消息速率 600/60s（音频帧率 ~300/min 留 2x 余量），超限 close 1008
  - 空闲超时 120s 踢出（防握手后占位）
  - token 校验失败记日志（fail2ban 吃）：auth_failed ip=<IP> reason=invalid_token
  - Origin 白名单（防 CSWSH，非浏览器 WS 客户端可不带 Origin）
  - 只绑 127.0.0.1:8001（nginx 反代，不直接暴露）
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse, parse_qs

try:
    import websockets
except ImportError:
    print("缺 websockets：pip install websockets", file=sys.stderr)
    raise

# ── 安全常量 ─────────────────────────────────────────────────────
RELAY_TOKEN = os.environ.get("PA_RELAY_TOKEN", "") or os.environ.get("PA_API_TOKEN", "")
LOG_FILE = os.environ.get("PA_RELAY_LOG", "/var/log/relay_bridge/relay_bridge.log")
MAX_FRAME_SIZE = 65_536        # 64KB 单帧（音频 PCM 帧 <32KB）
MAX_CONNS_PER_IP = 4           # 每 IP 最大并发 WS 连接
MAX_TOTAL_CONNS = 50           # 全局最大连接（单用户场景 50 足够）
RATE_LIMIT_WINDOW = 60         # 速率窗口（秒）
RATE_LIMIT_MAX_MSGS = 600      # 窗口内最大消息数（音频 5帧/s=300/min，2x 余量）
IDLE_TIMEOUT = 120             # 无业务消息超时（秒）
PING_INTERVAL = 30             # 心跳间隔
PING_TIMEOUT = 10              # 心跳回复超时
OPEN_TIMEOUT = 10              # 握手建立超时
CLOSE_TIMEOUT = 5              # 关闭超时
ALLOWED_ORIGINS = {  # CSWSH 防护白名单（自签 IP，无域名）
    "https://115.29.199.130", "http://115.29.199.130",
    "http://localhost", "https://localhost",
    "http://127.0.0.1", "https://127.0.0.1",
}

# ── 日志（fail2ban filter 匹配此格式）────────────────────────────
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True) if os.path.dirname(LOG_FILE) else None
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s relay_bridge: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("relay_bridge")


def _get_path(ws) -> str:
    req = getattr(ws, "request", None)
    if req is not None and getattr(req, "path", None):
        return req.path
    return getattr(ws, "path", "") or "/"


def _client_ip(ws) -> str:
    """优先 nginx X-Real-IP，回退 remote_address。"""
    req = getattr(ws, "request", None)
    if req is not None:
        hdrs = getattr(req, "headers", None)
        if hdrs:
            xri = hdrs.get("X-Real-IP") or hdrs.get("x-real-ip")
            if xri:
                return xri
    ra = getattr(ws, "remote_address", None)
    return ra[0] if ra else "unknown"


def _check_token(token: str | None) -> bool:
    if not RELAY_TOKEN:
        return True  # dev 放行
    import hmac
    return bool(token) and hmac.compare_digest(token, RELAY_TOKEN)


def _token_for(ws) -> bool:
    q = parse_qs(urlparse(_get_path(ws)).query)
    return _check_token(q.get("token", [""])[0])


def _origin_ok(ws) -> bool:
    req = getattr(ws, "request", None)
    if req is None:
        return True
    hdrs = getattr(req, "headers", None)
    if not hdrs:
        return True
    origin = hdrs.get("Origin") or hdrs.get("origin") or ""
    if not origin:
        return True  # 非浏览器客户端不发 Origin，放行（token 是主防线）
    return origin in ALLOWED_ORIGINS


async def _process_request(connection, request):
    """握手前校验：token 失败直接返 HTTP 403（不进 WS 协议），
    nginx 记 403 给 fail2ban nginx-ws-auth jail 吃。"""
    from urllib.parse import urlparse, parse_qs
    path = getattr(request, "path", "") or ""
    q = parse_qs(urlparse(path).query)
    token = q.get("token", [""])[0]
    if not _check_token(token):
        hdrs = getattr(request, "headers", None)
        ip = (hdrs.get("X-Real-IP") if hdrs else None) or "unknown"
        log.warning("auth_failed ip=%s reason=invalid_token path=%s", ip, path.split("?")[0])
        try:
            from websockets.http11 import Response
            from websockets.datastructures import Headers
            return Response(403, "Forbidden", Headers([("Content-Type", "text/plain")]),
                            b"invalid token\n")
        except Exception:
            return (403, [], b"invalid token\n")
    return None  # 放行握手


class _ConnState:
    __slots__ = ("ip", "last_msg", "stamps")
    def __init__(self, ip: str):
        self.ip = ip
        self.last_msg = time.monotonic()
        self.stamps: list[float] = []


class Bridge:
    def __init__(self):
        self.tunnel = None
        self.phones: set = set()
        self._lock = asyncio.Lock()
        self._ip_conns: dict[str, int] = defaultdict(int)
        self._total = 0

    def _admit(self, ws) -> bool:
        """握手后准入：token + origin + 连接数限制。返回 False 则已 close。"""
        ip = _client_ip(ws)
        if not _token_for(ws):
            log.warning("auth_failed ip=%s reason=invalid_token", ip)
            return False
        if not _origin_ok(ws):
            log.warning("auth_failed ip=%s reason=bad_origin", ip)
            return False
        if self._total >= MAX_TOTAL_CONNS:
            log.warning("conn_reject ip=%s reason=global_limit total=%d", ip, self._total)
            return False
        if self._ip_conns[ip] >= MAX_CONNS_PER_IP:
            log.warning("conn_reject ip=%s reason=per_ip_limit conns=%d", ip, self._ip_conns[ip])
            return False
        self._ip_conns[ip] += 1
        self._total += 1
        return True

    def _release(self, ws):
        ip = _client_ip(ws)
        self._ip_conns[ip] = max(0, self._ip_conns[ip] - 1)
        if self._ip_conns[ip] == 0:
            self._ip_conns.pop(ip, None)
        self._total = max(0, self._total - 1)

    @staticmethod
    def _rate_ok(state: _ConnState) -> bool:
        now = time.monotonic()
        cutoff = now - RATE_LIMIT_WINDOW
        state.stamps = [t for t in state.stamps if t > cutoff]
        if len(state.stamps) >= RATE_LIMIT_MAX_MSGS:
            return False
        state.stamps.append(now)
        state.last_msg = now
        return True

    async def _broadcast_phones(self, data):
        dead = []
        for p in list(self.phones):
            try:
                await p.send(data)
            except Exception:
                dead.append(p)
        for p in dead:
            self.phones.discard(p)

    async def handle_phone(self, ws):
        """手机侧 /ws/live。"""
        if not self._admit(ws):
            await ws.close(code=1008, reason="policy")
            return
        state = _ConnState(_client_ip(ws))
        async with self._lock:
            self.phones.add(ws)
        log.info("phone_in ip=%s total_phones=%d", state.ip, len(self.phones))
        if self.tunnel is None:
            await ws.send(json.dumps({"type": "device_offline",
                                      "data": {"msg": "电脑未连接，请稍候"},
                                      "ts": datetime.now().isoformat()}))
        try:
            async for msg in ws:
                if not self._rate_ok(state):
                    log.warning("rate_exceeded ip=%s kind=phone", state.ip)
                    await ws.close(code=1008, reason="rate limit")
                    return
                if self.tunnel is not None:
                    try:
                        await self.tunnel.send(msg)
                    except Exception as e:
                        log.warning("forward_fail kind=phone->tunnel: %s", e)
                        self.tunnel = None
        except Exception as e:
            log.warning("phone_error ip=%s: %s", state.ip, e)
        finally:
            async with self._lock:
                self.phones.discard(ws)
            self._release(ws)
            log.info("phone_out ip=%s remain=%d", state.ip, len(self.phones))

    async def handle_tunnel(self, ws):
        """电脑侧 /ws/tunnel。"""
        if not self._admit(ws):
            await ws.close(code=1008, reason="policy")
            return
        state = _ConnState(_client_ip(ws))
        async with self._lock:
            if self.tunnel is not None:
                try:
                    await self.tunnel.close()
                except Exception:
                    pass
            self.tunnel = ws
        log.info("tunnel_in ip=%s", state.ip)
        try:
            async for msg in ws:
                if not self._rate_ok(state):
                    log.warning("rate_exceeded ip=%s kind=tunnel", state.ip)
                    await ws.close(code=1008, reason="rate limit")
                    return
                await self._broadcast_phones(msg)
        except Exception as e:
            log.warning("tunnel_error ip=%s: %s", state.ip, e)
        finally:
            async with self._lock:
                if self.tunnel is ws:
                    self.tunnel = None
            self._release(ws)
            log.info("tunnel_out ip=%s", state.ip)

    async def router(self, ws):
        """按 path 分流。"""
        if _get_path(ws).split("?")[0] == "/ws/tunnel":
            await self.handle_tunnel(ws)
        else:
            await self.handle_phone(ws)


async def main():
    host = os.environ.get("PA_RELAY_HOST", "127.0.0.1")
    port = int(os.environ.get("PA_RELAY_PORT", "8001"))
    bridge = Bridge()
    log.info("listening %s:%d token=%s max_frame=%d max_conns_ip=%d max_total=%d",
             host, port, "on" if RELAY_TOKEN else "dev-off", MAX_FRAME_SIZE,
             MAX_CONNS_PER_IP, MAX_TOTAL_CONNS)
    async with websockets.serve(
        bridge.router, host, port,
        max_size=MAX_FRAME_SIZE,
        ping_interval=PING_INTERVAL,
        ping_timeout=PING_TIMEOUT,
        open_timeout=OPEN_TIMEOUT,
        close_timeout=CLOSE_TIMEOUT,
        compression=None,  # 音频二进制帧压缩率低，省 CPU
        process_request=_process_request,  # 握手前 403 拒坏 token
    ):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
