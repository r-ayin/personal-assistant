#!/usr/bin/env python3
"""tunnel_client.py — PC 端隧道客户端

拓扑：
  PC: ws://localhost:8000/ws/live (PA 后端)
                    ↕
  PC: tunnel_client → wss://ECS:443/ws/tunnel?token=... (出站连 ECS)
                    ↕
  ECS: relay_bridge → /ws/live (手机连入)
                    ↕
  手机浏览器 (外网 4G)

使用：
  export PA_RELAY_TOKEN="xxx"   # 同 PA_API_TOKEN
  export PA_ECS_HOST="115.29.199.130"
  python tunnel_client.py

重建连接：
  自动重连（指数退避 1-60s），无限重试。
  本地 PA 后端断开也自动等其恢复。
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import signal
import sys
import time
from urllib.parse import urlencode

try:
    import websockets
except ImportError:
    print("缺 websockets：pip install websockets", file=sys.stderr)
    raise

# ── 配置 ─────────────────────────────────────────────────────────
ECS_HOST = os.environ.get("PA_ECS_HOST", "115.29.199.130")
ECS_PORT = os.environ.get("PA_ECS_PORT", "443")
TOKEN = os.environ.get("PA_RELAY_TOKEN", "") or os.environ.get("PA_API_TOKEN", "")
LOCAL_WS = os.environ.get("PA_LOCAL_WS", "ws://localhost:8000/ws/live")
RECONNECT_BASE = 1.0  # 秒
RECONNECT_MAX = 60.0
RECONNECT_MULT = 2.0
PING_INTERVAL = 25  # 比 relay_bridge 的 30s 略短

log = logging.getLogger("tunnel_client")

# ── 日志 ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s tunnel: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

_shutdown = asyncio.Event()


def _signal():
    _shutdown.set()


async def _bridge(reader, writer, label: str):
    """双向桥接：reader → writer，任意端断开即停。"""
    try:
        async for msg in reader:
            if isinstance(msg, str):
                data = msg.encode("utf-8")
            else:
                data = msg
            await writer.send(data)
    except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
        log.debug("%s bridge closed: %s", label, e)
    except Exception as e:
        log.warning("%s bridge error: %s", label, e)


async def _run_tunnel(
    ecs_ws: websockets.WebSocketClientProtocol,
    local_ws: websockets.WebSocketClientProtocol,
):
    """双向桥接 ECS 隧道 ↔ 本地 PA 后端。先完成的引发另一个一起关闭。"""
    # 两个方向的桥接并发跑，哪个先完就取消另一个
    ecs_to_local = asyncio.create_task(_bridge(ecs_ws, local_ws, "ecs→local"))
    local_to_ecs = asyncio.create_task(_bridge(local_ws, ecs_ws, "local→ecs"))

    done, pending = await asyncio.wait(
        [ecs_to_local, local_to_ecs],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # 取消另一个方向
    for t in pending:
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

    # 关闭底层连接
    for ws in (ecs_ws, local_ws):
        try:
            await ws.close()
        except Exception:
            pass


async def _connect_local() -> websockets.WebSocketClientProtocol:
    """连本地 PA 后端，带重试。"""
    delay = RECONNECT_BASE
    while not _shutdown.is_set():
        try:
            ws = await websockets.connect(
                LOCAL_WS,
                max_size=65_536,
                ping_interval=PING_INTERVAL,
                ping_timeout=10,
                open_timeout=10,
            )
            log.info("本地 PA 后端已连接: %s", LOCAL_WS)
            return ws
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
            log.warning("本地 PA 后端不可用 (%s)，%0.fs 后重试...", e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * RECONNECT_MULT, RECONNECT_MAX)
    raise RuntimeError("shutdown")


async def _connect_ecs() -> websockets.WebSocketClientProtocol:
    """连 ECS 中继。"""
    params = urlencode({"token": TOKEN})
    uri = f"wss://{ECS_HOST}:{ECS_PORT}/ws/tunnel?{params}"
    log.info("正在连接 ECS 中继: %s", uri.replace(TOKEN, "***"))
    ws = await websockets.connect(
        uri,
        max_size=65_536,
        ping_interval=PING_INTERVAL,
        ping_timeout=10,
        open_timeout=15,
        # wss 需要 ssl，但是自签证书时可能需 verify=False
        # 正式用 ECS 证书时不需要这个
    )
    log.info("ECS 中继已连接")
    return ws


async def tunnel_loop():
    """主循环：连 ECS → 连本地 → 桥接 → 断开 → 重连"""
    log.info("tunnel_client 启动: ecs=%s:%s local=%s", ECS_HOST, ECS_PORT, LOCAL_WS)
    if not TOKEN:
        log.error("PA_RELAY_TOKEN 或 PA_API_TOKEN 未设置")
        return

    delay = RECONNECT_BASE
    while not _shutdown.is_set():
        try:
            ecs_ws = await _connect_ecs()
            delay = RECONNECT_BASE  # 连上后重置退避

            try:
                local_ws = await _connect_local()
            except Exception:
                await ecs_ws.close()
                raise

            await _run_tunnel(ecs_ws, local_ws)
            log.info("隧道断开，重连中...")
            delay = RECONNECT_BASE  # 正常断开也重置退避
            await asyncio.sleep(1)

        except (websockets.ConnectionClosed, OSError,
                asyncio.TimeoutError, ConnectionRefusedError) as e:
            log.warning("连接失败 (%s)，%0.fs 后重试...", e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * RECONNECT_MULT, RECONNECT_MAX)
        except Exception as e:
            log.error("隧道异常: %s", e, exc_info=True)
            await asyncio.sleep(5)


async def main():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal)
        except NotImplementedError:
            # Windows 不支持 add_signal_handler
            pass

    await tunnel_loop()
    log.info("tunnel_client 已停止")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
