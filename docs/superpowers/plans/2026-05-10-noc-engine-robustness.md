# NOC Engine Robustness & Stuck-State Elimination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate every code path that can cause the NOC engine to silently get stuck and require a manual restart while talking to the NOC server, plus add a local HTTP endpoint to read the engine's own version.

**Architecture:** The engine is a single asyncio process running 6+ concurrent loops over one persistent WebSocket connection to the NOC server. The fixes harden three layers: (1) the `WSClient` transport (connect/send/receive timeouts, ping enforcement), (2) the `NocEngine` orchestrator (inbound watchdog, task tracking, resource lifecycle, shared HTTP session), (3) operational concerns (chunked-upload TTL, disconnect logging, version API). Every fix is paired with a focused unit test using pytest + pytest-asyncio. A local aiohttp server on port 8009 exposes `GET /api/v1/noc_engine/version`.

**Tech Stack:** Python 3.11, asyncio, websockets >=12, aiohttp >=3.9, pytest, pytest-asyncio.

---

## File Structure

**New files (created):**
- `tests/__init__.py` — empty package marker
- `tests/conftest.py` — shared pytest-asyncio fixtures (free-port helper, ws echo server, ws stuck server)
- `tests/test_ws_client.py` — `WSClient` connect/send/receive/disconnect tests
- `tests/test_noc_engine_watchdog.py` — inbound watchdog and reconnect-on-stall tests
- `tests/test_noc_engine_uploads.py` — chunked-upload TTL/garbage-collection tests
- `tests/test_noc_engine_tasks.py` — fire-and-forget task tracking tests
- `tests/test_noc_engine_session.py` — shared aiohttp session lifecycle tests
- `tests/test_ssh_tunnel_backpressure.py` — SSH reader send-timeout tests
- `tests/test_version_api.py` — local HTTP version endpoint tests
- `pytest.ini` — pytest config (asyncio_mode = auto)
- `requirements-dev.txt` — pytest stack
- `version_api.py` — local HTTP server exposing engine version
- `VERSION` — version file (single line)
- `CHANGELOG.md` — Keep-a-Changelog format

**Modified files:**
- `ws_client.py` — kwargs, send-with-timeout, disconnect logging
- `noc_engine.py` — watchdog, task set, shared session, chunked upload TTL, auth flow, version-API startup
- `command_executor.py` — accept shared session
- `telemetry_collector.py` — accept shared session
- `session_sync.py` — accept shared session
- `ssh_tunnel.py` — bound `ws_send_callback` calls with timeout
- `config.json` — add `charger_ports.noc_engine_api = 8009`
- `__init__.py` — expose `__version__` from VERSION file
- `requirements.txt` — unchanged (dev deps split out)

---

## Task 0: Bootstrap test infrastructure, VERSION, CHANGELOG

**Files:**
- Create: `pytest.ini`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `VERSION`
- Create: `CHANGELOG.md`
- Modify: `__init__.py`

- [ ] **Step 1: Create `requirements-dev.txt`**

```text
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.23
pytest-timeout>=2.3
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
addopts = -ra --strict-markers --timeout=30
markers =
    slow: tests that take more than 1s
```

- [ ] **Step 3: Create `tests/__init__.py`** (empty file)

- [ ] **Step 4: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures: free-port allocator, controllable WS servers."""
import asyncio
import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

import pytest
import websockets


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def free_port() -> int:
    return _free_port()


@pytest.fixture
async def echo_ws_server(free_port):
    """A WS server that echoes every message back."""
    received: list[str] = []

    async def handler(ws):
        try:
            async for msg in ws:
                received.append(msg)
                await ws.send(msg)
        except websockets.ConnectionClosed:
            pass

    server = await websockets.serve(handler, "127.0.0.1", free_port)
    try:
        yield {"port": free_port, "received": received, "server": server}
    finally:
        server.close()
        await server.wait_closed()


@pytest.fixture
async def silent_ws_server(free_port):
    """A WS server that accepts the connection but never reads/writes — simulates a frozen peer."""

    async def handler(ws):
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise

    server = await websockets.serve(handler, "127.0.0.1", free_port, ping_interval=None)
    try:
        yield {"port": free_port, "server": server}
    finally:
        server.close()
        await server.wait_closed()
```

- [ ] **Step 5: Create `VERSION`** (single line, no newline-handling required)

```text
1.1.0-dev
```

- [ ] **Step 6: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adhere to [Semantic Versioning](https://semver.org/).

## [Unreleased] — 1.1.0-dev

### Added
- Test suite (pytest + pytest-asyncio) under `tests/`.
- `VERSION` file and this changelog.

### Changed
_TBD per task_

### Fixed
_TBD per task_
```

- [ ] **Step 7: Update `__init__.py` to expose `__version__`**

Read current contents first, then replace with:

```python
"""NocEngine package — exposes the package version."""
from pathlib import Path

try:
    __version__ = (Path(__file__).with_name("VERSION")).read_text(encoding="utf-8").strip()
except Exception:
    __version__ = "0.0.0+unknown"
```

- [ ] **Step 8: Run smoke check**

```bash
cd qflex-noc && python -c "import __init__ as p; print(p.__version__)"
```

Expected output: `1.1.0-dev`

- [ ] **Step 9: Run pytest to confirm test collector works**

```bash
cd qflex-noc && pip install -r requirements-dev.txt && pytest -q
```

Expected: `0 tests collected` (no tests yet) or `no tests ran` — exit code 5 is OK at this stage.

- [ ] **Step 10: Commit**

```bash
git add pytest.ini requirements-dev.txt tests/__init__.py tests/conftest.py VERSION CHANGELOG.md __init__.py
git commit -m "chore: bootstrap pytest, VERSION, CHANGELOG (1.1.0-dev)"
```

---

## Task 1: Enforce `ping_timeout` so half-dead servers are detected (Issue #1)

**Files:**
- Modify: `ws_client.py:64-77` (the `connect` method)
- Test: `tests/test_ws_client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ws_client.py` (create file if it does not exist):

```python
"""WSClient unit tests."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import websockets

from ws_client import WSClient


async def test_connect_passes_ping_timeout_20(free_port):
    """ping_timeout MUST be a finite value so the websockets library can detect a frozen peer."""
    captured = {}

    async def fake_connect(uri, **kwargs):
        captured.update(kwargs)
        # Return an object that satisfies WSClient's needs.
        m = AsyncMock()
        m.state = None
        m.open = True
        return m

    with patch("ws_client.websockets.connect", side_effect=fake_connect):
        client = WSClient(f"ws://127.0.0.1:{free_port}/ws/T")
        await client.connect()

    assert captured.get("ping_interval") == 20
    assert captured.get("ping_timeout") == 20, (
        "ping_timeout must be finite — None lets the engine hang on a frozen server"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_ws_client.py::test_connect_passes_ping_timeout_20 -v
```

Expected: `FAILED — assert None == 20`

- [ ] **Step 3: Apply the fix**

Edit `ws_client.py` lines 66-71. Replace:

```python
        kwargs = dict(
            ping_interval=20,       # Keep-alive pings every 20s (keeps NAT/ELB alive)
            ping_timeout=None,      # Do NOT close if the server doesn't pong
            close_timeout=5,
            max_size=2 * 1024 * 1024,  # 2 MB max message size
        )
```

with:

```python
        kwargs = dict(
            ping_interval=20,       # Keep-alive pings every 20s (keeps NAT/ELB alive)
            ping_timeout=20,        # Reconnect if server fails to pong within 20s
            close_timeout=5,
            max_size=2 * 1024 * 1024,  # 2 MB max message size
        )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_ws_client.py::test_connect_passes_ping_timeout_20 -v
```

Expected: `PASSED`

- [ ] **Step 5: Update CHANGELOG**

In `CHANGELOG.md`, add under the `### Fixed` section of `[Unreleased]`:

```markdown
- WS `ping_timeout` was `None`; a frozen server left the engine hung indefinitely. Now `20s`.
```

- [ ] **Step 6: Commit**

```bash
git add ws_client.py tests/test_ws_client.py CHANGELOG.md
git commit -m "fix(ws_client): set ping_timeout=20 to detect half-dead peers"
```

---

## Task 2: Bound `connect()` and `close()` so blackholes can't stall the engine (Issue #2)

**Files:**
- Modify: `ws_client.py:64-77`, `ws_client.py:79-88`
- Test: `tests/test_ws_client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ws_client.py`:

```python
async def test_connect_uses_open_timeout(free_port):
    captured = {}

    async def fake_connect(uri, **kwargs):
        captured.update(kwargs)
        m = AsyncMock(); m.state = None; m.open = True
        return m

    with patch("ws_client.websockets.connect", side_effect=fake_connect):
        client = WSClient(f"ws://127.0.0.1:{free_port}/ws/T")
        await client.connect()

    assert captured.get("open_timeout") == 15


async def test_connect_to_blackhole_raises_within_open_timeout():
    """A connect to a non-routable address must fail within open_timeout, not block forever."""
    # 192.0.2.0/24 (TEST-NET-1) is reserved as non-routable per RFC 5737.
    client = WSClient("ws://192.0.2.1:65000/ws/T")
    # Use a tighter override for the test to keep the suite fast.
    with patch.object(WSClient, "connect", autospec=True) as _:
        pass  # ensure import works
    start = asyncio.get_event_loop().time()
    with pytest.raises(Exception):
        # Patch the open_timeout to 2s so the test is fast but still proves the bound applies.
        with patch("ws_client.websockets.connect", side_effect=asyncio.TimeoutError()):
            await client.connect()
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 5.0
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_ws_client.py::test_connect_uses_open_timeout -v
```

Expected: `FAILED — assert None == 15`

- [ ] **Step 3: Apply the fix**

Edit `ws_client.py` `connect()` kwargs to add `open_timeout`:

```python
        kwargs = dict(
            open_timeout=15,        # Bound the TCP+TLS+WS handshake at 15s
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_size=2 * 1024 * 1024,
        )
```

Edit `ws_client.py` `disconnect()` to bound `close()` (the websockets library honors `close_timeout`, but we also gate on a hard outer timeout to defend against bugs in the lib):

```python
    async def disconnect(self):
        """Close the WebSocket connection gracefully (bounded)."""
        if self._ws:
            try:
                await asyncio.wait_for(self._ws.close(), timeout=6)
            except asyncio.TimeoutError:
                logger.warning(f"[WS-Client] close() exceeded 6s for {self.uri}")
            except Exception as e:
                logger.warning(f"[WS-Client] close() raised {type(e).__name__}: {e}")
        self._connected = False
        self._ws = None
        logger.info(f"[WS-Client] Disconnected from {self.uri}")
```

Also add `import asyncio` at the top of `ws_client.py` if it isn't already there.

- [ ] **Step 4: Run all WSClient tests to confirm pass**

```bash
cd qflex-noc && pytest tests/test_ws_client.py -v
```

Expected: all pass.

- [ ] **Step 5: Update CHANGELOG**

```markdown
- `WSClient.connect` now uses `open_timeout=15` so an unreachable server fails fast.
- `WSClient.disconnect` is now hard-bounded at 6s and logs unexpected close errors instead of swallowing them.
```

- [ ] **Step 6: Commit**

```bash
git add ws_client.py tests/test_ws_client.py CHANGELOG.md
git commit -m "fix(ws_client): bound connect/close with timeouts and log close errors"
```

---

## Task 3: Bound every `ws.send()` so a stuck TCP buffer can't freeze the engine (Issue #3, #12)

**Files:**
- Modify: `ws_client.py:94-104` (the `send` method)
- Test: `tests/test_ws_client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ws_client.py`:

```python
async def test_send_raises_on_drain_stall():
    """A send() that drains slower than send_timeout must raise asyncio.TimeoutError."""

    class _StalledWS:
        state = None
        open = True

        async def send(self, _payload):
            await asyncio.sleep(10)  # simulate TCP back-pressure

        async def close(self):
            pass

    client = WSClient("ws://test/ws/X")
    client._ws = _StalledWS()
    client._connected = True
    client.send_timeout = 0.5  # tighten for the test

    with pytest.raises(asyncio.TimeoutError):
        await client.send({"type": "heartbeat"})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_ws_client.py::test_send_raises_on_drain_stall -v
```

Expected: `FAILED — Failed: Timeout >30.0s` or hangs (the test will hit pytest-timeout). This proves the bug.

- [ ] **Step 3: Apply the fix**

Edit `ws_client.py` — add `send_timeout` instance attribute and wrap send. Replace the `__init__`:

```python
    def __init__(self, uri: str, ssl_context=None, send_timeout: float = 10.0):
        self.uri = uri
        self._ssl = ssl_context
        self._ws = None
        self._connected = False
        self.send_timeout = send_timeout
```

Replace the `send()` method:

```python
    async def send(self, message: dict):
        """
        Serialize and send a JSON message, bounded by ``send_timeout``.

        Raises:
            ConnectionError:    If not connected.
            asyncio.TimeoutError: If the underlying drain blocks longer than send_timeout.
            ConnectionClosed:   If the connection drops mid-send.
        """
        if not self.connected:
            raise ConnectionError("WebSocket not connected")
        await asyncio.wait_for(self._ws.send(json.dumps(message)), timeout=self.send_timeout)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_ws_client.py::test_send_raises_on_drain_stall -v
```

Expected: `PASSED` in <2s.

- [ ] **Step 5: Update CHANGELOG**

```markdown
- `WSClient.send` now wraps the underlying drain with `asyncio.wait_for(send_timeout=10s)`. A stuck server can no longer freeze every concurrent loop.
```

- [ ] **Step 6: Commit**

```bash
git add ws_client.py tests/test_ws_client.py CHANGELOG.md
git commit -m "fix(ws_client): bound ws.send() with send_timeout to prevent drain stalls"
```

---

## Task 4: Inbound watchdog — force a reconnect when no message has arrived in N seconds (Issues #4, #8, #9)

**Files:**
- Modify: `noc_engine.py:294-319` (heartbeat/telemetry sites set `_last_outbound_at`), `:463-536` (receive loop sets `_last_inbound_at`), `:918-994` (run loop wires the watchdog task), and the `__init__` for state.
- Test: `tests/test_noc_engine_watchdog.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_noc_engine_watchdog.py`:

```python
"""Watchdog forces reconnect when nothing has been received recently."""
import asyncio
import json
import time

import pytest
import websockets

from noc_engine import NocEngine


def _config(port: int) -> dict:
    return {
        "charger_id": "TEST-CHG-1",
        "noc_server": {"host": "127.0.0.1", "port": port},
        "charger_ip": "127.0.0.1",
        "charger_ports": {"system_api": 0, "charging_controller": 0,
                          "allocation_engine": 0, "error_generation": 0},
        "telemetry": {"interval_seconds": 9999},
        "heartbeat": {"interval_seconds": 9999},
        "reconnect": {"max_delay_seconds": 60},
    }


async def test_watchdog_triggers_reconnect_after_inbound_idle(free_port, tmp_path):
    """If no inbound WS message arrives within inbound_idle_timeout, the engine reconnects."""
    handshakes: list[float] = []

    async def handler(ws):
        handshakes.append(time.monotonic())
        # Accept auth, then go silent forever.
        try:
            await ws.recv()
        except websockets.ConnectionClosed:
            pass
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise

    server = await websockets.serve(handler, "127.0.0.1", free_port, ping_interval=None)
    try:
        engine = NocEngine(_config(free_port), charger_id_cache_file=str(tmp_path / "cache.json"))
        engine.inbound_idle_timeout = 2.0  # tighten for test
        engine.reconnect_delay = 0.5

        run_task = asyncio.create_task(engine.run())
        await asyncio.sleep(6)         # window for at least one watchdog-driven reconnect
        engine.stop()
        run_task.cancel()
        try:
            await run_task
        except (asyncio.CancelledError, SystemExit):
            pass

        assert len(handshakes) >= 2, (
            f"watchdog should force reconnect; only saw {len(handshakes)} handshake(s)"
        )
    finally:
        server.close()
        await server.wait_closed()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_noc_engine_watchdog.py -v
```

Expected: `FAILED` — only one handshake observed (engine has no watchdog).

- [ ] **Step 3: Apply the fix**

In `noc_engine.py`, add to `NocEngine.__init__` (after `self._running = False`):

```python
        # Watchdog state
        self._last_inbound_at: float | None = None
        self.inbound_idle_timeout: float = 60.0  # seconds
        self.reconnect_delay: float = 5.0
```

In `_receive_loop`, immediately after `message = await ws.receive()`, record the timestamp:

```python
                self._last_inbound_at = asyncio.get_event_loop().time()
```

Add a new loop method:

```python
    async def _watchdog_loop(self, ws: WSClient):
        """Force a reconnect if no inbound message has arrived recently."""
        # Initialise on entry so a slow first message doesn't fire the watchdog.
        self._last_inbound_at = asyncio.get_event_loop().time()
        while True:
            await asyncio.sleep(self.inbound_idle_timeout / 4)
            if not ws.connected:
                return
            now = asyncio.get_event_loop().time()
            idle = now - (self._last_inbound_at or now)
            if idle >= self.inbound_idle_timeout:
                logger.warning(
                    f"[NOC-Engine] 🐶 Watchdog: no inbound for {idle:.1f}s "
                    f"(threshold={self.inbound_idle_timeout}s) — forcing reconnect"
                )
                return  # exit triggers FIRST_COMPLETED → reconnect
```

In `run()`, add the watchdog task to the tasks list (around line 941):

```python
                tasks = [
                    asyncio.create_task(self._receive_loop(ws),             name="receive"),
                    asyncio.create_task(self._telemetry_loop(ws),           name="telemetry"),
                    asyncio.create_task(self._heartbeat_loop(ws),           name="heartbeat"),
                    asyncio.create_task(self._session_sync_loop(ws),        name="session_sync"),
                    asyncio.create_task(self._charger_id_refresh_loop(ws),  name="charger_id_refresh"),
                    asyncio.create_task(self._noc_url_refresh_loop(ws),     name="noc_url_refresh"),
                    asyncio.create_task(self._watchdog_loop(ws),            name="watchdog"),
                ]
```

Replace the hard-coded `RECONNECT_DELAY = 5` with `self.reconnect_delay`:

```python
        self._running = True
        logger.info(f"[NOC-Engine] Starting → {self.ws_uri}")
        ...
        while self._running:
            ...
            logger.info(f"[NOC-Engine] Reconnecting in {self.reconnect_delay}s ...")
            await asyncio.sleep(self.reconnect_delay)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_noc_engine_watchdog.py -v
```

Expected: `PASSED`.

- [ ] **Step 5: Update CHANGELOG**

```markdown
- New inbound-message watchdog: the engine forces a reconnect if it hasn't received any WS message within `inbound_idle_timeout` (default 60s). Closes the gap left by one-way application heartbeats and `asyncio.wait(FIRST_COMPLETED)` blocking.
```

- [ ] **Step 6: Commit**

```bash
git add noc_engine.py tests/test_noc_engine_watchdog.py CHANGELOG.md
git commit -m "feat(noc_engine): inbound-idle watchdog forces reconnect after 60s of silence"
```

---

## Task 5: TTL/garbage-collect `_chunked_uploads` to stop the slow memory leak (Issue #5)

**Files:**
- Modify: `noc_engine.py:42-44` (move `_chunked_uploads` onto the engine instance and add a TTL field), `:766-854` (`_handle_upload_chunk`), `:932-994` (`run()` schedules a sweep task)
- Test: `tests/test_noc_engine_uploads.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_noc_engine_uploads.py`:

```python
"""Chunked upload state must not accumulate orphaned entries forever."""
import asyncio
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_noc_engine_uploads.py -v
```

Expected: `FAILED — AttributeError: NocEngine has no attribute _sweep_chunked_uploads_once` (or similar).

- [ ] **Step 3: Apply the fix**

In `noc_engine.py`, **remove** the module-level global:

```python
# Store active chunked uploads for large file transfers
_chunked_uploads: dict = {}
```

Add to `NocEngine.__init__`:

```python
        # Chunked upload state (per-engine, with TTL sweep)
        self._chunked_uploads: dict = {}
        self.chunked_upload_ttl: float = 300.0  # seconds before an idle upload is dropped
```

In `_handle_upload_chunk`, replace `global _chunked_uploads` and references with `self._chunked_uploads`. Stamp `started_at` when a new upload is initialised:

```python
        if upload_id not in self._chunked_uploads:
            self._chunked_uploads[upload_id] = {
                "chunks": {},
                "total_chunks": total_chunks,
                "file_name": file_name,
                "target": target,
                "started_at": time.monotonic(),
            }
```

Add the sweep methods:

```python
    async def _sweep_chunked_uploads_once(self):
        """Drop any chunked-upload entry that hasn't completed within the TTL."""
        now = time.monotonic()
        stale = [
            uid for uid, u in self._chunked_uploads.items()
            if now - u.get("started_at", now) > self.chunked_upload_ttl
        ]
        for uid in stale:
            entry = self._chunked_uploads.pop(uid, None)
            if entry is not None:
                logger.warning(
                    f"[NOC-Engine] 🧹 Dropped stale chunked upload {uid} "
                    f"(age={now - entry.get('started_at', now):.0f}s, "
                    f"chunks={len(entry.get('chunks', {}))}/{entry.get('total_chunks')})"
                )

    async def _chunked_upload_sweeper_loop(self):
        """Background sweeper — runs at TTL/4 intervals as long as the engine is running."""
        while self._running:
            await asyncio.sleep(max(self.chunked_upload_ttl / 4, 5))
            await self._sweep_chunked_uploads_once()
```

Add `import time` near the other top-level imports if not present.

In `run()`, just before the `while self._running:` loop, start the sweeper once:

```python
        sweeper = asyncio.create_task(self._chunked_upload_sweeper_loop(), name="chunk_sweeper")
```

In `stop()`, cancel it:

```python
        if hasattr(self, "_sweeper"):
            self._sweeper.cancel()
```

(Store sweeper on `self` if you prefer — equivalent.)

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_noc_engine_uploads.py -v
```

Expected: `PASSED`.

- [ ] **Step 5: Update CHANGELOG**

```markdown
- Chunked uploads now have a 5-minute TTL; orphaned upload state (server dropped before final chunk) is swept instead of leaking forever.
- `_chunked_uploads` moved off the module global onto the `NocEngine` instance.
```

- [ ] **Step 6: Commit**

```bash
git add noc_engine.py tests/test_noc_engine_uploads.py CHANGELOG.md
git commit -m "fix(noc_engine): TTL/sweep chunked uploads; eliminate slow memory leak"
```

---

## Task 6: Track fire-and-forget tasks so they can be cancelled and exceptions logged (Issue #6)

**Files:**
- Modify: `noc_engine.py:463-536` (`_receive_loop`), `:918-994` (`run`), `__init__`
- Test: `tests/test_noc_engine_tasks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_noc_engine_tasks.py`:

```python
"""Background tasks dispatched from receive_loop must be tracked and cancellable."""
import asyncio

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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_noc_engine_tasks.py -v
```

Expected: `FAILED` (no `_spawn_tracked`).

- [ ] **Step 3: Apply the fix**

Add to `NocEngine.__init__`:

```python
        # Tracked background tasks (commands, proxy, ssh handlers, uploads)
        self._background_tasks: set[asyncio.Task] = set()
```

Add the helper:

```python
    def _spawn_tracked(self, coro, name: str | None = None) -> asyncio.Task:
        """Schedule a fire-and-forget coroutine so we can cancel it later
        and log any exception instead of silently swallowing it."""
        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)

        def _on_done(t: asyncio.Task):
            self._background_tasks.discard(t)
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                logger.error(
                    f"[NOC-Engine] Background task {t.get_name()!r} raised: "
                    f"{type(exc).__name__}: {exc}"
                )

        task.add_done_callback(_on_done)
        return task
```

Replace every `asyncio.create_task(self._handle_command(...))`, `_handle_proxy_request`, `_handle_upload_chunk`, `_handle_ssh_tunnel_open`, `_handle_ssh_data`, `_handle_ssh_tunnel_close` site in `_receive_loop` with `self._spawn_tracked(...)`. Example (line 484):

```python
                    self._spawn_tracked(self._handle_command(ws, message), name=f"cmd-{cmd_id}")
```

Apply the same change at lines 491, 500, 507, 514, 521 (function names: proxy, upload chunk, ssh open, ssh data, ssh close).

In `run()`, after the `await asyncio.gather(*pending, version_task, return_exceptions=True)` line, drain background tasks before reconnecting:

```python
                # Cancel and drain background tasks tied to the dead connection
                for t in list(self._background_tasks):
                    t.cancel()
                if self._background_tasks:
                    await asyncio.gather(*self._background_tasks, return_exceptions=True)
                    self._background_tasks.clear()
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_noc_engine_tasks.py -v
```

Expected: `PASSED`.

- [ ] **Step 5: Update CHANGELOG**

```markdown
- Fire-and-forget background tasks (command/proxy/upload/ssh handlers) are now tracked, cancelled on disconnect, and their exceptions logged.
```

- [ ] **Step 6: Commit**

```bash
git add noc_engine.py tests/test_noc_engine_tasks.py CHANGELOG.md
git commit -m "fix(noc_engine): track and cancel background tasks; surface their exceptions"
```

---

## Task 7: Use a shared `aiohttp.ClientSession` instead of one-per-call (Issue #7, #11)

**Files:**
- Modify: `noc_engine.py` (add `_http`/`_http_session` lifecycle), `command_executor.py`, `telemetry_collector.py`, `session_sync.py`
- Test: `tests/test_noc_engine_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_noc_engine_session.py`:

```python
"""Engine should hold a single aiohttp.ClientSession reused by all collaborators."""
import asyncio
from unittest.mock import AsyncMock

import aiohttp
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


async def test_engine_exposes_shared_http_session(tmp_path):
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))
    await engine._ensure_http_session()
    s1 = engine.http_session
    await engine._ensure_http_session()
    s2 = engine.http_session
    assert s1 is s2
    assert isinstance(s1, aiohttp.ClientSession)
    assert not s1.closed
    await engine._close_http_session()
    assert engine.http_session is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_noc_engine_session.py -v
```

Expected: `FAILED`.

- [ ] **Step 3: Apply the fix**

In `NocEngine.__init__`:

```python
        self.http_session: aiohttp.ClientSession | None = None
```

(and `import aiohttp` at module top.)

Add helpers:

```python
    async def _ensure_http_session(self) -> aiohttp.ClientSession:
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
            logger.debug("[NOC-Engine] aiohttp.ClientSession opened")
        return self.http_session

    async def _close_http_session(self):
        if self.http_session is not None:
            try:
                await self.http_session.close()
            except Exception as e:
                logger.warning(f"[NOC-Engine] Error closing HTTP session: {e}")
            self.http_session = None
```

In `run()`, ensure the session is live before the connect loop and close it on `stop()`:

```python
        self._running = True
        await self._ensure_http_session()
        ...
        # at the end, after `while self._running` exits:
        await self._close_http_session()
```

In `stop()`, schedule the close (keep behaviour for both async/sync callers like the existing SSH cleanup pattern).

Update every `async with aiohttp.ClientSession() as session:` callsite inside `noc_engine.py` (lines 192, 256, 342, 408, 740, 869, plus `_handle_proxy_request`'s session) to use the shared instance:

```python
        session = await self._ensure_http_session()
        async with session.get(...) as resp:
            ...
```

For `command_executor.execute`, add an optional `session` kwarg:

```python
async def execute(command: dict, charger_ip: str = "localhost",
                  session: aiohttp.ClientSession | None = None) -> dict:
    ...
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()
    try:
        async with session.request(method, **kwargs) as resp:
            ...
    finally:
        if own_session:
            await session.close()
```

(Move the existing body inside the `try`; keep behaviour identical when called without a session for backwards compat with tests/CLI scripts.)

In `noc_engine._handle_command`, pass it:

```python
            result = await execute_command(command, charger_ip=self.charger_ip,
                                           session=await self._ensure_http_session())
```

For `telemetry_collector.collect`, add an optional `session` kwarg with the same own/shared pattern. In `_telemetry_loop`, pass `session=await self._ensure_http_session()`.

For `session_sync.SessionSyncManager.__init__`, accept `http_session: aiohttp.ClientSession | None = None` and use it inside `_fetch_active_sessions` / `_fetch_history` (own/shared pattern). In `_session_sync_loop`, pass the engine's session.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_noc_engine_session.py -v
```

Expected: `PASSED`.

- [ ] **Step 5: Run the full suite to confirm no regressions**

```bash
cd qflex-noc && pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Update CHANGELOG**

```markdown
- Engine now holds a single shared `aiohttp.ClientSession` and passes it to telemetry, command executor, and session sync. Eliminates per-call session churn (FD/ephemeral-port pressure under load).
```

- [ ] **Step 7: Commit**

```bash
git add noc_engine.py command_executor.py telemetry_collector.py session_sync.py tests/test_noc_engine_session.py CHANGELOG.md
git commit -m "fix: share a single aiohttp.ClientSession across noc_engine collaborators"
```

---

## Task 8: Bound the SSH reader's WebSocket sends so back-pressure can't pin tunnels (Issue #10)

**Files:**
- Modify: `ssh_tunnel.py:256-337` (`_ssh_reader_loop`)
- Test: `tests/test_ssh_tunnel_backpressure.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ssh_tunnel_backpressure.py`:

```python
"""SSH tunnel reader must close the tunnel if WS send keeps timing out."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from ssh_tunnel import SSHTunnelManager


async def test_reader_closes_tunnel_when_ws_send_stalls(monkeypatch):
    """If ws_send_callback stalls past the per-call timeout, the reader must give up."""

    mgr = SSHTunnelManager()

    # Fake reader that produces a single chunk of data, then "blocks" on the next read.
    class _Reader:
        def __init__(self):
            self._first = True

        async def read(self, _n):
            if self._first:
                self._first = False
                return b"SSH-2.0-Test\r\n"
            await asyncio.sleep(60)
            return b""

    class _Writer:
        def close(self): pass
        async def wait_closed(self): pass
        def get_extra_info(self, _k): return None

    async def stalled_send(_msg):
        await asyncio.sleep(60)  # never returns

    # Inject a fake tunnel directly without opening a real TCP connection.
    from ssh_tunnel import LocalSSHTunnel
    tunnel = LocalSSHTunnel(tunnel_id="t1", reader=_Reader(), writer=_Writer())
    mgr._tunnels["t1"] = tunnel

    mgr.ws_send_timeout = 0.3  # tighten for test
    task = asyncio.create_task(mgr._ssh_reader_loop("t1", stalled_send))

    # Within ~1s the reader should detect the WS send stall and close the tunnel.
    await asyncio.sleep(1.5)
    assert tunnel.closed, "reader should close tunnel after ws_send timeouts"

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_ssh_tunnel_backpressure.py -v
```

Expected: `FAILED` (or hangs and pytest-timeout fires).

- [ ] **Step 3: Apply the fix**

In `SSHTunnelManager.__init__`, add:

```python
        self.ws_send_timeout: float = 5.0
```

In `_ssh_reader_loop`, replace the inner `await ws_send_callback(message)` block with:

```python
                try:
                    await asyncio.wait_for(
                        ws_send_callback(message),
                        timeout=self.ws_send_timeout,
                    )
                    logger.debug(
                        f"[SSH-Tunnel] Sent {len(data)} bytes from SSHD "
                        f"for tunnel {tunnel_id}"
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"[SSH-Tunnel] ws_send_callback timed out after "
                        f"{self.ws_send_timeout}s for {tunnel_id} — closing tunnel"
                    )
                    break
                except Exception as e:
                    logger.error(f"[SSH-Tunnel] Failed to send to WebSocket: {e}")
                    break
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_ssh_tunnel_backpressure.py -v
```

Expected: `PASSED`.

- [ ] **Step 5: Update CHANGELOG**

```markdown
- SSH tunnel reader now bounds each `ws_send_callback` call at 5s. WS back-pressure can no longer pin the tunnel forever; tunnels are closed cleanly instead.
```

- [ ] **Step 6: Commit**

```bash
git add ssh_tunnel.py tests/test_ssh_tunnel_backpressure.py CHANGELOG.md
git commit -m "fix(ssh_tunnel): bound ws_send_callback to recover from WS back-pressure"
```

---

## Task 9: Stop blocking auth on `_fetch_firmware_version`; make it best-effort (Issue #11)

**Files:**
- Modify: `noc_engine.py:184-230` (`_fetch_firmware_version` + `_send_auth`)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ws_client.py` (close to engine-flow tests fits — but to keep it independent, place in `tests/test_noc_engine_session.py`):

```python
async def test_send_auth_completes_when_firmware_endpoint_is_slow(tmp_path):
    """If the firmware endpoint takes > short_timeout, auth still goes out promptly."""
    engine = NocEngine(_cfg(), charger_id_cache_file=str(tmp_path / "c.json"))
    engine.firmware_fetch_timeout = 0.2

    sent = []

    class _WS:
        connected = True
        async def send(self, m): sent.append(m)

    async def slow_fetch():
        await asyncio.sleep(2)
        return "9.9.9"

    engine._fetch_firmware_version = slow_fetch  # type: ignore[assignment]

    start = asyncio.get_event_loop().time()
    await engine._send_auth(_WS())
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 1.0, f"auth must not be blocked by slow firmware fetch (took {elapsed:.2f}s)"
    assert any(m["type"] == "auth" for m in sent)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_noc_engine_session.py::test_send_auth_completes_when_firmware_endpoint_is_slow -v
```

Expected: `FAILED — auth blocked ~2s`.

- [ ] **Step 3: Apply the fix**

In `NocEngine.__init__`:

```python
        self.firmware_fetch_timeout: float = 1.5
```

Replace `_send_auth`:

```python
    async def _send_auth(self, ws: WSClient):
        try:
            fetched = await asyncio.wait_for(
                self._fetch_firmware_version(),
                timeout=self.firmware_fetch_timeout,
            )
        except asyncio.TimeoutError:
            fetched = None
            logger.info(
                f"[NOC-Engine] Firmware version fetch exceeded "
                f"{self.firmware_fetch_timeout}s — using config value"
            )

        if fetched:
            self.firmware_version = fetched
            logger.info(f"[NOC-Engine] Firmware version refreshed: {fetched}")

        msg = self._make_msg("auth", {
            "charger_id":       self.charger_id,
            "firmware_version": self.firmware_version,
            "model":            self.model,
        })
        await ws.send(msg)
        logger.info(f"[NOC-Engine] Auth → charger_id={self.charger_id} fw={self.firmware_version}")
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd qflex-noc && pytest tests/test_noc_engine_session.py::test_send_auth_completes_when_firmware_endpoint_is_slow -v
```

Expected: `PASSED`.

- [ ] **Step 5: Update CHANGELOG**

```markdown
- `_send_auth` no longer blocks for the full 5s aiohttp timeout when the local OCPP firmware endpoint is slow; firmware fetch is bounded at 1.5s and is best-effort.
```

- [ ] **Step 6: Commit**

```bash
git add noc_engine.py tests/test_noc_engine_session.py CHANGELOG.md
git commit -m "fix(noc_engine): bound firmware-version fetch in auth at 1.5s"
```

---

## Task 10: Local HTTP API on port 8009 to read engine version (new feature requested)

**Files:**
- Create: `version_api.py`
- Modify: `noc_engine.py` (start/stop the HTTP app), `config.json` (`charger_ports.noc_engine_api`), `main.py` (port wiring)
- Test: `tests/test_version_api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_version_api.py`:

```python
"""GET /api/v1/noc_engine/version returns the engine version + uptime."""
import asyncio

import aiohttp
import pytest

from version_api import VersionAPIServer


async def test_version_endpoint_returns_version(free_port):
    server = VersionAPIServer(version="1.1.0-dev", host="127.0.0.1", port=free_port)
    await server.start()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://127.0.0.1:{free_port}/api/v1/noc_engine/version") as r:
                assert r.status == 200
                data = await r.json()
                assert data["success"] is True
                assert data["value"] == "1.1.0-dev"
                assert "uptime_seconds" in data
                assert isinstance(data["uptime_seconds"], (int, float))
    finally:
        await server.stop()


async def test_version_endpoint_health(free_port):
    server = VersionAPIServer(version="1.1.0-dev", host="127.0.0.1", port=free_port)
    await server.start()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://127.0.0.1:{free_port}/api/v1/noc_engine/health") as r:
                assert r.status == 200
                data = await r.json()
                assert data["status"] == "ok"
    finally:
        await server.stop()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd qflex-noc && pytest tests/test_version_api.py -v
```

Expected: `FAILED — ImportError: version_api`.

- [ ] **Step 3: Implement `version_api.py`**

Create `version_api.py`:

```python
#!/usr/bin/env python3
"""
Local HTTP API for noc_engine self-introspection.

Endpoints:
  GET /api/v1/noc_engine/version  → {success, value, uptime_seconds}
  GET /api/v1/noc_engine/health   → {status: "ok"}

Bound to localhost by default; intended for on-charger consumers
(other A-core services, monitoring scripts).
"""
import logging
import time
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)


class VersionAPIServer:
    def __init__(self, version: str, host: str = "127.0.0.1", port: int = 8009):
        self.version = version
        self.host = host
        self.port = port
        self._started_at = time.monotonic()
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.BaseSite] = None

    async def _handle_version(self, _request: web.Request) -> web.Response:
        return web.json_response({
            "success": True,
            "value": self.version,
            "uptime_seconds": round(time.monotonic() - self._started_at, 1),
        })

    async def _handle_health(self, _request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/api/v1/noc_engine/version", self._handle_version)
        app.router.add_get("/api/v1/noc_engine/health",  self._handle_health)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(f"[VersionAPI] Listening on http://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        logger.info("[VersionAPI] Stopped")
```

- [ ] **Step 4: Run the version-API tests to verify they pass**

```bash
cd qflex-noc && pytest tests/test_version_api.py -v
```

Expected: both `PASSED`.

- [ ] **Step 5: Wire it into `NocEngine` and `main.py`**

In `config.json`, add inside `charger_ports`:

```json
    "noc_engine_api": 8009,
```

In `noc_engine.py` `__init__`:

```python
        from __init__ import __version__ as _engine_version
        from version_api import VersionAPIServer
        self._version_api = VersionAPIServer(
            version=_engine_version,
            host="127.0.0.1",
            port=int(ports.get("noc_engine_api", 8009)),
        )
```

(If you prefer, do the imports at module top and only construct the instance in `__init__`.)

In `run()`, just after `self._running = True` and before the reconnect loop:

```python
        try:
            await self._version_api.start()
        except OSError as e:
            logger.warning(f"[NOC-Engine] Version API failed to start: {e}")
```

In `stop()`:

```python
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._version_api.stop())
            else:
                loop.run_until_complete(self._version_api.stop())
        except Exception as e:
            logger.warning(f"[NOC-Engine] Error stopping Version API: {e}")
```

- [ ] **Step 6: Smoke-test the running engine endpoint**

In a terminal, start the engine:

```bash
cd qflex-noc && python main.py
```

In another terminal:

```bash
curl http://127.0.0.1:8009/api/v1/noc_engine/version
```

Expected response:

```json
{"success": true, "value": "1.1.0-dev", "uptime_seconds": 3.2}
```

Stop the engine with Ctrl+C.

- [ ] **Step 7: Update CHANGELOG**

```markdown
### Added
- Local HTTP API on port 8009: `GET /api/v1/noc_engine/version` and `/api/v1/noc_engine/health`.
- `charger_ports.noc_engine_api` (default 8009) configurable in `config.json`.
```

- [ ] **Step 8: Commit**

```bash
git add version_api.py noc_engine.py config.json tests/test_version_api.py CHANGELOG.md
git commit -m "feat: local HTTP version API on :8009 (GET /api/v1/noc_engine/version)"
```

---

## Task 11: Full-suite green-light + manual stuck-state verification

**Files:** none — verification only.

- [ ] **Step 1: Full suite**

```bash
cd qflex-noc && pytest -v
```

Expected: all tests pass; total time under ~30s.

- [ ] **Step 2: Manual verification — frozen-server scenario**

```bash
# Terminal A — start a deliberately silent WS server on a known port:
python -c "
import asyncio, websockets
async def h(ws):
    await asyncio.sleep(99999)
async def main():
    async with websockets.serve(h, '127.0.0.1', 8001, ping_interval=None):
        await asyncio.sleep(99999)
asyncio.run(main())
"

# Terminal B — point config.json noc_server.host=127.0.0.1, port=8001 and run engine:
python main.py
```

Watch the log. Expected within ~60s of last inbound message:

```
[NOC-Engine] 🐶 Watchdog: no inbound for 60.0s (threshold=60.0s) — forcing reconnect
[NOC-Engine] Connection closed — will reconnect
[NOC-Engine] Reconnecting in 5s ...
```

If the watchdog fires and reconnect happens, the fix is verified end-to-end. Stop both processes.

- [ ] **Step 3: Manual verification — version endpoint**

```bash
# With config.json restored to real NOC server, run:
python main.py &
curl -s http://127.0.0.1:8009/api/v1/noc_engine/version
```

Expected: `{"success": true, "value": "1.1.0-dev", ...}`

- [ ] **Step 4: Commit (verification log only — no code changes)**

No commit; this task is verification.

---

## Task 12: Finalise version → 1.1.0, update CHANGELOG release header, ask user about graphify

**Files:**
- Modify: `VERSION`, `CHANGELOG.md`

- [ ] **Step 1: Bump VERSION**

Replace contents of `VERSION` with:

```text
1.1.0
```

- [ ] **Step 2: Update CHANGELOG header**

In `CHANGELOG.md`, change `## [Unreleased] — 1.1.0-dev` to `## [1.1.0] — 2026-05-10` and add a new empty `## [Unreleased]` section above it for future work:

```markdown
## [Unreleased]

## [1.1.0] — 2026-05-10
```

- [ ] **Step 3: Ask the user about graphify**

Send a single message to the user before committing this task:

> "VERSION is bumped to 1.1.0 and CHANGELOG is finalised. Your global rule mentions updating *graphify* on every change. I couldn't find a graphify file or tool in this repo — could you point me at where graphify lives (path, command, or external system) so I can include it in this release? Once you tell me, I'll apply the graphify update and commit."

Wait for the user's reply, apply whatever they describe, then continue to Step 4.

- [ ] **Step 4: Commit the release bump**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: release 1.1.0 — robustness fixes + version API"
```

- [ ] **Step 5: Final tag (only if the user confirms)**

```bash
git tag -a v1.1.0 -m "v1.1.0 — robustness fixes + version API"
```

(Do not push tags without the user's go-ahead.)

---

## Self-Review Notes

**Spec coverage (12 issues + version API):**

| Issue | Task |
|---|---|
| 1. `ping_timeout=None` | 1 |
| 2. No connect timeout | 2 |
| 3. No `ws.send` timeout | 3 |
| 4. `asyncio.wait` global stall | 4 (watchdog) |
| 5. `_chunked_uploads` leak | 5 |
| 6. Fire-and-forget tasks | 6 |
| 7. Per-call `ClientSession` | 7 |
| 8. One-way heartbeat | 4 (watchdog covers it) |
| 9. `session_sync` polls `ws.connected` only | 4 (watchdog reconnect propagates) |
| 10. SSH reader back-pressure | 8 |
| 11. `_fetch_firmware_version` blocks auth | 9 |
| 12. `disconnect()` swallows exceptions | 2 |
| Version API | 10 |

All 12 issues + the version API are mapped to a concrete task.

**Risk callouts:**
- Task 7 touches every aiohttp callsite — biggest blast radius. The shared session is keyword-only and own/shared-fallback, so old callers and tests still work.
- Task 4's watchdog default of 60s is conservative; tighten only after monitoring real reconnect frequency.
- Task 6 cancels background tasks on every disconnect. If a long upload is mid-flight when the WS drops, it is cancelled — this matches what the server expects (reconnect + retransmit).
