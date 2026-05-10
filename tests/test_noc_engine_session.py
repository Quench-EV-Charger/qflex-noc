"""Engine should hold a single aiohttp.ClientSession reused by all collaborators."""
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


async def test_close_then_ensure_creates_new_session(tmp_path):
    """After explicit close, ensure_http_session must create a new live session."""
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))
    s1 = await engine._ensure_http_session()
    await engine._close_http_session()
    s2 = await engine._ensure_http_session()
    assert s1 is not s2
    assert not s2.closed
    await engine._close_http_session()
