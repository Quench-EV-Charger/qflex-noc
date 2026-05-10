#!/usr/bin/env python3
"""
Local HTTP API for noc_engine self-introspection.

Endpoints:
  GET /api/v1/noc_engine/version  → {success, value, uptime_seconds}
  GET /api/v1/noc_engine/health   → {status: "ok"}

Bound to localhost by default; intended for on-charger consumers
(other A-core services, monitoring scripts).
"""
import logging
import time
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)


class VersionAPIServer:
    def __init__(self, version: str, host: str = "127.0.0.1", port: int = 8009):
        self.version = version
        self.host = host
        self.port = port
        self._started_at = time.monotonic()
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.BaseSite] = None

    async def _handle_version(self, _request: web.Request) -> web.Response:
        return web.json_response({
            "success": True,
            "value": self.version,
            "uptime_seconds": round(time.monotonic() - self._started_at, 1),
        })

    async def _handle_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/api/v1/noc_engine/version", self._handle_version)
        app.router.add_get("/api/v1/noc_engine/health",  self._handle_health)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(f"[VersionAPI] Listening on http://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        logger.info("[VersionAPI] Stopped")
