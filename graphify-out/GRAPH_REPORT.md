# Graph Report - qflex-noc  (2026-05-13)

## Corpus Check
- 20 files · ~19,788 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 269 nodes · 618 edges · 18 communities detected
- Extraction: 51% EXTRACTED · 49% INFERRED · 0% AMBIGUOUS · INFERRED: 302 edges (avg confidence: 0.52)
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
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]

## God Nodes (most connected - your core abstractions)
1. `SessionSyncManager` - 81 edges
2. `SSHTunnelManager` - 79 edges
3. `WSClient` - 78 edges
4. `VersionAPIServer` - 73 edges
5. `NocEngine` - 65 edges
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
Cohesion: 0.09
Nodes (50): Post complete file to dev-tools service on port 8005., Main engine loop. Connects to NOC server and starts all sub-loops.         On d, Main engine loop. Connects to NOC server and starts all sub-loops.         On d, Stop the NOC engine and cleanup resources., Stop the NOC engine and cleanup resources., Stop the NOC engine and cleanup resources., Read the engine's own package version from the VERSION file., Read the engine's own package version from the VERSION file. (+42 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (27): NocEngine, Core NOC engine class.      Args:         config: Parsed config.json dict, _cfg(), Engine should hold a single aiohttp.ClientSession reused by all collaborators., If the firmware endpoint takes > firmware_fetch_timeout, auth still goes out pro, After explicit close, ensure_http_session must create a new live session., test_close_then_ensure_creates_new_session(), test_engine_exposes_shared_http_session() (+19 more)

### Community 2 - "Community 2"
Cohesion: 0.1
Nodes (14): _now_iso(), Main engine loop. Connects to NOC server and starts all sub-loops.         On d, Build the WebSocket URI from current noc_url (or host/port) + charger_id., Merge `updates` into the runtime cache file (preserves other fields)., Fetch firmware version from the charger's OCPP config endpoint.         Returns, Poll :8003/api/v1/system/version five times at 20-second intervals         imme, Send heartbeat every N seconds to keep the connection alive., Collect and push charger telemetry every N seconds. (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (14): main(), Start the session sync loop., Stop the session sync loop., Main sync loop - runs every 30 seconds., Perform one sync cycle., Fetch active sessions from local APIs for both guns., Detect sessions that were active but are now completed., Fetch session history from local API (incremental). (+6 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (14): LocalSSHTunnel, Create a new TCP connection to local SSHD.                  Args:, Decode Base64 data and write to SSHD connection.                  Args:, Background task: Read from SSHD, Base64 encode, send via WebSocket., Represents a single SSH tunnel from WebSocket to local SSHD.          Attribut, Close tunnel and cleanup resources.          Args:             tunnel_id: Tun, Calculate tunnel statistics., Return statistics for all active tunnels. (+6 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (17): _fetch_charger_id(), _fetch_noc_url(), _load_cached_charger_id(), _load_cached_noc_url(), _main(), Save charger ID components to persistent cache file., Load NOC URL from persistent cache file., Save NOC URL to persistent cache file. (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (7): Post complete file to dev-tools service on port 8005., Schedule a fire-and-forget coroutine so we can cancel it later         and log, Receive messages from NOC server and dispatch them.         Handles:, Handle SSH tunnel open request from NOC Server.         Creates TCP connection, Handle SSH data from client (via NOC Server).         Forward to local SSHD., Handle SSH tunnel close request from NOC Server.         Clean up the tunnel an, Handle file upload chunk from NOC Server. Accumulates chunks and posts to port 8

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (10): Serialize and send a JSON message, bounded by ``send_timeout``.          Raise, Open WebSocket connection to the NOC server., Close the WebSocket connection gracefully (bounded)., If the underlying close() hangs, disconnect must still return within ~6s., A send() that drains slower than send_timeout must raise asyncio.TimeoutError., ping_timeout MUST be a finite value so the websockets library can detect a froze, test_connect_passes_open_timeout(), test_connect_passes_ping_timeout_20() (+2 more)

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
Cohesion: 0.5
Nodes (2): Args:             noc_ws_client: WebSocket client connected to NOC Server, Load sync state from local JSON file.

### Community 12 - "Community 12"
Cohesion: 0.5
Nodes (3): GET /api/v1/noc_engine/version returns the engine version + uptime., test_version_endpoint_health(), test_version_endpoint_returns_version()

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (2): execute(), Execute a proxy command received from the NOC server.      Args:         comm

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Return number of active tunnels.

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Return list of active tunnel IDs.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Receive the next JSON message.          Raises:             ConnectionError:

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): NocEngine — Remote Charger Management Module ===================================

## Knowledge Gaps
- **46 isolated node(s):** `Execute a proxy command received from the NOC server.      Args:         comm`, `Manages session data synchronization from charger APIs to NOC Server.`, `Args:             noc_ws_client: WebSocket client connected to NOC Server`, `Load sync state from local JSON file.`, `Persist sync state to local JSON file.` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (4 nodes): `Args:             noc_ws_client: WebSocket client connected to NOC Server`, `Load sync state from local JSON file.`, `.__init__()`, `._load_state()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (3 nodes): `command_executor.py`, `execute()`, `Execute a proxy command received from the NOC server.      Args:         comm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (2 nodes): `Return number of active tunnels.`, `.get_tunnel_count()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (2 nodes): `Return list of active tunnel IDs.`, `.get_tunnel_ids()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (2 nodes): `Receive the next JSON message.          Raises:             ConnectionError:`, `.receive()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `__init__.py`, `NocEngine — Remote Charger Management Module ===================================`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `NocEngine` connect `Community 1` to `Community 0`, `Community 2`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.365) - this node is a cross-community bridge._
- **Why does `SessionSyncManager` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 6`, `Community 11`?**
  _High betweenness centrality (0.240) - this node is a cross-community bridge._
- **Why does `SSHTunnelManager` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 6`, `Community 14`, `Community 15`?**
  _High betweenness centrality (0.239) - this node is a cross-community bridge._
- **Are the 64 inferred relationships involving `SessionSyncManager` (e.g. with `NocEngine` and `Core NOC engine class.      Args:         config: Parsed config.json dict`) actually correct?**
  _`SessionSyncManager` has 64 INFERRED edges - model-reasoned connections that need verification._
- **Are the 67 inferred relationships involving `SSHTunnelManager` (e.g. with `NocEngine` and `Core NOC engine class.      Args:         config: Parsed config.json dict`) actually correct?**
  _`SSHTunnelManager` has 67 INFERRED edges - model-reasoned connections that need verification._
- **Are the 71 inferred relationships involving `WSClient` (e.g. with `NocEngine` and `Core NOC engine class.      Args:         config: Parsed config.json dict`) actually correct?**
  _`WSClient` has 71 INFERRED edges - model-reasoned connections that need verification._
- **Are the 67 inferred relationships involving `VersionAPIServer` (e.g. with `NocEngine` and `Core NOC engine class.      Args:         config: Parsed config.json dict`) actually correct?**
  _`VersionAPIServer` has 67 INFERRED edges - model-reasoned connections that need verification._