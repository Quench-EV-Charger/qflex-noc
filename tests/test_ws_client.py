"""WSClient unit tests."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ws_client import WSClient


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
