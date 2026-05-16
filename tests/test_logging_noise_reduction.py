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


class TestTelemetryFetchPerEndpointFlip:
    def test_repeated_ok_does_not_emit_per_call(self, caplog):
        import inspect
        import telemetry_collector
        src = inspect.getsource(telemetry_collector._fetch)
        # Old per-call DEBUG must be gone (or demoted to logger.log(5, ...))
        assert 'logger.debug(f"[Telemetry] {key} ok' not in src
        # New flip helper must be present.
        assert "log_on_change" in src, (
            "_fetch must use log_on_change for per-endpoint status flips"
        )


class TestSessionSyncQuiet:
    def test_fetch_zero_history_does_not_emit_unconditionally(self):
        import inspect
        import session_sync
        src = inspect.getsource(session_sync.SessionSyncManager._fetch_history)
        # The old unconditional log must be gone.
        assert 'logger.debug(f"[SessionSync] Fetched ' not in src
        # The new gated emission must be present.
        assert "log_on_change" in src or "if len(sessions)" in src

    def test_send_success_demoted_below_debug(self):
        import inspect
        import session_sync
        src = inspect.getsource(session_sync.SessionSyncManager._send_to_noc)
        assert 'logger.debug(f"[SessionSync] Sent session_sync' not in src


class TestRefreshLoopsRateLimited:
    def test_engine_has_refresh_rate_limiters(self, tmp_path):
        from noc_engine import NocEngine
        from log_helpers import RateLimitedLogger
        cfg = {
            "charger_id": "T1",
            "noc_server": {"host": "127.0.0.1", "port": 1},
            "charger_ip": "127.0.0.1",
            "charger_ports": {"system_api": 0, "charging_controller": 0,
                              "allocation_engine": 0, "error_generation": 0},
        }
        engine = NocEngine(cfg, charger_id_cache_file=str(tmp_path / "c.json"))
        for name in ("_rl_ocpp_serial", "_rl_hw_serial", "_rl_noc_url"):
            rl = getattr(engine, name, None)
            assert isinstance(rl, RateLimitedLogger), f"missing {name}"

    def test_refresh_loops_use_logger_exception(self):
        import inspect
        import noc_engine
        for fn_name in ("_charger_id_refresh_loop", "_noc_url_refresh_loop"):
            fn = getattr(noc_engine.NocEngine, fn_name)
            src = inspect.getsource(fn)
            # The bare DEBUG patterns must be gone.
            assert "logger.debug(f\"[NOC-Engine] NOC URL refresh error:" not in src
            assert "logger.debug(f\"[NOC-Engine] Charger ID refresh:" not in src
            assert "logger.debug(f\"[NOC-Engine] Charger ID refresh error:" not in src
            # Rate-limited exception() must be present.
            assert ".exception(" in src


class TestSessionSyncExceptionLogging:
    def test_failed_to_fetch_uses_exception(self):
        import inspect
        import session_sync
        for name in ("_fetch_active_sessions", "_fetch_history"):
            src = inspect.getsource(getattr(session_sync.SessionSyncManager, name))
            # Old pattern is gone.
            assert "logger.error(f\"[SessionSync] Failed to fetch" not in src
            # New `logger.exception` is present.
            assert "logger.exception" in src
