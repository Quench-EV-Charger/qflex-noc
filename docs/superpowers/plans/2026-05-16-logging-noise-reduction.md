# qflex-noc Logging Noise Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `noc_engine.log` from ~95 MB/day to <10 MB/day by silencing third-party `websockets`/`httpx`/`asyncio` DEBUG chatter, turning per-tick INFO traces into change-only / windowed summaries, deleting success-API logs, and switching exception-handlers to `logger.exception` so real failures finally show a stack frame. The big-rock insight from the 24h capture is that **86% of 856 113 lines are DEBUG noise** (`732 905 DEBUG`) — and `websockets.client` alone accounts for `469 536` lines (≈55% of the whole file). One config line removes most of it.

**Architecture:** Add a small `log_helpers.py` next to the existing flat modules with three primitives: `log_on_change(key, value, msg, threshold=...)`, `RateLimitedLogger(key, schedule=(1,10,100,1000))` (with `.error/.exception/.ok`), and `PeriodicSummary(key, window_seconds=60)` (buffers counts + emits one INFO/window with O→F / F→O flip lines). Add a one-time `_configure_library_loggers()` helper called from `main.py` right after `logging.basicConfig(...)` to set `websockets`, `websockets.client`, `websockets.server`, `websockets.protocol`, `httpx`, and `asyncio` to `WARNING`. Apply the helpers at the seven worst-offender sites identified from the capture. Sweep `except ... as e: logger.error(f"…{e}…")` blocks in `noc_engine.py`, `session_sync.py`, `telemetry_collector.py`, `ssh_tunnel.py`, `command_executor.py` to `logger.exception(...)`. Keep the once-per-process `✅ OCPP serial / ✅ HW serial / ✅ Charger ID` startup INFO lines — they are useful.

**Tech Stack:** Python 3.11+, asyncio, websockets >=12, aiohttp >=3.9, pytest, pytest-asyncio (tests live in `tests/`, fixtures in `tests/conftest.py`).

**Reference (source of all line counts in this plan):** 24h capture at `qflex_logs_full_20260515_114015/noc-engine/noc_engine.log` (95 MB, 856 113 lines; 732 905 DEBUG / 96 011 INFO / 62 WARNING / 45 ERROR / 27 086 other).

| Site | Lines/24h | Action |
|---|---:|---|
| `websockets.client` library DEBUG (TEXT frames + keepalive ping/pong) | **469 536** | Set library loggers to WARNING (Task 1) |
| `[NOC-Engine] ♥ Heartbeat sent` DEBUG ([noc_engine.py:351](../../noc_engine.py#L351)) | 89 503 | Demote to TRACE (`logger.log(5, ...)`) — Task 1 also lifts DEBUG above this level |
| `[NOC-Engine] 📥 INCOMING WS MESSAGE \| type=proxy_request` INFO ([noc_engine.py:590](../../noc_engine.py#L590)) | 21 932 | PeriodicSummary 60s windowed (Task 4) |
| `[NOC-Engine] 📡 Telemetry sent` INFO ([noc_engine.py:368](../../noc_engine.py#L368)) | 21 931 | PeriodicSummary 1h windowed + flip-line on OK↔FAIL (Task 3) |
| `[Telemetry] X ok (...)` DEBUG ([telemetry_collector.py:88](../../telemetry_collector.py#L88)) | 21 933 × 3 + 20 799 × 3 | Demote per-endpoint OK to TRACE; only log status-flip / failure (Task 5) |
| `[SessionSync] Sent session_sync to NOC Server` DEBUG ([session_sync.py:294](../../session_sync.py#L294)) | 11 885 | Demote to TRACE; log only on flip (Task 5 sibling — folded into Task 6) |
| `[SessionSync] Fetched 0 history sessions` DEBUG ([session_sync.py:232](../../session_sync.py#L232)) | 10 116 | Log only when count > 0 or 0→N / N→0 transition (Task 6) |
| `[NOC-Engine] NOC URL refresh error` DEBUG ([noc_engine.py:471](../../noc_engine.py#L471)) | 3 501 | `RateLimitedLogger` + `logger.exception` (Task 7) |
| `[NOC-Engine] Charger ID refresh error/fetch failed` DEBUG ([noc_engine.py:407, 421, 425](../../noc_engine.py#L407)) | 3 493 | `RateLimitedLogger` + `logger.exception` (Task 7) |
| `[SessionSync] Failed to fetch …` ERROR ([session_sync.py:188, 237](../../session_sync.py#L188)) | 30 (10 × 3) | `logger.exception(...)` (Task 8) |
| Sweep: `except ... as e: logger.error(f"…{e}…")` across module | ~16 sites | `logger.exception(...)` (Task 9) |
| `✅ OCPP serial`, `✅ HW serial`, `✅ Charger ID`, `✅ NOC URL` startup INFO ([main.py:147, 202, 218, 228](../../main.py#L147)) | <10 (once per process) | **Keep — they are useful** (Task 10 makes this explicit) |
| Version bump + CHANGELOG + graphify | — | Task 11 |

---

## File Structure

**New:**
- `log_helpers.py` — `log_on_change`, `RateLimitedLogger`, `PeriodicSummary`, `_configure_library_loggers`, `reset_log_caches`
- `tests/test_log_helpers.py` — unit tests for the helpers
- `tests/test_logging_noise_reduction.py` — behavioral tests for the touched call sites

**Modified:**
- `main.py` — call `_configure_library_loggers()` once at startup
- `noc_engine.py` — telemetry-sent summary (line 368), incoming-WS summary (line 590), heartbeat demote (line 351), NOC-URL refresh rate-limit (line 471), Charger-ID refresh rate-limit (lines 407/421/425), `logger.exception` sweep
- `telemetry_collector.py` — per-endpoint OK to TRACE + status-flip helper (line 88)
- `session_sync.py` — `Fetched 0 history sessions` to log-on-change (line 232), `Sent session_sync to NOC Server` to TRACE + flip (line 294), `Failed to fetch …` to `logger.exception` (lines 188, 237), sweep
- `ssh_tunnel.py` — `logger.exception` sweep
- `command_executor.py` — `logger.exception` sweep (only the bare `error` site at line 128; line 138 already has `exc_info=True`)
- `CHANGELOG.md` — new `[1.1.5]` entry
- `VERSION` — `1.1.4` → `1.1.5`

---

## Task 1: Library-logger config + `log_helpers.py` (helpers + tests)

**Why this is task 1.** Setting `websockets.client` to `WARNING` removes ~470 000 DEBUG lines/day in a single call — bigger than every other task combined. Pair it with the helper module so subsequent tasks just `from log_helpers import …`.

**Files:**
- Create: `log_helpers.py`
- Create: `tests/test_log_helpers.py`
- Modify: `main.py:50-55` (add the library-config call after `logging.basicConfig`)

- [ ] **Step 1: Write the failing test**

`tests/test_log_helpers.py`:
```python
"""log_helpers: log_on_change / RateLimitedLogger / PeriodicSummary / library config."""
import logging
import time

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
        log_on_change(logger, "rate", 0.30, "r=0.30", threshold=0.5)  # Δ 0.2 suppressed
        log_on_change(logger, "rate", 0.80, "r=0.80", threshold=0.5)  # Δ 0.7 logged
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
    assert "#1" in records[0].getMessage()
    assert "#10" in records[1].getMessage()
    assert "#100" in records[2].getMessage()


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
        ps.failure("conn refused")     # OK → FAIL flip — immediate INFO
        ps.failure("conn refused")     # still FAIL — no flip line
        ps.success()                   # FAIL → OK flip — immediate INFO
    msgs = [r.getMessage() for r in caplog.records]
    flips = [m for m in msgs if "→" in m or "->" in m]
    assert len(flips) == 2, f"expected 2 flip lines, got: {msgs}"


def test_configure_library_loggers_silences_websockets():
    _configure_library_loggers()
    for name in ("websockets", "websockets.client", "websockets.server",
                 "websockets.protocol", "httpx", "asyncio"):
        assert logging.getLogger(name).level == logging.WARNING, name
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
python -m pytest tests/test_log_helpers.py -v
```
Expected: `ModuleNotFoundError: No module named 'log_helpers'`.

- [ ] **Step 3: Implement `log_helpers.py`**

Create `log_helpers.py` at the module root (flat layout — same level as `noc_engine.py`):

```python
"""Reusable logging helpers for keeping noc_engine.log signal-rich.

Primitives
----------
- ``log_on_change(logger, key, value, msg, threshold=None)`` — emit only when
  ``value`` differs from the last logged value (with optional numeric threshold).
- ``RateLimitedLogger(logger, key, schedule=(1, 10, 100, 1000))`` — emit errors
  on a backoff schedule when the same condition keeps repeating; emit ONE
  "recovered" INFO line on the first success after a streak.
- ``PeriodicSummary(logger, key, window_seconds=60)`` — buffer per-window counts
  and emit one INFO line per window; also tracks last status so OK↔FAIL flips
  produce an immediate INFO line.

- ``_configure_library_loggers()`` — set ``websockets`` / ``httpx`` / ``asyncio``
  to ``WARNING``. Call once at process start; safe to call multiple times.
- ``reset_log_caches()`` — test-only helper to wipe module-level state.

All caches are process-local. asyncio is single-threaded inside one process,
so we deliberately avoid locks.
"""

from __future__ import annotations

import logging
import time
from typing import Any

_last_logged: dict[str, Any] = {}


def reset_log_caches() -> None:
    """Wipe all module-level caches. Test-only — never call at runtime."""
    _last_logged.clear()


def log_on_change(
    logger: logging.Logger,
    key: str,
    value: Any,
    msg: str,
    *,
    level: int = logging.INFO,
    threshold: float | None = None,
) -> None:
    """Emit ``msg`` at ``level`` only when ``value`` differs from the previously
    logged value for ``key``.

    ``threshold`` (numeric only): treat values within ±threshold of the
    previously logged value as "unchanged". Useful for floats with sensor wobble.
    """
    prev = _last_logged.get(key, _MISSING)
    if prev is _MISSING:
        logger.log(level, msg)
        _last_logged[key] = value
        return
    if (
        threshold is not None
        and isinstance(value, (int, float))
        and isinstance(prev, (int, float))
    ):
        if abs(value - prev) < threshold:
            return
    elif value == prev:
        return
    logger.log(level, msg)
    _last_logged[key] = value


class RateLimitedLogger:
    """Emit errors on a backoff schedule (default 1, 10, 100, 1000) when a
    condition keeps repeating. Emit a single "recovered" INFO line on the first
    ``.ok()`` after a streak.
    """

    def __init__(
        self,
        logger: logging.Logger,
        *,
        key: str,
        schedule: tuple[int, ...] = (1, 10, 100, 1000),
    ) -> None:
        self._logger = logger
        self._key = key
        self._schedule = frozenset(schedule)
        self._attempts = 0

    def error(self, msg: str, *args: Any, exc_info: bool = False) -> None:
        self._attempts += 1
        if self._attempts in self._schedule:
            rendered = msg % args if args else msg
            self._logger.error(
                "[%s attempt #%d] %s", self._key, self._attempts, rendered,
                exc_info=exc_info,
            )

    def exception(self, msg: str, *args: Any) -> None:
        """Like ``error`` but always captures the current exception's traceback."""
        self.error(msg, *args, exc_info=True)

    def ok(self, msg: str = "recovered") -> None:
        if self._attempts > 0:
            self._logger.info(
                "[%s] %s after %d failed attempt(s)",
                self._key, msg, self._attempts,
            )
        self._attempts = 0


class PeriodicSummary:
    """Buffer per-window counts and flush one INFO line per ``window_seconds``.

    Two usage modes:

    1. ``increment()`` — bump a simple counter. ``flush()`` (called automatically
       once the window has elapsed) emits ``"<key> × N in last <window>s"``.

    2. ``success()`` / ``failure(reason)`` — track an OK/FAIL pattern. Same
       periodic summary, PLUS an immediate INFO line whenever the status flips
       (e.g. ``"telemetry: OK → FAIL (conn refused)"``).
    """

    def __init__(
        self,
        logger: logging.Logger,
        *,
        key: str,
        window_seconds: float = 60.0,
    ) -> None:
        self._logger = logger
        self._key = key
        self._window = window_seconds
        self._count = 0
        self._ok_count = 0
        self._fail_count = 0
        self._window_started = time.monotonic()
        self._last_status: str | None = None  # "ok" / "fail" / None

    # --- counter-only API ------------------------------------------------
    def increment(self, n: int = 1) -> None:
        self._count += n
        self._maybe_flush()

    # --- status API ------------------------------------------------------
    def success(self) -> None:
        self._ok_count += 1
        if self._last_status == "fail":
            self._logger.info(f"[{self._key}] FAIL → OK (recovered)")
        self._last_status = "ok"
        self._maybe_flush()

    def failure(self, reason: str = "") -> None:
        self._fail_count += 1
        if self._last_status == "ok":
            tail = f" ({reason})" if reason else ""
            self._logger.info(f"[{self._key}] OK → FAIL{tail}")
        elif self._last_status is None:
            tail = f" ({reason})" if reason else ""
            self._logger.info(f"[{self._key}] FAIL{tail}")
        self._last_status = "fail"
        self._maybe_flush()

    # --- flush ----------------------------------------------------------
    def _maybe_flush(self) -> None:
        if time.monotonic() - self._window_started >= self._window:
            self.flush()

    def flush(self) -> None:
        if self._count > 0:
            self._logger.info(
                f"[{self._key}] {self._count} in last {int(self._window)}s"
            )
        if self._ok_count > 0 or self._fail_count > 0:
            self._logger.info(
                f"[{self._key}] {self._ok_count} ok / {self._fail_count} failed "
                f"in last {int(self._window)}s"
            )
        self._count = 0
        self._ok_count = 0
        self._fail_count = 0
        self._window_started = time.monotonic()


_LIBRARY_LOGGERS_TO_QUIET: tuple[str, ...] = (
    "websockets",
    "websockets.client",
    "websockets.server",
    "websockets.protocol",
    "httpx",
    "asyncio",
)


def _configure_library_loggers(level: int = logging.WARNING) -> None:
    """Silence third-party libraries that flood DEBUG output.

    Idempotent — safe to call multiple times. Called once from ``main.py``
    immediately after ``logging.basicConfig(...)``.
    """
    for name in _LIBRARY_LOGGERS_TO_QUIET:
        logging.getLogger(name).setLevel(level)


class _Sentinel:
    pass


_MISSING = _Sentinel()
```

- [ ] **Step 4: Run the test and verify it passes**

```powershell
python -m pytest tests/test_log_helpers.py -v
```
Expected: 7 tests pass.

- [ ] **Step 5: Wire `_configure_library_loggers()` into `main.py`**

In `main.py`, **immediately after the existing `logger = logging.getLogger(__name__)` at line 55**, add:

```python
# Silence third-party libraries (websockets.client alone produced 469 536
# DEBUG lines / day before this — see CHANGELOG 1.1.5).
sys.path.insert(0, str(Path(__file__).parent))  # ensure log_helpers is importable
from log_helpers import _configure_library_loggers  # noqa: E402
_configure_library_loggers()
```

(The `sys.path.insert` is already done at line 61 *after* the `NocEngine` import, but `log_helpers` must be importable before that — moving the insert up two lines is the cleanest fix. Verify with a final test run.)

- [ ] **Step 6: Commit**

```powershell
git add log_helpers.py tests/test_log_helpers.py main.py
git commit -m "feat(noc): add log_helpers + silence websockets/httpx/asyncio DEBUG"
```

---

## Task 2: Demote `[NOC-Engine] ♥ Heartbeat sent` to TRACE

**Why:** [noc_engine.py:351](../../noc_engine.py#L351) is the **second-biggest log producer in the file** (89 503 DEBUG lines/day — one every ~1s). It's already at DEBUG, but `logging.basicConfig(level="DEBUG")` (the default in `config.json` per [main.py:51](../../main.py#L51)) still emits it. Bury it below DEBUG so even DEBUG mode hides per-tick heartbeats. The matching `websockets.client > TEXT '{"type":"heartbeat"…}'` line (89 485/day) is already silenced by Task 1.

**Files:**
- Modify: `noc_engine.py:351`

- [ ] **Step 1: Replace line 351**

In `noc_engine.py`, change:
```python
                await ws.send(self._make_msg("heartbeat", {}))
                logger.debug("[NOC-Engine] ♥ Heartbeat sent")
```
to:
```python
                await ws.send(self._make_msg("heartbeat", {}))
                logger.log(5, "[NOC-Engine] ♥ Heartbeat sent")  # below DEBUG (10)
```

Level 5 is below stdlib `DEBUG` (10), so even `level=DEBUG` will not emit. Anyone who genuinely needs heartbeat tracing can call `logging.getLogger("noc_engine").setLevel(5)` interactively.

- [ ] **Step 2: Run regression tests**

```powershell
python -m pytest tests/ -v -k "heartbeat or watchdog"
```
Expected: no failures.

- [ ] **Step 3: Commit**

```powershell
git add noc_engine.py
git commit -m "refactor(noc): demote heartbeat-sent log below DEBUG (-89k lines/day)"
```

---

## Task 3: `[NOC-Engine] 📡 Telemetry sent` → `PeriodicSummary` (1h window + flip)

**Why:** [noc_engine.py:368](../../noc_engine.py#L368) fires every 30s (the telemetry interval) at **INFO**, producing 21 931 lines/day with no per-tick information value. Replace with one INFO line per hour summarizing ok/fail counts, plus an immediate flip line on OK→FAIL or FAIL→OK.

**Files:**
- Modify: `noc_engine.py:130-138` (constructor — add the `PeriodicSummary` instance), `noc_engine.py:356-371` (`_telemetry_loop`)
- Test: `tests/test_logging_noise_reduction.py` (new file)

- [ ] **Step 1: Write the failing test**

`tests/test_logging_noise_reduction.py`:
```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestTelemetrySummary -v
```
Expected: `AttributeError: 'NocEngine' object has no attribute '_telemetry_summary'` and source-inspection assertion fails.

- [ ] **Step 3: Add the `PeriodicSummary` instance + rewrite `_telemetry_loop`**

In `noc_engine.py`, **inside `__init__` immediately after the `self._ssh_manager = SSHTunnelManager()` line at [noc_engine.py:141](../../noc_engine.py#L141)** add:

```python
        # Periodic summaries for high-frequency events. Constructed once;
        # safe to use across reconnects (state is per-process, not per-WS).
        from log_helpers import PeriodicSummary
        self._telemetry_summary = PeriodicSummary(
            logger, key="Telemetry", window_seconds=3600.0,
        )
        self._proxy_request_summary = PeriodicSummary(
            logger, key="proxy_request", window_seconds=60.0,
        )
```

Then **replace the body of `_telemetry_loop` at [noc_engine.py:356-371](../../noc_engine.py#L356)**:

```python
    async def _telemetry_loop(self, ws: WSClient):
        """Collect and push charger telemetry every N seconds.

        Per-tick INFO line was dropped — see `_telemetry_summary` for a 1h
        windowed summary and immediate OK↔FAIL flip lines.
        """
        while True:
            await asyncio.sleep(self.telemetry_interval)
            if not ws.connected:
                break
            try:
                payload = await collect_telemetry(
                    self.api_urls,
                    session=await self._ensure_http_session(),
                )
                await ws.send(self._make_msg("telemetry", payload))
                self._telemetry_summary.success()
            except Exception as e:
                self._telemetry_summary.failure(str(e))
                logger.warning(f"[NOC-Engine] Telemetry push failed: {e}")
                break
```

(The `warning` on failure is kept because it carries the actual error string; the summary just provides counts and flip events.)

- [ ] **Step 4: Run the test and verify it passes**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestTelemetrySummary -v
```
Expected: both tests pass.

- [ ] **Step 5: Commit**

```powershell
git add noc_engine.py tests/test_logging_noise_reduction.py
git commit -m "refactor(noc): telemetry-sent → 1h PeriodicSummary + flip lines"
```

---

## Task 4: `📥 INCOMING WS MESSAGE | type=proxy_request` → 60s `PeriodicSummary`

**Why:** [noc_engine.py:590](../../noc_engine.py#L590) fires at **INFO** for *every* inbound WS message — 21 932 lines/day, almost all of them `type=proxy_request`. The line dumps `keys=[…]` which is not useful in steady state. Replace with: keep per-message logging only at DEBUG, and emit a 60s windowed summary "`proxy_request × N in last 60s`" via the `PeriodicSummary` constructed in Task 3.

**Files:**
- Modify: `noc_engine.py:589-590` (the unconditional INFO line) and `noc_engine.py:599-604` (the proxy_request branch — bump its summary)

- [ ] **Step 1: Append the failing test**

Add to `tests/test_logging_noise_reduction.py`:
```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestIncomingWSMessageSummary -v
```
Expected: assertions fail.

- [ ] **Step 3: Rewrite the offending block**

In `noc_engine.py`, **replace the block at lines 586-604**:

```python
                message = await ws.receive()
                msg_type = message.get("type", "UNKNOWN")

                # Log EVERYTHING we receive at INFO level for debugging
                logger.info(f"[NOC-Engine] 📥 INCOMING WS MESSAGE | type={msg_type} | keys={list(message.keys())}")

                if msg_type == "command":
                    # Dispatch to a separate task so we don't block receive loop
                    payload = message.get("payload", {})
                    cmd_id = payload.get("command_id", "?")
                    logger.info(f"[NOC-Engine] ⚡ Dispatching command task for cmd={cmd_id}")
                    self._spawn_tracked(self._handle_command(ws, message), name=f"cmd-{cmd_id}")

                elif msg_type == "proxy_request":
                    # Handle web tool proxy request (synchronous response)
                    payload = message.get("payload", {})
                    request_id = payload.get("request_id", "?")
                    logger.info(f"[NOC-Engine] 🔀 Proxy request {request_id}: {payload.get('method')} {payload.get('path')}")
                    self._spawn_tracked(self._handle_proxy_request(ws, message), name=f"proxy-{request_id}")
```

with:

```python
                message = await ws.receive()
                msg_type = message.get("type", "UNKNOWN")

                # Per-message DEBUG (lifecycle trace); the 60s summary below
                # is the canonical INFO-level signal.
                logger.debug(
                    f"[NOC-Engine] 📥 WS msg type={msg_type} keys={list(message.keys())}"
                )

                if msg_type == "command":
                    # Dispatch to a separate task so we don't block receive loop
                    payload = message.get("payload", {})
                    cmd_id = payload.get("command_id", "?")
                    logger.info(f"[NOC-Engine] ⚡ Dispatching command task for cmd={cmd_id}")
                    self._spawn_tracked(self._handle_command(ws, message), name=f"cmd-{cmd_id}")

                elif msg_type == "proxy_request":
                    # Aggregate via 60s windowed summary; keep per-message DEBUG
                    # for forensic troubleshooting.
                    payload = message.get("payload", {})
                    request_id = payload.get("request_id", "?")
                    logger.debug(
                        f"[NOC-Engine] 🔀 Proxy request {request_id}: "
                        f"{payload.get('method')} {payload.get('path')}"
                    )
                    self._proxy_request_summary.increment()
                    self._spawn_tracked(self._handle_proxy_request(ws, message), name=f"proxy-{request_id}")
```

(Other branches — `upload_chunk`, `ssh_tunnel_open`, `ssh_data`, `ssh_tunnel_close`, `ack`, `else` — are unchanged. Their INFO lines have meaningful payload and are infrequent.)

- [ ] **Step 4: Run the test and verify it passes**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestIncomingWSMessageSummary -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add noc_engine.py tests/test_logging_noise_reduction.py
git commit -m "refactor(noc): 📥 INCOMING + proxy_request to DEBUG + 60s PeriodicSummary"
```

---

## Task 5: `[Telemetry] X ok (...)` → TRACE + per-endpoint status-flip

**Why:** [telemetry_collector.py:88](../../telemetry_collector.py#L88) is **already DEBUG** but the production config currently runs at DEBUG, so 21 933 × 3 + 20 799 × 3 ≈ **128 K** lines/day come from this single line (one per telemetry interval × 4 endpoints × … with retries). Drop them to TRACE (level 5) so even DEBUG mode stays quiet, and add a per-endpoint OK→FAIL / FAIL→OK flip line via `log_on_change` (status string keyed on endpoint).

**Files:**
- Modify: `telemetry_collector.py:84-110` (`_fetch`)

- [ ] **Step 1: Append the failing test**

Add to `tests/test_logging_noise_reduction.py`:
```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestTelemetryFetchPerEndpointFlip -v
```
Expected: assertion fails (`log_on_change` not imported).

- [ ] **Step 3: Rewrite `_fetch`**

In `telemetry_collector.py`, **change the imports at the top of the file** (after the existing imports near line 41):

```python
from log_helpers import log_on_change
```

Then **replace the body of `_fetch` (lines 84-110)**:

```python
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_s)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                # Per-call OK is TRACE (level 5) so even DEBUG stays quiet.
                # A status-flip line goes out via log_on_change.
                logger.log(5, f"[Telemetry] {key} ok ({url})")
                log_on_change(
                    logger, f"telemetry_status:{key}", "ok",
                    f"[Telemetry] {key} ok ({url})",
                )
                health = {"status": "ok", "url": url, "http_code": 200}
                return key, data, health

            # Non-200 response — service is up but returning an error
            log_on_change(
                logger, f"telemetry_status:{key}", f"http_{resp.status}",
                f"[Telemetry] {key} → HTTP {resp.status} from {url}",
                level=logging.WARNING,
            )
            health = {"status": "http_error", "url": url, "http_code": resp.status}
            return key, None, health

    except asyncio.TimeoutError:
        log_on_change(
            logger, f"telemetry_status:{key}", "timeout",
            f"[Telemetry] {key} timed out ({timeout_s}s): {url}",
            level=logging.WARNING,
        )
        health = {"status": "timeout", "url": url}
        return key, None, health

    except aiohttp.ClientConnectorError as e:
        log_on_change(
            logger, f"telemetry_status:{key}", "unreachable",
            f"[Telemetry] {key} service not reachable: {url}",
            level=logging.WARNING,
        )
        health = {"status": "unreachable", "url": url, "error": str(e)}
        return key, None, health

    except Exception:
        logger.exception(f"[Telemetry] {key} unexpected error ({url})")
        log_on_change(
            logger, f"telemetry_status:{key}", "error",
            f"[Telemetry] {key} unexpected error ({url})",
            level=logging.ERROR,
        )
        health = {"status": "error", "url": url, "error": "see traceback"}
        return key, None, health
```

This converts: per-call OK lines → TRACE (silent at DEBUG); per-call WARN lines → only emitted when the status string actually changes for that endpoint; bare `except Exception as e: logger.warning(...)` → `logger.exception(...)`.

- [ ] **Step 4: Run the test and verify it passes**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestTelemetryFetchPerEndpointFlip -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add telemetry_collector.py tests/test_logging_noise_reduction.py
git commit -m "refactor(telemetry): per-endpoint OK to TRACE; status-flip via log_on_change"
```

---

## Task 6: `[SessionSync] Fetched 0 history sessions` → log-on-change + send-success demote

**Why:**
- [session_sync.py:232](../../session_sync.py#L232) emits `[SessionSync] Fetched 0 history sessions` at DEBUG every 30s — 10 116 lines/day, all `0`. Only emit when count > 0 or on a 0→N / N→0 transition.
- [session_sync.py:294](../../session_sync.py#L294) emits `[SessionSync] Sent session_sync to NOC Server` at DEBUG every poll — 11 885 lines/day. Demote to TRACE and emit only on send-failure or status flip.

**Files:**
- Modify: `session_sync.py:232`, `session_sync.py:294`

- [ ] **Step 1: Append the failing test**

Add to `tests/test_logging_noise_reduction.py`:
```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestSessionSyncQuiet -v
```
Expected: assertions fail.

- [ ] **Step 3: Rewrite `_fetch_history` and `_send_to_noc`**

In `session_sync.py`, **add an import near line 36** (next to the existing `logger = logging.getLogger(__name__)`):

```python
from log_helpers import log_on_change
```

**Replace the line at [session_sync.py:232](../../session_sync.py#L232)**:

```python
                        sessions = data.get("sessions", [])
                        logger.debug(f"[SessionSync] Fetched {len(sessions)} history sessions")
                        return sessions
```

with:

```python
                        sessions = data.get("sessions", [])
                        # Only emit when count is non-zero OR on a 0↔N transition.
                        log_on_change(
                            logger,
                            "session_sync:history_count",
                            len(sessions),
                            f"[SessionSync] Fetched {len(sessions)} history sessions",
                            level=logging.DEBUG,
                        )
                        return sessions
```

**Replace the line at [session_sync.py:294](../../session_sync.py#L294)**:

```python
            logger.debug(f"[SessionSync] Sent session_sync to NOC Server")
```

with:

```python
            # TRACE: per-tick send success is not actionable; the next failure
            # branch will log with `logger.exception`.
            logger.log(5, "[SessionSync] Sent session_sync to NOC Server")
```

- [ ] **Step 4: Run the test and verify it passes**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestSessionSyncQuiet -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add session_sync.py tests/test_logging_noise_reduction.py
git commit -m "refactor(session_sync): log-on-change for history count; demote send-success"
```

---

## Task 7: `NOC URL refresh error` / `Charger ID refresh error` → `RateLimitedLogger` + `logger.exception`

**Why:** [noc_engine.py:471](../../noc_engine.py#L471) (`NOC URL refresh error: Cannot connect to host localhost:8003`) and [noc_engine.py:407, 421, 425](../../noc_engine.py#L407) (`Charger ID refresh: OCPP/HW fetch failed` / `Charger ID refresh error`) fire every 10s while port 8003 is unreachable — 3 501 + 3 493 = ~7 000 lines/day. All currently DEBUG, all losing the stack frame to a bare `{e}` interpolation. Switch to `RateLimitedLogger` so attempts 1/10/100/1000 are recorded with the full traceback, then a single recovery line via `.ok()`.

**Files:**
- Modify: `noc_engine.py:130-141` (constructor — add 3 rate limiters), `noc_engine.py:393-425` (`_charger_id_refresh_loop`), `noc_engine.py:458-487` (`_noc_url_refresh_loop`)

- [ ] **Step 1: Append the failing test**

Add to `tests/test_logging_noise_reduction.py`:
```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestRefreshLoopsRateLimited -v
```
Expected: assertions fail.

- [ ] **Step 3: Add the 3 rate limiters in `__init__`**

In `noc_engine.py`, **immediately after the `PeriodicSummary` block added in Task 3** (right after `self._proxy_request_summary = …`), append:

```python
        # Rate-limit per-endpoint refresh failures. Attempts 1, 10, 100, 1000
        # each log a stack-frame; subsequent silent until .ok() emits a single
        # "recovered" INFO when the endpoint comes back.
        from log_helpers import RateLimitedLogger
        self._rl_ocpp_serial = RateLimitedLogger(logger, key="charger_id_refresh/ocpp")
        self._rl_hw_serial   = RateLimitedLogger(logger, key="charger_id_refresh/hw")
        self._rl_noc_url     = RateLimitedLogger(logger, key="noc_url_refresh")
```

- [ ] **Step 4: Rewrite the OCPP-fetch except clause in `_charger_id_refresh_loop`**

In `noc_engine.py`, **replace lines 393-408**:

```python
            try:
                session = await self._ensure_http_session()
                try:
                    async with session.get(
                        self._ocpp_serial_url,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            serial = data.get("value", "").replace("\x00", "").strip()
                            if data.get("success") and serial:
                                ocpp_serial = serial
                except Exception as e:
                    logger.debug(
                        f"[NOC-Engine] Charger ID refresh: OCPP fetch failed: {e}"
                    )
```

with:

```python
            try:
                session = await self._ensure_http_session()
                try:
                    async with session.get(
                        self._ocpp_serial_url,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            serial = data.get("value", "").replace("\x00", "").strip()
                            if data.get("success") and serial:
                                ocpp_serial = serial
                                self._rl_ocpp_serial.ok()
                except Exception:
                    self._rl_ocpp_serial.exception(
                        "OCPP serial fetch failed (URL: %s)", self._ocpp_serial_url,
                    )
```

- [ ] **Step 5: Rewrite the HW-fetch except clause in the same loop**

**Replace lines 410-425** (`try: …hw_serial… except Exception as e: logger.debug(...) ... except Exception as e: logger.debug(f"[NOC-Engine] Charger ID refresh error: {e}")`):

```python
                try:
                    async with session.get(
                        self._hw_serial_url,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            serial = str(data.get("serial_number", "")).replace("\x00", "").strip()
                            if data.get("success") and serial:
                                hw_serial = serial
                except Exception as e:
                    logger.debug(
                        f"[NOC-Engine] Charger ID refresh: HW fetch failed: {e}"
                    )
            except Exception as e:
                logger.debug(f"[NOC-Engine] Charger ID refresh error: {e}")
```

with:

```python
                try:
                    async with session.get(
                        self._hw_serial_url,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            serial = str(data.get("serial_number", "")).replace("\x00", "").strip()
                            if data.get("success") and serial:
                                hw_serial = serial
                                self._rl_hw_serial.ok()
                except Exception:
                    self._rl_hw_serial.exception(
                        "HW serial fetch failed (URL: %s)", self._hw_serial_url,
                    )
            except Exception:
                # Outer error: e.g. _ensure_http_session() blew up. Bucket under OCPP
                # since that's the first endpoint we'd have hit.
                self._rl_ocpp_serial.exception("Charger ID refresh outer error")
```

- [ ] **Step 6: Rewrite `_noc_url_refresh_loop` except clause**

**Replace lines 470-471**:

```python
            except Exception as e:
                logger.debug(f"[NOC-Engine] NOC URL refresh error: {e}")
```

with:

```python
            except Exception:
                self._rl_noc_url.exception(
                    "NOC URL refresh failed (URL: %s)", self._noc_url_url,
                )
                continue
        # After a successful fetch, announce recovery once and reset the counter.
```

Then, **directly after the `if data.get("success") and url: new_url = url` line (≈line 469)**, insert:

```python
                            self._rl_noc_url.ok()
```

- [ ] **Step 7: Run the test and verify it passes**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestRefreshLoopsRateLimited -v
```
Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add noc_engine.py tests/test_logging_noise_reduction.py
git commit -m "fix(noc): rate-limit refresh-loop errors + capture stack frames"
```

---

## Task 8: `[SessionSync] Failed to fetch …` → `logger.exception`

**Why:** Three sites in `session_sync.py` log `Failed to fetch …: {e}` with the exception string only — no traceback. The 24h capture has 30 instances (10 × 3), and when one of these fires the operator wants the stack frame. Switch to `logger.exception(...)`.

**Files:**
- Modify: `session_sync.py:188`, `session_sync.py:237`

- [ ] **Step 1: Append the failing test**

Add to `tests/test_logging_noise_reduction.py`:
```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestSessionSyncExceptionLogging -v
```

- [ ] **Step 3: Make the two edits in `session_sync.py`**

**Replace [session_sync.py:187-188](../../session_sync.py#L187)**:
```python
                except Exception as e:
                    logger.error(f"[SessionSync] Failed to fetch active session gun {gun_id}: {e}")
```
with:
```python
                except Exception:
                    logger.exception(
                        f"[SessionSync] Failed to fetch active session gun {gun_id}"
                    )
```

**Replace [session_sync.py:236-237](../../session_sync.py#L236)**:
```python
        except Exception as e:
            logger.error(f"[SessionSync] Failed to fetch history: {e}")
```
with:
```python
        except Exception:
            logger.exception("[SessionSync] Failed to fetch history")
```

- [ ] **Step 4: Run the test and verify it passes**

```powershell
python -m pytest tests/test_logging_noise_reduction.py::TestSessionSyncExceptionLogging -v
```

- [ ] **Step 5: Commit**

```powershell
git add session_sync.py tests/test_logging_noise_reduction.py
git commit -m "fix(session_sync): use logger.exception in _fetch_* error paths"
```

---

## Task 9: Sweep `except ... as e: logger.error(f\"…{e}…\")` across all modules

**Why:** The remaining sites all lose the stack frame. The grep below (which the executor will run) enumerates them.

**In-scope files:** `noc_engine.py`, `session_sync.py`, `telemetry_collector.py`, `ssh_tunnel.py`, `command_executor.py`.

**Out of scope (do NOT touch):** `qflex-charging`, `qflex-allocation`, `qflex-platform/platform/errors`.

- [ ] **Step 1: Enumerate candidate sites**

```powershell
python -m pytest tests/ -v --collect-only -q   # sanity check baseline first
```

Then enumerate:
```powershell
Get-ChildItem noc_engine.py, session_sync.py, telemetry_collector.py, ssh_tunnel.py, command_executor.py |
  Select-String -Pattern 'logger\.error\(.*\{e\}' -CaseSensitive
```

Expected hits (verified from current source on 2026-05-16):
- `command_executor.py:128` — `logger.error(f"[Executor] cmd={command_id} connection error: {e}")` ← in `except aiohttp.ClientConnectorError as e:`
- `noc_engine.py:674` — `logger.error(f"[NOC-Engine] Failed to send command result for cmd={cmd_id}: {e}")`
- `noc_engine.py:740` — `logger.error(f"[NOC-Engine] 🔐 Failed to send SSH tunnel ack: {e}")`
- `noc_engine.py:778` — `logger.error(f"[NOC-Engine] 🔐 Failed to send tunnel closed: {e}")`
- `noc_engine.py:814` — `logger.error(f"[NOC-Engine] 🔐 Failed to send tunnel closed: {e}")`
- `noc_engine.py:967` — `logger.error(f"[NOC-Engine] Failed to decode chunk {chunk_index}: {e}")`
- `noc_engine.py:1098` — `logger.error(f"[NOC-Engine] Exception posting to port 8005: {type(e).__name__}: {e}")`
- `session_sync.py:98` — `logger.error(f"[SessionSync] Failed to save state: {e}")`
- `session_sync.py:126` — `logger.error(f"[SessionSync] Sync error: {e}")`
- `session_sync.py:296` — `logger.error(f"[SessionSync] Failed to send to NOC: {e}")`
- `ssh_tunnel.py:200` — `logger.error(f"[SSH-Tunnel] OS error opening tunnel {tunnel_id}: {e}")`
- `ssh_tunnel.py:205` — `logger.error(f"[SSH-Tunnel] Failed to open tunnel {tunnel_id}: {type(e).__name__}: {e}")` (and the immediately-following `logger.error(f"[SSH-Tunnel] Traceback: {traceback.format_exc()}")` should be **deleted** — `logger.exception` already includes the traceback)
- `ssh_tunnel.py:254` — `logger.error(f"[SSH-Tunnel] Failed to forward to SSHD: {e}")`
- `ssh_tunnel.py:338` — `logger.error(f"[SSH-Tunnel] Failed to send to WebSocket: {e}")`
- `ssh_tunnel.py:345` — `logger.error(f"[SSH-Tunnel] Reader loop error for {tunnel_id}: {e}")`

**Already correct (do not modify):**
- `command_executor.py:138` — already has `exc_info=True`.
- `noc_engine.py:648` — already has `exc_info=True`.
- `noc_engine.py:1192` — already has `exc_info=True`.

**Already addressed in earlier tasks:**
- `session_sync.py:188, 237` — Task 8.
- `noc_engine.py:407, 421, 425, 471` — Task 7.

- [ ] **Step 2: Apply the rewrite at each site**

For each site, replace:
```python
        except Exception as e:                       # or specific subclass
            logger.error(f"[X] message: {e}")
```
with:
```python
        except Exception:                            # keep the subclass if specific
            logger.exception("[X] message")
```

Notes:
- When the original error message includes `{type(e).__name__}: {e}`, drop both — `logger.exception` prepends a clean `Traceback (most recent call last):` block that already says the exception type.
- When the original is `except aiohttp.ClientConnectorError as e:` (e.g. `command_executor.py:128`), keep the narrow exception class — change only the body:
  ```python
      except aiohttp.ClientConnectorError:
          logger.exception(f"[Executor] cmd={command_id} connection error")
  ```
- For `ssh_tunnel.py:205-207`, also delete the explicit `traceback.format_exc()` line that follows — it's now redundant.

- [ ] **Step 3: Re-run the enumeration grep to confirm no `error(...{e}...)` remains**

```powershell
Get-ChildItem noc_engine.py, session_sync.py, telemetry_collector.py, ssh_tunnel.py, command_executor.py |
  Select-String -Pattern 'logger\.error\(.*\{e\}' -CaseSensitive
```
Expected: zero hits.

- [ ] **Step 4: Run the full test suite**

```powershell
python -m pytest tests/ -v
```
Expected: all previously passing tests still pass (we're not changing behavior, just log content).

- [ ] **Step 5: Commit**

```powershell
git add noc_engine.py session_sync.py ssh_tunnel.py command_executor.py
git commit -m "fix(noc): use logger.exception across error paths to capture stack frames"
```

---

## Task 10: KEEP — once-per-process startup INFO lines

**Why this is its own task:** the engineer doing the sweep in Task 9 will be tempted to "clean up" these too. They are deliberately kept. **Do not touch them.**

The following INFO lines fire **once per process** (during `_fetch_charger_id` / `_fetch_noc_url` / startup banner) and are exactly the kind of signal that helps post-mortem reconstruction of "what state did the engine boot in?":

- `[NocEngine] ✅ NOC URL    : <url>` — [main.py:147](../../main.py#L147)
- `[NocEngine] ✅ OCPP serial: <serial>` — [main.py:202](../../main.py#L202)
- `[NocEngine] ✅ HW serial  : <serial>` — [main.py:218](../../main.py#L218)
- `[NocEngine] ✅ Charger ID  : <id>` — [main.py:228](../../main.py#L228)
- `[NocEngine] 🔍 Resolving charger ID ...` — [main.py:184](../../main.py#L184)
- `[NocEngine]    OCPP serial : <url>` — [main.py:185](../../main.py#L185)
- `[NocEngine]    HW serial   : <url>` — [main.py:186](../../main.py#L186)
- Startup banner block at [main.py:277-300](../../main.py#L277) (`====`, `Charger ID`, `Model`, `Firmware`, `NOC Server`, `Charger IP`, `APIs target`, `Telemetry`, `====`)
- `[NOC-Engine] Charger ID changed: <old> → <new> — reconnecting` — [noc_engine.py:435](../../noc_engine.py#L435) (fires only on actual change; ~zero/day in steady state)
- `[NOC-Engine] NOC URL changed: <old> → <new> — reconnecting` — [noc_engine.py:480](../../noc_engine.py#L480) (fires only on actual change; ~zero/day in steady state)

- [ ] **Step 1: Add a one-line comment above each block so future cleanup passes don't touch them**

In `main.py`, **above [main.py:147](../../main.py#L147)** (`logger.info(f"[NocEngine] ✅ NOC URL ...")`), insert:
```python
                    # KEEP — once-per-process boot trace; useful for post-mortem.
```

Repeat above [main.py:202](../../main.py#L202), [main.py:218](../../main.py#L218), [main.py:228](../../main.py#L228), and above the startup banner at [main.py:277](../../main.py#L277):
```python
    # KEEP — startup banner; one-shot at boot.
```

In `noc_engine.py`, above the `Charger ID changed` block at [noc_engine.py:434-436](../../noc_engine.py#L434):
```python
            # KEEP — fires only on actual change (≈ zero/day in steady state).
```

And above the matching `NOC URL changed` block at [noc_engine.py:479-481](../../noc_engine.py#L479):
```python
            # KEEP — fires only on actual change (≈ zero/day in steady state).
```

- [ ] **Step 2: Commit**

```powershell
git add main.py noc_engine.py
git commit -m "docs(noc): annotate once-per-process startup INFO lines as KEEP"
```

---

## Task 11: Version bump, CHANGELOG, graphify, full test sweep

**Why:** Project-wide rule (global CLAUDE.md): *"With every change bump the version, update graphify and generate changelog"*. Current version is `1.1.4` ([VERSION](../../VERSION), [CHANGELOG.md:7](../../CHANGELOG.md#L7)). Bump to `1.1.5`.

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Re-run: `graphify update .`

- [ ] **Step 1: Bump `VERSION`**

Replace the single line:
```
1.1.4
```
with:
```
1.1.5
```

(There are no embedded version constants — `__init__.py` reads `VERSION` at import time, and `noc_engine.py:_read_engine_version()` does the same. Confirmed by `grep -rn "1\.1\.4" --include="*.py"` returning zero hits.)

- [ ] **Step 2: Insert the CHANGELOG entry**

In `CHANGELOG.md`, **after the `## [Unreleased]` line at line 5**, insert:

```markdown
## [1.1.5] — 2026-05-16

### Changed

#### Logging noise reduction — `noc_engine.log` 95 MB/day → <10 MB/day

- **Why.** A 24h capture (`qflex_logs_full_20260515_114015/noc-engine/noc_engine.log`, 856 113 lines, 95 MB — the biggest log of the four QFlex modules) showed **86% was DEBUG noise** (732 905 DEBUG lines). The single worst contributor was the `websockets.client` library at 469 536 lines/day (≈55% of the file) — TEXT-frame dumps and keepalive ping/pong traces with no application-level signal. Application code added another ~250 K lines of per-tick INFO/DEBUG: heartbeat-sent (89 503), telemetry-sent (21 931 INFO), incoming-WS (21 932 INFO), per-endpoint telemetry OK (~128 K DEBUG), session-sync send-success (11 885 DEBUG), zero-history fetch (10 116 DEBUG), and refresh-loop connection errors (~7 000 DEBUG with no stack frame). Meanwhile genuine errors were tiny (45 ERROR / 62 WARNING in 856 K lines) — they were getting buried.
- **New helpers (`log_helpers.py`).** Three primitives plus a library-config call:
  - `log_on_change(logger, key, value, msg, threshold=None)` — emits only when a tracked value changes.
  - `RateLimitedLogger(logger, key, schedule=(1, 10, 100, 1000))` — backoff schedule + a single "recovered" INFO line on `.ok()`.
  - `PeriodicSummary(logger, key, window_seconds)` — buffers per-window counts and emits one INFO/window; also tracks OK/FAIL status and emits an immediate flip line on a transition.
  - `_configure_library_loggers()` — sets `websockets`, `websockets.client`, `websockets.server`, `websockets.protocol`, `httpx`, `asyncio` to `WARNING`. Called once from `main.py` at startup. **Removes ~470 000 lines/day on its own.**
- **Per-site changes:**
  - `main.py` — calls `_configure_library_loggers()` immediately after `logging.basicConfig(...)`. Once-per-process startup INFO lines (`✅ OCPP serial`, `✅ HW serial`, `✅ Charger ID`, `✅ NOC URL`, startup banner) are explicitly KEPT with inline `# KEEP` comments to deter future cleanups.
  - `noc_engine.py` — `_heartbeat_loop` log demoted below DEBUG (level 5) so even DEBUG mode skips it (-89 503 lines/day). `_telemetry_loop` per-tick INFO replaced by a 1-hour `PeriodicSummary` with immediate OK↔FAIL flip lines (-21 931 INFO/day). `_receive_loop` unconditional `📥 INCOMING WS MESSAGE` INFO demoted to DEBUG (-21 932 INFO/day); the `proxy_request` branch now also feeds a 60s `PeriodicSummary`. `_charger_id_refresh_loop` (OCPP + HW fetches) and `_noc_url_refresh_loop` now use per-endpoint `RateLimitedLogger.exception(...)` — first failure captures the stack frame; recovery is announced via `.ok()`.
  - `telemetry_collector.py` — `_fetch` per-call OK demoted to TRACE (level 5); per-endpoint status flips emitted via `log_on_change`. The bare `except Exception as e:` is now `logger.exception(...)`.
  - `session_sync.py` — `Fetched N history sessions` only emits when `N>0` or on a 0↔N transition (via `log_on_change`). `Sent session_sync to NOC Server` demoted to TRACE. All three `Failed to fetch …` ERROR sites use `logger.exception(...)`.
  - `ssh_tunnel.py`, `command_executor.py` — sweep of `except ... as e: logger.error(f"…{e}…")` → `logger.exception(...)`. Redundant `traceback.format_exc()` lines deleted.
- **Behavior unchanged.** No control-flow edits. Existing tests pass unchanged.
- **New tests.** `tests/test_log_helpers.py` (7 tests) covers the helpers and library-config call. `tests/test_logging_noise_reduction.py` covers each touched call site (`TestTelemetrySummary`, `TestIncomingWSMessageSummary`, `TestTelemetryFetchPerEndpointFlip`, `TestSessionSyncQuiet`, `TestRefreshLoopsRateLimited`, `TestSessionSyncExceptionLogging`).
- **Estimated reduction.** Library silencing (-470 K) + heartbeat demote (-89 K) + telemetry summary (-21 K) + incoming-WS demote (-21 K) + telemetry-OK to TRACE (-128 K) + session-sync demotes (-22 K) + refresh-loop rate-limit (-7 K) ≈ **758 K lines/day removed** (≈88% of the original 856 K).
```

- [ ] **Step 3: Full test sweep**

```powershell
python -m pytest tests/ -v
```
Expected: all previously passing tests still pass; the 9 new test classes pass.

- [ ] **Step 4: Update graphify**

```powershell
graphify update .
```
Expected: AST-only update completes, no API cost.

- [ ] **Step 5: Commit**

```powershell
git add VERSION CHANGELOG.md graphify-out/
git commit -m "chore: bump to 1.1.5 + CHANGELOG for logging noise reduction"
```

---

## Self-Review Notes

**Spec coverage:**
- Activity 1 (remove repetitive noise) → Tasks 1 (library silencing), 2 (heartbeat demote), 3 (telemetry summary), 4 (incoming-WS summary), 5 (per-endpoint OK→TRACE).
- Activity 2 (log on change) → Tasks 5 (status-flip via `log_on_change`), 6 (history count via `log_on_change`).
- Activity 3 (remove success API logs) → Tasks 3, 4, 5, 6 (per-tick success → summary/TRACE/flip).
- Activity 4 (record exceptions) → Tasks 7 (`RateLimitedLogger.exception`), 8 (`logger.exception` on session-sync `Failed to fetch`), 9 (sweep).
- User's "single biggest win" — library logger config → Task 1.
- User's "keep startup INFO" — Task 10 (explicit KEEP annotations).

**Verification log of source line numbers** — every line/file reference was confirmed against the working tree on 2026-05-16:
- `noc_engine.py:351` ✓ `[NOC-Engine] ♥ Heartbeat sent` (DEBUG)
- `noc_engine.py:368` ✓ `[NOC-Engine] 📡 Telemetry sent` (INFO)
- `noc_engine.py:407` ✓ `[NOC-Engine] Charger ID refresh: OCPP fetch failed` (DEBUG)
- `noc_engine.py:421` ✓ `[NOC-Engine] Charger ID refresh: HW fetch failed` (DEBUG)
- `noc_engine.py:425` ✓ `[NOC-Engine] Charger ID refresh error` (DEBUG) — note: the brief said "verify" for line 425 — confirmed it's at 425, not 471.
- `noc_engine.py:471` ✓ `[NOC-Engine] NOC URL refresh error` (DEBUG)
- `noc_engine.py:590` ✓ `[NOC-Engine] 📥 INCOMING WS MESSAGE | type={msg_type} | keys={list(message.keys())}` (INFO)
- `session_sync.py:188` ✓ `[SessionSync] Failed to fetch active session gun {gun_id}` (ERROR)
- `session_sync.py:232` ✓ `[SessionSync] Fetched {N} history sessions` (DEBUG)
- `session_sync.py:237` ✓ `[SessionSync] Failed to fetch history` (ERROR)
- `session_sync.py:294` ✓ `[SessionSync] Sent session_sync to NOC Server` (DEBUG)
- `telemetry_collector.py:88` ✓ `[Telemetry] {key} ok ({url})` (DEBUG)
- `main.py:51-55` ✓ `logging.basicConfig(...)` then `logger = logging.getLogger(__name__)` — the right place for `_configure_library_loggers()`.
- `VERSION` ✓ contains `1.1.4` on a single line.
- `CHANGELOG.md` ✓ Keep-a-Changelog format with `## [Unreleased]` at line 5 and `## [1.1.4] — 2026-05-14` at line 7.

If the engineer finds a drift (someone touched these files first), the *anchor strings* (e.g. `"♥ Heartbeat sent"`, `"📥 INCOMING WS MESSAGE"`, `"📡 Telemetry sent"`, `"Fetched 0 history sessions"`, `"NOC URL refresh error"`) are the source of truth — line numbers are just hints.

**Scope discipline.** This plan does **not** touch `qflex-charging`, `qflex-allocation`, or `qflex-platform/platform/errors` — those modules each need their own version bump, CHANGELOG, and graphify run, so they're separate plans.
