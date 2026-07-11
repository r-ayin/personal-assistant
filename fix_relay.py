#!/usr/bin/env python3
"""修复 relay_bridge.py 的缩进问题。"""
import re

with open("/opt/pa-relay/relay_bridge.py", "r") as f:
    content = f.read()

# Replace the broken sed edit with properly indented code
old_block = """# Also listen on 0.0.0.0:18801 for PC direct tunnel
    async with websockets.serve(
        bridge.router, "0.0.0.0", 18801,
        max_size=MAX_FRAME_SIZE,
        ping_interval=PING_INTERVAL,
        ping_timeout=PING_TIMEOUT,
        open_timeout=OPEN_TIMEOUT,
        close_timeout=CLOSE_TIMEOUT,
        compression=None,
        process_request=_process_request,
    ):
        await asyncio.Future()/"""

new_block = """        # Also listen on 0.0.0.0:18801 for PC direct tunnel
        async with websockets.serve(
            bridge.router, "0.0.0.0", 18801,
            max_size=MAX_FRAME_SIZE,
            ping_interval=PING_INTERVAL,
            ping_timeout=PING_TIMEOUT,
            open_timeout=OPEN_TIMEOUT,
            close_timeout=CLOSE_TIMEOUT,
            compression=None,
            process_request=_process_request,
        ):
            await asyncio.Future()"""

content = content.replace(old_block, new_block)

with open("/opt/pa-relay/relay_bridge.py", "w") as f:
    f.write(content)

import py_compile
py_compile.compile("/opt/pa-relay/relay_bridge.py", doraise=True)
print("FIXED")
