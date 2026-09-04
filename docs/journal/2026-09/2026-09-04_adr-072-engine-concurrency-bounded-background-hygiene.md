---
title: "ADR-072 — Engine Concurrency Model & Bounded Background Hygiene Pool"
created: 2026-09-04
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - concurrency
---

# ADR-072 — Engine Concurrency Model & Bounded Background Hygiene Pool

- **Status:** Proposed — pending implementation. Complements
  [ADR-065](../2026-08/2026-08-30_adr-065-mcp-client-threading-logging-standard.md)
  (MCP client threading) and
  [ADR-028](../2026-08/2026-08-25_adr-028-slack-socket-mode-thread-context-isolation.md)
  (Slack thread isolation); consistent with
  [ADR-020](../2026-08/2026-08-25_adr-020-zero-maintenance-mandate.md).
  Source: [2026-09-04 Backend Architecture & Objective-Effectiveness Review](./2026-09-04_backend-architecture-effectiveness-review.md) (F8–F10).
- **Date:** 2026-09-04
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`MultiAgentSlackRunner` runs one `SlackDaemon` per persona; each dispatches
`_process_message` in a fresh daemon thread
([slack.py:220](../../../sympose/slack.py#L220)); all share **one
`PersonaEngine`** instance. The engine holds plain dicts mutated with unguarded
read-modify-write from N threads:

- `self.histories`, `self.active_vault_ctx`, `self.model_overrides`,
  `self.active_sessions` ([engine.py:24-27](../../../sympose/engine.py#L24-L27)).
- `VaultManager._last_searches` is a **class-level dict** with a shared
  `"default"` key ([vault.py:313](../../../sympose/vault.py#L313)) that every
  search overwrites — two Slack threads searching concurrently corrupt each
  other's `/read <n>` / number-selection context.
- `_BACKLINK_CACHE` is a module global with no lock
  ([vault.py:15](../../../sympose/vault.py#L15)).

Background work is also unbounded. Per qualifying turn the engine may spawn:

- `HeuristicGatedExtractor.extract_async` — a thread running an LLM call
  ([memory.py:85](../../../sympose/memory.py#L85));
- at turn 3, `generate_smart_title_async` — another thread, another LLM call
  ([sessions.py:119](../../../sympose/sessions.py#L119));
- `append_memory` → `check_and_compact_async`
  ([compactor.py:126](../../../sympose/compactor.py#L126)) — the trigger is
  `count >= threshold` and compaction is async, so **every turn** between
  crossing the threshold and the first compaction completing spawns its own
  compaction thread on the same file. The per-file lock serialises the writes,
  but every thread still runs the full LLM distillation call.

There is no thread pool, no dedupe, no backpressure. Under a busy multi-agent
Slack channel this piles up.

## Decision

Proposed, not yet implemented:

- **ADR-072.1 — Session-keyed state, no shared fallbacks.** All per-conversation
  engine state is keyed strictly by `_get_history_key(handle, session_id)`.
  `VaultManager._last_searches` drops the `"default"` key and is keyed by
  `handle` (+ session where available). Last-search state moves onto the engine
  (per-session) rather than living as `VaultManager` class state.
- **ADR-072.2 — One lock for engine dicts.** A single `threading.RLock` on
  `PersonaEngine` guards mutation of `histories` / `active_vault_ctx` /
  `model_overrides` / `active_sessions`; `_BACKLINK_CACHE` gets its own module
  lock (mirroring `compactor._GLOBAL_LOCK`).
- **ADR-072.3 — Bounded hygiene pool.** Replace ad-hoc `threading.Thread(...)`
  for extraction, titling, and compaction with a single
  `ThreadPoolExecutor(max_workers=performance.hygiene_workers, default 2)` owned
  by the engine. Daemon behaviour preserved; the process still exits without
  joining.
- **ADR-072.4 — Single-flight compaction.** A module-level `set` of in-flight
  compaction paths (or `Lock.acquire(blocking=False)` per target) so at most one
  compaction per file is ever queued, regardless of how many turns crossed the
  threshold.

## Consequences

**Positive** (anticipated — not yet implemented)

- No cross-thread context corruption in Slack multi-agent use.
- Bounded, predictable background load; the "zero-maintenance" mandate holds
  under real concurrency, not just single-user CLI.
- Compaction runs once per threshold crossing, not once per turn.

**Negative / costs**

- A hygiene pool cap means extraction/titling can queue briefly under burst
  load; acceptable — this work is already best-effort and off the response path.
- One RLock introduces a (tiny) serialisation point on dict mutation; the
  critical sections are dict writes, sub-microsecond.

## Alternatives rejected

- **One `PersonaEngine` per Slack daemon thread.** Removes the sharing but
  fragments history and model overrides per thread and multiplies memory-file
  handles; the session-key discipline already gives isolation without it.
- **`queue.Queue` + a single worker thread for all hygiene.** Simpler than a
  pool but serialises unrelated LLM calls behind each other; a 2-worker pool is
  the smaller change with better latency.
- **Leave it (single-user CLI is the real workload).** Rejected — Slack
  multi-agent is a shipped, documented feature (ADR-028) and is exactly where
  the races bite.
