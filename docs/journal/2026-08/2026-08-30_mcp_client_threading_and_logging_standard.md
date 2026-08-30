---
entry: 2026-08-30
created: 2026-08-30 19:05
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - mcp/client
  - threading
  - structured-logging
  - adr-065
---

# Engineering Journal: MCP Client Threading & Logging Standard (ADR-065)

> **Date:** August 30, 2026
> **Lead Architect:** damiro
> **Engineering Partner:** Grace / Antigravity IDE
> **Status:** APPROVED & IMPLEMENTED (ADR-065)

---

## 1. Context & Motivation

`MCPClient` wraps a JSON-RPC 2.0 stdio subprocess (e.g. `npx @modelcontextprotocol/server-*`).
Before this ADR the write+read cycle in `_send_request()` was unguarded: two concurrent
`call_tool()` callers on the same client could race on the subprocess stdout, stealing each
other's response frame and causing silent failures or hangs.

Additionally, all diagnostic output used bare `print()` statements, making it impossible to
filter, route, or suppress MCP noise in production without patching source.

---

## 2. Architectural Decisions (ADR-065)

### ADR-065.1: Dual-Lock Threading Model

`MCPClient` now carries **two** locks with distinct responsibilities:

```python
self._lock     = threading.Lock()   # guards _request_id counter (increment atomicity)
self._io_lock  = threading.Lock()   # serialises one write+read cycle at a time
```

`_send_request()` acquires `_io_lock` for the entire write-then-readline loop.
This means only one in-flight JSON-RPC request is active per client at a time — correct,
simple, and safe without the complexity of a full async dispatch table.

```python
def _send_request(self, payload):
    """Thread-safe JSON-RPC request/response cycle. Serialised via _io_lock."""
    with self._io_lock:
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()
        # ... select() read loop ...
```

**Why not an async dispatch table?**  
Worker tasks are already isolated in threads; adding a per-request `asyncio` layer would
require migrating the entire engine to async, which violates the Zero-Maintenance Mandate
(ADR-020). The single-lock approach is a correct, zero-dependency fix.

### ADR-065.2: Structured Logging Standard

All `print()` calls in backend/daemon modules are replaced with `logging.getLogger(__name__)`:

| Module | Level | Rationale |
|---|---|---|
| `mcp_client.py` | `log.warning(...)` | Spawn failures & init errors are operator-relevant warnings |
| `mcp.py` | `log.warning(...)` | Registry-level tool load failures |
| `profiles.py` | `log.warning(...)` | Missing or malformed profile files |
| `skills.py` | `log.warning(...)` | Skill parse errors |
| `slack.py` | `log.info/warning/error` | Connection, message, and rate-limit events |
| `server.py` | `log.info(...)` | Request lifecycle events |
| `compactor.py` | `log.info/warning` | Compaction progress and lock events |

> **Carve-out:** `cli.py` and `ui.py` use `rich.console.print()` for intentional terminal
> UI output. These are **not** logging calls and are **not** changed.

### ADR-065.3: `select()` Non-Blocking Read Loop

The read loop in `_send_request()` uses `select.select()` with a 50 ms poll interval
instead of a blocking `readline()`. This prevents the lock from hanging forever if the
subprocess stalls, and allows the timeout to be enforced reliably:

```python
while time.time() - start_time < self.timeout:
    rlist, _, _ = select.select([self.process.stdout], [], [], 0.05)
    if not rlist:
        continue
    line = self.process.stdout.readline()
    ...
```

---

## 3. Scope of Changes

| File | Change |
|---|---|
| `sympose/mcp_client.py` | Added `_io_lock`; replaced `print()` with `log.*`; added `select()` loop |
| `sympose/mcp.py` | Replaced `print()` with `log.warning()` |
| `sympose/profiles.py` | Replaced `print()` with `log.warning()` |
| `sympose/skills.py` | Replaced `print()` with `log.warning()` |
| `sympose/slack.py` | Full logging migration + per-channel `Semaphore(3)` rate limiting |
| `sympose/server.py` | Replaced `print()` with `log.info()`; dynamic version via `importlib.metadata` |
| `sympose/compactor.py` | Added structured logging + file locking |
| `sympose/config.py` | Centralised `DEFAULT_CHAT_MODEL` / `DEFAULT_WORKER_MODEL` constants |

---

## 4. Verification

```text
pytest tests/ — 101 passed, 0 failed
python -m ast sympose/mcp_client.py  — OK
grep "print(" sympose/mcp_client.py sympose/mcp.py sympose/profiles.py sympose/skills.py — 0 matches
```
