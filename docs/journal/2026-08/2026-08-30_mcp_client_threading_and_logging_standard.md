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

## 2. Architectural Decisions

- **[ADR-065 - MCP Client Threading & Logging Standard](./2026-08-30_adr-065-mcp-client-threading-logging-standard.md):**
  a dual-lock model - `_lock` for the request-id counter, `_io_lock` serialising
  one write+read cycle per client (065.1); a structured `logging` standard
  replacing `print()` in backend/daemon modules, with a `cli.py` / `ui.py`
  `rich.console` carve-out (065.2); a `select()` non-blocking read loop so a
  stalled subprocess cannot hold the lock (065.3). Rejected a full async
  dispatch table (would force an async engine migration, against
  [ADR-020](./2026-08-25_adr-020-zero-maintenance-mandate.md)).

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
