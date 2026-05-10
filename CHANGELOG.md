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
