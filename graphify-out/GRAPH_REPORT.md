# Graph Report - qflex-noc  (2026-05-10)

## Corpus Check
- 20 files · ~19,579 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 241 nodes · 506 edges · 13 communities detected
- Extraction: 62% EXTRACTED · 38% INFERRED · 0% AMBIGUOUS · INFERRED: 190 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]

## God Nodes (most connected - your core abstractions)
1. `NocEngine` - 65 edges
2. `SessionSyncManager` - 53 edges
3. `SSHTunnelManager` - 51 edges
4. `WSClient` - 50 edges
5. `VersionAPIServer` - 45 edges
6. `LocalSSHTunnel` - 8 edges
7. `_main()` - 6 edges
8. `_read_cache()` - 5 edges
9. `_write_cache()` - 5 edges
10. `_fetch_charger_id()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Read the runtime-discovered cache file. Returns {} on any error.` --uses--> `NocEngine`  [INFERRED]
  main.py → noc_engine.py
- `Merge `updates` into the cache file (preserves other fields).` --uses--> `NocEngine`  [INFERRED]
  main.py → noc_engine.py
- `Load charger_id from persistent cache file.` --uses--> `NocEngine`  [INFERRED]
  main.py → noc_engine.py
- `Save charger ID components to persistent cache file.` --uses--> `NocEngine`  [INFERRED]
  main.py → noc_engine.py
- `Load NOC URL from persistent cache file.` --uses--> `NocEngine`  [INFERRED]
  main.py → noc_engine.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (20): Stop the NOC engine and cleanup resources., Collect and push session data every 30 seconds., main(), Start the session sync loop., Stop the session sync loop., Main sync loop - runs every 30 seconds., Perform one sync cycle., Fetch active sessions from local APIs for both guns. (+12 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (22): Main engine loop. Connects to NOC server and starts all sub-loops.         On d, Drop any chunked-upload entry that hasn't completed within the TTL., Post complete file to dev-tools service on port 8005., LocalSSHTunnel, Create a new TCP connection to local SSHD.                  Args:, Decode Base64 data and write to SSHD connection.                  Args:, Background task: Read from SSHD, Base64 encode, send via WebSocket., Represents a single SSH tunnel from WebSocket to local SSHD.          Attribut (+14 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (16): Stop the NOC engine and cleanup resources., Send heartbeat every N seconds to keep the connection alive., Schedule a fire-and-forget coroutine so we can cancel it later         and log, Receive messages from NOC server and dispatch them.         Handles:, Execute a proxy command, then push the result back to the server., Handle SSH tunnel open request from NOC Server.         Creates TCP connection, Handle SSH data from client (via NOC Server).         Forward to local SSHD., Handle SSH tunnel close request from NOC Server.         Clean up the tunnel an (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.13
Nodes (26): NocEngine, _cfg(), Engine should hold a single aiohttp.ClientSession reused by all collaborators., If the firmware endpoint takes > firmware_fetch_timeout, auth still goes out pro, After explicit close, ensure_http_session must create a new live session., test_close_then_ensure_creates_new_session(), test_engine_exposes_shared_http_session(), test_send_auth_completes_when_firmware_endpoint_is_slow() (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (17): Read the engine's own package version from the VERSION file., Core NOC engine class.      Args:         config: Parsed config.json dict, Drop any chunked-upload entry that hasn't completed within the TTL., Background sweeper — runs at TTL/4 intervals as long as the engine is running., Serialize and send a JSON message, bounded by ``send_timeout``.          Raise, Receive the next JSON message.          Raises:             ConnectionError:, Thin WebSocket wrapper used by NocEngine.      Usage:         client = WSClie, Open WebSocket connection to the NOC server. (+9 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (17): _fetch_charger_id(), _fetch_noc_url(), _load_cached_charger_id(), _load_cached_noc_url(), _main(), Save charger ID components to persistent cache file., Load NOC URL from persistent cache file., Save NOC URL to persistent cache file. (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (9): Post complete file to dev-tools service on port 8005., Main engine loop. Connects to NOC server and starts all sub-loops.         On d, Return an SSL context for WSS connections., Fetch firmware version from the charger's OCPP config endpoint.         Returns, Poll :8003/api/v1/system/version five times at 10-second intervals         imme, Collect and push charger telemetry every N seconds., Lazily create the shared aiohttp.ClientSession (re-creates if it was closed)., Close the shared aiohttp.ClientSession (idempotent). (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.2
Nodes (6): _now_iso(), Build the WebSocket URI from current noc_url (or host/port) + charger_id., Merge `updates` into the runtime cache file (preserves other fields)., Poll local APIs every 10s to refresh charger ID and update cache.          On, Poll local API every 10s to refresh the NOC server URL and update cache., _read_engine_version()

### Community 8 - "Community 8"
Cohesion: 0.31
Nodes (8): copy_to_folder(), iter_matching_files(), main(), Export the qflex-charging project, keeping only .py, .json, .js, and .html files, Write ``files`` to ``zip_path`` under a top-level directory ``arc_root``., Yield files under ``root`` whose suffix is in ``include_exts``.      Skips any, Copy each file under ``folder_root`` preserving its path relative to PROJECT_ROO, write_zip()

### Community 9 - "Community 9"
Cohesion: 0.29
Nodes (5): echo_ws_server(), Shared pytest fixtures: free-port allocator, controllable WS servers., A WS server that echoes every message back., A WS server that accepts the connection but never reads/writes — simulates a fro, silent_ws_server()

### Community 10 - "Community 10"
Cohesion: 0.5
Nodes (4): collect(), _fetch(), Collect telemetry from all configured local API sources.      Args:         a, Fetch a single JSON endpoint.      Returns:         (key, data_or_None, healt

### Community 11 - "Community 11"
Cohesion: 0.67
Nodes (2): execute(), Execute a proxy command received from the NOC server.      Args:         comm

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (1): NocEngine — Remote Charger Management Module ===================================

## Knowledge Gaps
- **46 isolated node(s):** `Execute a proxy command received from the NOC server.      Args:         comm`, `Manages session data synchronization from charger APIs to NOC Server.`, `Args:             noc_ws_client: WebSocket client connected to NOC Server`, `Load sync state from local JSON file.`, `Persist sync state to local JSON file.` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (3 nodes): `command_executor.py`, `execute()`, `Execute a proxy command received from the NOC server.      Args:         comm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (2 nodes): `__init__.py`, `NocEngine — Remote Charger Management Module ===================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `NocEngine` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.396) - this node is a cross-community bridge._
- **Why does `SessionSyncManager` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.237) - this node is a cross-community bridge._
- **Why does `SSHTunnelManager` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.236) - this node is a cross-community bridge._
- **Are the 34 inferred relationships involving `NocEngine` (e.g. with `Read the runtime-discovered cache file. Returns {} on any error.` and `Merge `updates` into the cache file (preserves other fields).`) actually correct?**
  _`NocEngine` has 34 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `SessionSyncManager` (e.g. with `NocEngine` and `Core NOC engine class.      Args:         config: Parsed config.json dict`) actually correct?**
  _`SessionSyncManager` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `SSHTunnelManager` (e.g. with `NocEngine` and `Core NOC engine class.      Args:         config: Parsed config.json dict`) actually correct?**
  _`SSHTunnelManager` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 43 inferred relationships involving `WSClient` (e.g. with `NocEngine` and `Core NOC engine class.      Args:         config: Parsed config.json dict`) actually correct?**
  _`WSClient` has 43 INFERRED edges - model-reasoned connections that need verification._