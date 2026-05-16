"""log_helpers: log_on_change / RateLimitedLogger / PeriodicSummary / library config."""
import logging

import pytest

from log_helpers import (
    PeriodicSummary,
    RateLimitedLogger,
    _configure_library_loggers,
    log_on_change,
    reset_log_caches,
)


@pytest.fixture(autouse=True)
def _clean_caches():
    reset_log_caches()
    yield
    reset_log_caches()


def test_log_on_change_emits_only_on_value_change(caplog):
    logger = logging.getLogger("test.log_helpers")
    with caplog.at_level(logging.INFO, logger="test.log_helpers"):
        log_on_change(logger, "k1", 42, "v=42")
        log_on_change(logger, "k1", 42, "v=42")
        log_on_change(logger, "k1", 43, "v=43")
    msgs = [r.getMessage() for r in caplog.records]
    assert msgs == ["v=42", "v=43"]


def test_log_on_change_threshold_suppresses_small_deltas(caplog):
    logger = logging.getLogger("test.log_helpers")
    with caplog.at_level(logging.INFO, logger="test.log_helpers"):
        log_on_change(logger, "rate", 0.10, "r=0.10", threshold=0.5)
        log_on_change(logger, "rate", 0.30, "r=0.30", threshold=0.5)  # delta 0.2 suppressed
        log_on_change(logger, "rate", 0.80, "r=0.80", threshold=0.5)  # delta 0.7 logged
    msgs = [r.getMessage() for r in caplog.records]
    assert msgs == ["r=0.10", "r=0.80"]


def test_rate_limited_logger_backoff_schedule(caplog):
    logger = logging.getLogger("test.log_helpers")
    rl = RateLimitedLogger(logger, key="noc_url", schedule=(1, 10, 100))
    with caplog.at_level(logging.ERROR, logger="test.log_helpers"):
        for i in range(1, 121):
            rl.error("conn error #%d", i)
    records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(records) == 3
    # Use unambiguous form (the attempt counter ends with "]" so "#N]" is unique).
    assert "attempt #1]" in records[0].getMessage()
    assert "attempt #10]" in records[1].getMessage()
    assert "attempt #100]" in records[2].getMessage()


def test_rate_limited_logger_recovered_after_failure_streak(caplog):
    logger = logging.getLogger("test.log_helpers")
    rl = RateLimitedLogger(logger, key="noc_url", schedule=(1, 10))
    with caplog.at_level(logging.INFO, logger="test.log_helpers"):
        rl.error("fail #1")
        rl.error("fail #2")
        rl.ok("recovered")
        rl.ok("recovered again")  # idempotent — streak already cleared
    msgs = [r.getMessage() for r in caplog.records]
    assert any("fail #1" in m for m in msgs)
    assert any("recovered" in m and "2 failed attempt(s)" in m for m in msgs)
    # Second ok() must not produce an extra recovery line.
    assert sum("recovered" in m for m in msgs) == 1


def test_periodic_summary_emits_one_line_per_window(caplog, monkeypatch):
    logger = logging.getLogger("test.log_helpers")
    # Freeze monotonic time so the test is deterministic.
    fake_now = [1000.0]
    monkeypatch.setattr("log_helpers.time.monotonic", lambda: fake_now[0])

    ps = PeriodicSummary(logger, key="proxy_request", window_seconds=60.0)
    with caplog.at_level(logging.INFO, logger="test.log_helpers"):
        for _ in range(5):
            ps.increment()           # window 1: 5 events
        fake_now[0] += 70.0          # cross the window
        ps.increment()               # this call flushes the previous window
        fake_now[0] += 70.0
        ps.flush()                   # explicit flush emits whatever is left
    msgs = [r.getMessage() for r in caplog.records]
    assert sum("proxy_request" in m and "5" in m for m in msgs) == 1
    assert sum("proxy_request" in m and "1" in m and "5" not in m for m in msgs) == 1


def test_periodic_summary_status_flip_emits_inline(caplog):
    logger = logging.getLogger("test.log_helpers")
    ps = PeriodicSummary(logger, key="telemetry", window_seconds=3600.0)
    with caplog.at_level(logging.INFO, logger="test.log_helpers"):
        ps.success()
        ps.success()
        ps.failure("conn refused")     # OK -> FAIL flip — immediate INFO
        ps.failure("conn refused")     # still FAIL — no flip line
        ps.success()                   # FAIL -> OK flip — immediate INFO
    msgs = [r.getMessage() for r in caplog.records]
    flips = [m for m in msgs if "→" in m or "->" in m]
    assert len(flips) == 2, f"expected 2 flip lines, got: {msgs}"


def test_configure_library_loggers_silences_websockets():
    _configure_library_loggers()
    for name in ("websockets", "websockets.client", "websockets.server",
                 "websockets.protocol", "httpx", "asyncio"):
        assert logging.getLogger(name).level == logging.WARNING, name
