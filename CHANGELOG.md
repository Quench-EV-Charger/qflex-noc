# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adhere to [Semantic Versioning](https://semver.org/).

## [Unreleased] — 1.1.0-dev

### Added
- Test suite (pytest + pytest-asyncio) under `tests/`.
- `VERSION` file and this changelog.

### Changed
_TBD per task_

### Fixed
- WS `ping_timeout` was `None`; a frozen server left the engine hung indefinitely. Now `20s`.
- `WSClient.connect` now uses `open_timeout=15` so an unreachable server fails fast.
- `WSClient.disconnect` is now hard-bounded at 6s and logs unexpected close errors instead of swallowing them.
- `WSClient.send` now wraps the underlying drain with `asyncio.wait_for(send_timeout=10s)`. A stuck server can no longer freeze every concurrent loop.

### Added
- New inbound-message watchdog: the engine forces a reconnect if it hasn't received any WS message within `inbound_idle_timeout` (default 60s). Closes the gap left by one-way application heartbeats and `asyncio.wait(FIRST_COMPLETED)` blocking. Polling cadence is capped at 5s so disconnects are noticed quickly even with high thresholds.
- Background sweeper for chunked-upload state with a 5-minute TTL.

### Changed
- `_chunked_uploads` moved off the module global onto the `NocEngine` instance; orphaned upload state (server dropped before final chunk) is now garbage-collected instead of leaking forever.
- Fire-and-forget background tasks (command/proxy/upload/ssh handlers) are now tracked, cancelled on disconnect, and their exceptions logged.
