---
title: "ADR-038 — Post-Remediation Hardening & Defensive Engineering Standards"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-038 — Post-Remediation Hardening & Defensive Engineering Standards

- **Status:** Accepted — predates `sympose/server.py`; the dashboard/API auth gap
  it did not cover is addressed by
  [ADR-064](./2026-08-30_adr-064-dashboard-api-auth-plan.md)
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

A technical audit of the codebase (19 modules, prompt pipelines, Slack daemon,
compactor, workers) found 25 edge-case anomalies across two passes, revealing
failure modes that needed to become binding standards: hardcoded identity
fallbacks; sibling-path bypass in string-prefix sandbox checks; multi-agent
in-memory state clobbering; async compaction write races; orphaned MCP
subprocesses and blocking I/O; and session-log bleed into `_memory.md`.

## Decision

Ratify **6 defensive engineering & hardening standards**:

1. **Zero hardcoded identity.** No username / persona / handle hardcoded
   anywhere; resolve dynamically from `ProfileManager` and `os.getenv("USER")`;
   regex parsers strip Markdown decorators.
2. **Directory-delimited path boundary validation.** `str.startswith()` for
   sandbox checks is prohibited; use
   `os.path.commonpath([target, base]) == base` or `Path.is_relative_to()`.
3. **Anchored relative asset discovery.** Template / config lookups anchor to the
   package root, with CWD only as a secondary fallback.
4. **Session-isolated multi-client concurrency & lifecycle hooks.**
   `chat_stream` / `get_history` / `reset_history` take an explicit
   `session_id`; spawned subprocesses register `atexit` cleanup.
5. **Thread-safe memory compaction & snapshot reconciliation.** Async compaction
   takes a process-wide `get_file_lock(filepath)`, snapshots lines, and re-reads
   under lock on completion to preserve newly appended facts.
6. **Discrete working-memory line standard.** `*_memory.md` files contain only
   discrete bullets; extraction / summarization filters to bullet lines before
   appending.

## Consequences

**Positive**

- Immunity to traversal and sibling-path escapes.
- Flawless multi-agent Slack thread isolation; zero lost memories under async
  compaction; clean subprocess shutdown. 23/23 tests pass.

**Negative / costs**

- The pass ran on 2026-08-26, **before** `sympose/server.py` and its `/api/*`
  surface existed (2026-08-27–29), so the dashboard shipped with no auth review —
  the gap ADR-064 later documents.

## Alternatives rejected

> Not captured in the original decision record.
