"""WSClient unit tests."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ws_client import WSClient


async def test_connect_passes_open_timeout(free_port):
    captured = {}

    async def fake_connect(uri, **kwargs):
        captured.update(kwargs)
        m = AsyncMock(); m.open = True
        return m

    with patch("ws_client.websockets.connect", side_effect=fake_connect):
        client = WSClient(f"ws://127.0.0.1:{free_port}/ws/T")
        await client.connect()

    assert captured.get("open_timeout") == 15


async def test_disconnect_is_bounded_when_close_hangs():
    """If the underlying close() hangs, disconnect must still return within ~6s."""
    class _HangingWS:
        open = True

        async def close(self):
            await asyncio.sleep(60)

    client = WSClient("ws://test/ws/X")
    client._ws = _HangingWS()  # type: ignore[assignment]
    client._connected = True

    start = asyncio.get_event_loop().time()
    await client.disconnect()
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 8, f"disconnect hung for {elapsed:.1f}s — close() bound is missing"
    assert client._ws is None
    assert client._connected is False


async def test_connect_passes_ping_timeout_20(free_port):
    """ping_timeout MUST be a finite value so the websockets library can detect a frozen peer."""
    captured = {}

    async def fake_connect(uri, **kwargs):
        captured.update(kwargs)
        m = AsyncMock()
        m.open = True
        return m

    with patch("ws_client.websockets.connect", side_effect=fake_connect):
        client = WSClient(f"ws://127.0.0.1:{free_port}/ws/T")
        await client.connect()

    assert captured.get("ping_interval") == 20
    assert captured.get("ping_timeout") == 20, (
        "ping_timeout must be finite — None lets the engine hang on a frozen server"
    )
