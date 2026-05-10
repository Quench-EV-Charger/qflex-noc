"""Shared pytest fixtures: free-port allocator, controllable WS servers."""
import asyncio
import socket
import sys
from pathlib import Path

import pytest
import websockets

# Make the parent qflex-noc package importable as flat modules (matches how main.py runs).
_QFLEX_NOC_DIR = Path(__file__).resolve().parent.parent
if str(_QFLEX_NOC_DIR) not in sys.path:
    sys.path.insert(0, str(_QFLEX_NOC_DIR))


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def free_port() -> int:
    return _free_port()


@pytest.fixture
async def echo_ws_server(free_port):
    """A WS server that echoes every message back."""
    received: list[str] = []

    async def handler(ws):
        try:
            async for msg in ws:
                received.append(msg)
                await ws.send(msg)
        except websockets.ConnectionClosed:
            pass

    server = await websockets.serve(handler, "127.0.0.1", free_port)
    try:
        yield {"port": free_port, "received": received, "server": server}
    finally:
        server.close()
        await server.wait_closed()


@pytest.fixture
async def silent_ws_server(free_port):
    """A WS server that accepts the connection but never reads/writes — simulates a frozen peer."""

    async def handler(_ws):
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise

    server = await websockets.serve(handler, "127.0.0.1", free_port, ping_interval=None)
    try:
        yield {"port": free_port, "server": server}
    finally:
        server.close()
        await server.wait_closed()
