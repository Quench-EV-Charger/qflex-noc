#!/usr/bin/env python3
"""
NocEngine WebSocket Client
===========================
Manages a persistent WebSocket connection to the NOC server.

Features:
  - connect / disconnect
  - send JSON messages
  - receive JSON messages
  - reports connection state
"""

import asyncio
import json
import logging
import ssl
import time
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)


class WSClient:
    """
    Thin WebSocket wrapper used by NocEngine.

    Usage:
        client = WSClient("ws://server:8080/ws/CHARGER-001")
        await client.connect()
        await client.send({"type": "heartbeat", ...})
        msg = await client.receive()
        await client.disconnect()
    """

    def __init__(self, uri: str, ssl_context=None, send_timeout: float = 10.0):
        self.uri = uri
        self._ssl = ssl_context
        self._ws = None
        self._connected = False
        self.send_timeout = send_timeout
        # Monotonic timestamp of the last observed WS-level activity
        # (send, receive, or pong).  Used by the engine watchdog.
        self._last_activity_at: float = time.monotonic()

    # ------------------------------------------------------------------
    # Connection state
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        if not self._connected or self._ws is None:
            return False
        # websockets >=13 uses ClientConnection with .state
        if hasattr(self._ws, "state"):
            try:
                from websockets.protocol import State
                return self._ws.state is State.OPEN
            except Exception:
                pass
        # Legacy WebSocketClientProtocol uses .open
        return getattr(self._ws, "open", False)

    @property
    def last_activity_at(self) -> float:
        """Monotonic timestamp of the most recent WS activity (send/recv/pong)."""
        return self._last_activity_at

    def _touch_activity(self) -> None:
        """Record that WS-level activity just occurred."""
        self._last_activity_at = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        """Open WebSocket connection to the NOC server."""
        kwargs: dict[str, Any] = {
            "open_timeout": 15,        # Bound the TCP+TLS+WS handshake at 15s
            "ping_interval": 20,       # Keep-alive pings every 20s (keeps NAT/ELB alive)
            "ping_timeout": 20,        # Reconnect if server fails to pong within 20s
            "close_timeout": 5,
            "max_size": 2 * 1024 * 1024,  # 2 MB max message size
        }
        if self._ssl is not None:
            kwargs["ssl"] = self._ssl

        self._ws = await websockets.connect(self.uri, **kwargs)
        self._connected = True
        self._touch_activity()  # mark connection as fresh activity

        # Register a pong callback so the watchdog sees server liveness
        # even when no application messages are flowing.
        if hasattr(self._ws, "pong_waiter"):
            # websockets < 13 (legacy protocol)
            pass  # pong handled internally; we touch on send/recv instead
        # For all versions we can monkey-patch the internal pong handler
        # via the public callback API if available.
        try:
            # websockets >= 13 exposes a pong_handler callback
            self._ws.pong_handler = self._on_pong  # type: ignore[attr-defined]
        except AttributeError:
            pass
        logger.info(f"[WS-Client] Connected to {self.uri}")

    async def disconnect(self):
        """Close the WebSocket connection gracefully (bounded)."""
        if self._ws:
            try:
                await asyncio.wait_for(self._ws.close(), timeout=6)
            except asyncio.TimeoutError:
                logger.warning(f"[WS-Client] close() exceeded 6s for {self.uri}")
            except Exception as e:
                logger.warning(f"[WS-Client] close() raised {type(e).__name__}: {e}")
        self._connected = False
        self._ws = None
        logger.info(f"[WS-Client] Disconnected from {self.uri}")

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _on_pong(self, data: bytes = b"") -> None:
        """Called when a pong frame arrives from the server."""
        self._touch_activity()
        logger.debug("[WS-Client] 🏓 Pong received")

    async def send(self, message: dict):
        """
        Serialize and send a JSON message, bounded by ``send_timeout``.

        Raises:
            ConnectionError:      If not connected.
            asyncio.TimeoutError: If the underlying drain blocks longer than send_timeout.
            ConnectionClosed:     If the connection drops mid-send.
        """
        if not self.connected:
            raise ConnectionError("WebSocket not connected")
        await asyncio.wait_for(self._ws.send(json.dumps(message)), timeout=self.send_timeout)
        self._touch_activity()

    async def receive(self) -> dict:
        """
        Receive the next JSON message.

        Raises:
            ConnectionError: If not connected.
            ConnectionClosed: If connection dropped.
        """
        if not self.connected:
            raise ConnectionError("WebSocket not connected")
        raw = await self._ws.recv()
        self._touch_activity()
        return json.loads(raw)
