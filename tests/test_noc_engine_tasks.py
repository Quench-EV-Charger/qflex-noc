"""Background tasks dispatched from receive_loop must be tracked and cancellable."""
import asyncio
import logging

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


async def test_spawn_tracks_task_and_logs_exceptions(tmp_path, caplog):
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))

    async def boom():
        raise RuntimeError("kaboom")

    caplog.set_level(logging.ERROR, logger="noc_engine")

    t = engine._spawn_tracked(boom(), name="boom-task")
    assert t in engine._background_tasks

    # Wait for the task to finish so the discard callback runs.
    try:
        await asyncio.wait_for(asyncio.shield(t), timeout=1)
    except Exception:
        pass

    assert t not in engine._background_tasks
    assert any("kaboom" in rec.message for rec in caplog.records), (
        "exceptions in background tasks must be logged, not silently dropped"
    )


async def test_spawn_tracked_normal_completion_removes_task(tmp_path):
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))

    async def ok():
        return 42

    t = engine._spawn_tracked(ok(), name="ok-task")
    await t
    assert t not in engine._background_tasks
