"""GET /api/v1/noc_engine/version returns the engine version + uptime."""
import aiohttp
import pytest

from version_api import VersionAPIServer


async def test_version_endpoint_returns_version(free_port):
    server = VersionAPIServer(version="1.1.0-dev", host="127.0.0.1", port=free_port)
    await server.start()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://127.0.0.1:{free_port}/api/v1/noc_engine/version") as r:
                assert r.status == 200
                data = await r.json()
                assert data["success"] is True
                assert data["value"] == "1.1.0-dev"
                assert "uptime_seconds" in data
                assert isinstance(data["uptime_seconds"], (int, float))
    finally:
        await server.stop()


async def test_version_endpoint_health(free_port):
    server = VersionAPIServer(version="1.1.0-dev", host="127.0.0.1", port=free_port)
    await server.start()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://127.0.0.1:{free_port}/api/v1/noc_engine/health") as r:
                assert r.status == 200
                data = await r.json()
                assert data["status"] == "ok"
    finally:
        await server.stop()
