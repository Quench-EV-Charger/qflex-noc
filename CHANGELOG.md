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
