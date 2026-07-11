#!/usr/bin/env python3
import asyncio, websockets, sys

TOKEN = "b3018ea3c3eca3ce34adaf99f16fc1ec1e7ca9f0335a9d2884e3f7cd44c3dbc6"

async def test():
    uri = f"ws://127.0.0.1:8001/ws/tunnel?token={TOKEN}"
    print(f"Connecting to {uri}")
    try:
        async with websockets.connect(uri, max_size=65536, ping_interval=30, ping_timeout=10, open_timeout=15) as ws:
            print("Connected!")
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"Received: {msg}")
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}", file=sys.stderr)

asyncio.run(test())
