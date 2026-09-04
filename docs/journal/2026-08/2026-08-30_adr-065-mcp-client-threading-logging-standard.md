---
title: "ADR-065 — MCP Client Threading & Logging Standard"
created: 2026-08-30
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-065 — MCP Client Threading & Logging Standard

- **Status:** Accepted — hardens the client from
  [ADR-013](./2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md) /
  [ADR-032](./2026-08-26_adr-032-first-class-mcp-directory-modular-hub.md)
- **Date:** 2026-08-30
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner) with Antigravity IDE

## Context

`MCPClient` wraps a JSON-RPC 2.0 stdio subprocess. The write+read cycle in
`_send_request()` was unguarded: two concurrent `call_tool()` callers on one
client could race on stdout and steal each other's response frame, causing silent
failures or hangs. All diagnostics used bare `print()`, impossible to filter or
route in production without patching source.

## Decision

- **ADR-065.1 — Dual-lock threading model.** `self._lock` guards the
  `_request_id` counter; `self._io_lock` serialises one write+read cycle at a
  time. `_send_request()` holds `_io_lock` for the whole write-then-readline
  loop — one in-flight request per client.
- **ADR-065.2 — Structured logging standard.** Replace `print()` with
  `logging.getLogger(__name__)` in backend / daemon modules
  (`mcp_client`, `mcp`, `profiles`, `skills`, `slack`, `server`, `compactor`) at
  appropriate levels. **Carve-out:** `cli.py` / `ui.py` keep
  `rich.console.print()` for intentional terminal UI — not logging.
- **ADR-065.3 — `select()` non-blocking read loop.** The read loop uses
  `select.select()` with a 50 ms poll instead of blocking `readline()`, so a
  stalled subprocess cannot hold the lock forever and the timeout is enforced.

Also: `slack.py` gains a per-channel `Semaphore(3)` rate limit; `server.py`
reports its version via `importlib.metadata`; `config.py` centralises
`DEFAULT_CHAT_MODEL` / `DEFAULT_WORKER_MODEL`.

## Consequences

**Positive**

- Concurrent worker tool calls on one client are correct and safe.
- MCP noise is filterable / routable without source edits.
- `pytest` — 101 passed.

**Negative / costs**

- One in-flight JSON-RPC request per client (no pipelining) — accepted as the
  simple, zero-dependency correct fix.

## Alternatives rejected

- **A full async dispatch table (per-request `asyncio` correlation).** Rejected:
  would require migrating the whole engine to async, against the Zero-Maintenance
  Mandate ([ADR-020](./2026-08-25_adr-020-zero-maintenance-mandate.md)); worker
  tasks are already thread-isolated, so a single I/O lock is sufficient.
