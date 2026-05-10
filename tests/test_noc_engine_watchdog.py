"""Watchdog forces reconnect when nothing has been received recently."""
import asyncio

import pytest

from noc_engine import NocEngine


def _config() -> dict:
    return {
        "charger_id": "TEST-CHG-1",
        "noc_server": {"host": "127.0.0.1", "port": 1},
        "charger_ip": "127.0.0.1",
        "charger_ports": {"system_api": 0, "charging_controller": 0,
                          "allocation_engine": 0, "error_generation": 0},
    }


class _FakeWS:
    """Minimal stand-in: always reports 'connected'. The watchdog never sends/receives."""
    connected = True


async def test_watchdog_returns_when_inbound_idle_exceeds_threshold(tmp_path):
    """If `_last_inbound_at` is never refreshed within the threshold, the watchdog returns."""
    engine = NocEngine(_config(), charger_id_cache_file=str(tmp_path / "c.json"))
    engine.inbound_idle_timeout = 1.0  # 1s threshold for fast test

    ws = _FakeWS()
    start = asyncio.get_event_loop().time()
    await asyncio.wait_for(engine._watchdog_loop(ws), timeout=5)  # type: ignore[arg-type]
    elapsed = asyncio.get_event_loop().time() - start

    # Should fire after roughly inbound_idle_timeout + one polling slice.
    assert 1.0 <= elapsed < 4.0, (
        f"watchdog fired at {elapsed:.2f}s, expected ~1-2s"
    )


async def test_watchdog_does_not_fire_when_inbound_kept_fresh(tmp_path):
    """While `_last_inbound_at` is refreshed, the watchdog must not return."""
    engine = NocEngine(_config(), charger_id_cache_file=str(tmp_path / "c.json"))
    engine.inbound_idle_timeout = 1.5

    ws = _FakeWS()
    keep_fresh = True

    async def feeder():
        while keep_fresh:
            engine._last_inbound_at = asyncio.get_event_loop().time()
            await asyncio.sleep(0.3)

    feeder_task = asyncio.create_task(feeder())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(engine._watchdog_loop(ws), timeout=3)  # type: ignore[arg-type]
    finally:
        keep_fresh = False
        feeder_task.cancel()
        try:
            await feeder_task
        except (asyncio.CancelledError, BaseException):
            pass


async def test_watchdog_returns_when_disconnected(tmp_path):
    """If the WS reports disconnected, the watchdog returns within one polling slice."""
    engine = NocEngine(_config(), charger_id_cache_file=str(tmp_path / "c.json"))
    # Polling cadence is min(timeout/4, 5.0) — pick a value that yields ~1s slices
    engine.inbound_idle_timeout = 4.0

    class _DisconnectedWS:
        connected = False

    start = asyncio.get_event_loop().time()
    await asyncio.wait_for(engine._watchdog_loop(_DisconnectedWS()), timeout=4)  # type: ignore[arg-type]
    elapsed = asyncio.get_event_loop().time() - start
    # First poll waits ~1s then sees ws.connected=False and returns.
    assert elapsed < 2.0, f"watchdog took {elapsed:.2f}s to notice disconnect"
