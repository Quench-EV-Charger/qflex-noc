"""Engine should hold a single aiohttp.ClientSession reused by all collaborators."""
import asyncio

import aiohttp
import pytest

from noc_engine import NocEngine


def _cfg():
    return {
        "charger_id": "T",
        "noc_server": {"host": "127.0.0.1", "port": 1},
        "charger_ip": "127.0.0.1",
        "charger_ports": {"system_api": 0, "charging_controller": 0,
                          "allocation_engine": 0, "error_generation": 0},
    }


async def test_engine_exposes_shared_http_session(tmp_path):
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))
    s1 = await engine._ensure_http_session()
    s2 = await engine._ensure_http_session()
    assert s1 is s2
    assert isinstance(s1, aiohttp.ClientSession)
    assert not s1.closed
    await engine._close_http_session()
    assert engine.http_session is None


async def test_send_auth_completes_when_firmware_endpoint_is_slow(tmp_path):
    """If the firmware endpoint takes > firmware_fetch_timeout, auth still goes out promptly."""
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))
    engine.firmware_fetch_timeout = 0.2

    sent: list[dict] = []

    class _WS:
        connected = True
        async def send(self, m):
            sent.append(m)

    async def slow_fetch():
        await asyncio.sleep(2)
        return "9.9.9"

    engine._fetch_firmware_version = slow_fetch  # type: ignore[assignment]

    start = asyncio.get_event_loop().time()
    await engine._send_auth(_WS())  # type: ignore[arg-type]
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 1.0, f"auth must not be blocked by slow firmware fetch (took {elapsed:.2f}s)"
    assert any(m["type"] == "auth" for m in sent)


async def test_close_then_ensure_creates_new_session(tmp_path):
    """After explicit close, ensure_http_session must create a new live session."""
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))
    s1 = await engine._ensure_http_session()
    await engine._close_http_session()
    s2 = await engine._ensure_http_session()
    assert s1 is not s2
    assert not s2.closed
    await engine._close_http_session()
