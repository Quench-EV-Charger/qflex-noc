"""Reusable logging helpers for keeping noc_engine.log signal-rich.

Primitives
----------
- ``log_on_change(logger, key, value, msg, threshold=None)`` — emit only when
  ``value`` differs from the last logged value (with optional numeric threshold).
- ``RateLimitedLogger(logger, key, schedule=(1, 10, 100, 1000))`` — emit errors
  on a backoff schedule when the same condition keeps repeating; emit ONE
  "recovered" INFO line on the first success after a streak.
- ``PeriodicSummary(logger, key, window_seconds=60)`` — buffer per-window counts
  and emit one INFO line per window; also tracks last status so OK<->FAIL flips
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


class _Sentinel:
    """Marker used by ``log_on_change`` to distinguish "never logged" from a
    real previously-logged value of ``None``."""


_MISSING = _Sentinel()


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

    ``threshold`` (numeric only): treat values within +/- threshold of the
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
            # Lazy formatting — leave %-substitution to the logging framework
            # so handlers that filter by record can still see the raw template.
            self._logger.error(
                "[%s attempt #%d] " + msg,
                self._key,
                self._attempts,
                *args,
                exc_info=exc_info,
            )

    def exception(self, msg: str, *args: Any) -> None:
        """Like ``error`` but always captures the current exception's traceback."""
        self.error(msg, *args, exc_info=True)

    def ok(self, msg: str = "recovered") -> None:
        if self._attempts > 0:
            self._logger.info(
                "[%s] %s after %d failed attempt(s)",
                self._key,
                msg,
                self._attempts,
            )
        self._attempts = 0


class PeriodicSummary:
    """Buffer per-window counts and flush one INFO line per ``window_seconds``.

    Two usage modes:

    1. ``increment()`` — bump a simple counter. ``flush()`` (called automatically
       once the window has elapsed) emits ``"<key> N in last <window>s"``.

    2. ``success()`` / ``failure(reason)`` — track an OK/FAIL pattern. Same
       periodic summary, PLUS an immediate INFO line whenever the status flips
       (e.g. ``"telemetry: OK -> FAIL (conn refused)"``).
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
        # Flush first so the new event lands in the new window, not the old one.
        self._maybe_flush()
        self._count += n

    # --- status API ------------------------------------------------------
    def success(self) -> None:
        self._maybe_flush()
        self._ok_count += 1
        if self._last_status == "fail":
            self._logger.info(f"[{self._key}] FAIL → OK (recovered)")
        self._last_status = "ok"

    def failure(self, reason: str = "") -> None:
        self._maybe_flush()
        self._fail_count += 1
        if self._last_status == "ok":
            tail = f" ({reason})" if reason else ""
            self._logger.info(f"[{self._key}] OK → FAIL{tail}")
        elif self._last_status is None:
            tail = f" ({reason})" if reason else ""
            self._logger.info(f"[{self._key}] FAIL{tail}")
        self._last_status = "fail"

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
