"""Chunked upload state must not accumulate orphaned entries forever."""
import time

import pytest

from noc_engine import NocEngine


def _config() -> dict:
    return {
        "charger_id": "T",
        "noc_server": {"host": "127.0.0.1", "port": 1},
        "charger_ip": "127.0.0.1",
        "charger_ports": {"system_api": 0, "charging_controller": 0,
                          "allocation_engine": 0, "error_generation": 0},
    }


async def test_orphan_upload_is_garbage_collected(tmp_path):
    engine = NocEngine(_config(), charger_id_cache_file=str(tmp_path / "c.json"))
    engine.chunked_upload_ttl = 0.5
    engine._chunked_uploads["abandoned"] = {
        "chunks": {0: b"data"},
        "total_chunks": 5,
        "file_name": "f.bin",
        "target": "x",
        "started_at": time.monotonic() - 10,  # already older than TTL
    }

    await engine._sweep_chunked_uploads_once()

    assert "abandoned" not in engine._chunked_uploads


async def test_fresh_upload_is_kept(tmp_path):
    engine = NocEngine(_config(), charger_id_cache_file=str(tmp_path / "c.json"))
    engine.chunked_upload_ttl = 60.0
    engine._chunked_uploads["fresh"] = {
        "chunks": {0: b"data"},
        "total_chunks": 5,
        "file_name": "f.bin",
        "target": "x",
        "started_at": time.monotonic(),
    }

    await engine._sweep_chunked_uploads_once()

    assert "fresh" in engine._chunked_uploads
