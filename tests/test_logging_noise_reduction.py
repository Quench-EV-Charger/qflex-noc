"""Behavioral tests for the qflex-noc logging-noise reduction sites."""
import logging

import pytest

from log_helpers import reset_log_caches


@pytest.fixture(autouse=True)
def _clean_caches():
    reset_log_caches()
    yield
    reset_log_caches()


class TestTelemetrySummary:
    """[NOC-Engine] 📡 Telemetry sent — should be a 1h-windowed summary, not per-tick INFO."""

    def test_no_per_tick_telemetry_sent_info(self, caplog):
        # Inspect the source to make sure the per-tick `logger.info("[NOC-Engine] 📡 Telemetry sent")`
        # is gone. The new code routes through PeriodicSummary.success().
        import inspect

        import noc_engine
        src = inspect.getsource(noc_engine.NocEngine._telemetry_loop)
        assert 'logger.info("[NOC-Engine] 📡 Telemetry sent")' not in src
        assert "_telemetry_summary" in src, (
            "telemetry loop must route via the PeriodicSummary instance"
        )

    def test_constructor_creates_telemetry_summary(self, tmp_path):
        from noc_engine import NocEngine
        cfg = {
            "charger_id": "T1",
            "noc_server": {"host": "127.0.0.1", "port": 1},
            "charger_ip": "127.0.0.1",
            "charger_ports": {"system_api": 0, "charging_controller": 0,
                              "allocation_engine": 0, "error_generation": 0},
        }
        engine = NocEngine(cfg, charger_id_cache_file=str(tmp_path / "c.json"))
        assert hasattr(engine, "_telemetry_summary")
        # Default window: 3600s.
        assert engine._telemetry_summary._window == 3600.0


class TestIncomingWSMessageSummary:
    def test_no_unconditional_incoming_ws_info(self):
        import inspect
        import noc_engine
        src = inspect.getsource(noc_engine.NocEngine._receive_loop)
        # Old line — should be gone entirely.
        assert "📥 INCOMING WS MESSAGE" not in src or "logger.debug" in src, (
            "INCOMING WS MESSAGE must be DEBUG-only, not INFO"
        )

    def test_proxy_request_routes_through_summary(self):
        import inspect
        import noc_engine
        src = inspect.getsource(noc_engine.NocEngine._receive_loop)
        assert "_proxy_request_summary.increment()" in src
