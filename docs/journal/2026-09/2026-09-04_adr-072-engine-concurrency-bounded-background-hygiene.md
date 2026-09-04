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

- **Status:** Accepted — implemented 2026-09-04 (072.1–072.4), with one
  deliberate deviation from 072.3's literal wording. See **Implementation
  Note** below. Complements
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

## Implementation Note (2026-09-04)

- **072.1 (session-keyed state)** — implemented for the demonstrated bug:
  `VaultManager._last_searches` no longer has a shared `"default"` fallback key,
  so two *different* personas searching concurrently can no longer read each
  other's `/read <n>` results. **Not fully implemented**: two Slack *threads on
  the same persona* still share that persona's last-search cursor — full
  session-scoping would mean threading a session id through `VaultManager`'s
  static call sites in `commands.py`/`actions.py`, a materially bigger change
  than this pass. Flagged, not silently closed.
- **072.2 (engine lock)** — implemented. `PersonaEngine._lock`
  (`threading.RLock`) guards `histories`, `active_vault_ctx`, `active_sessions`,
  `model_overrides`; added `get/set/clear_model_override()` so `commands.py` no
  longer mutates the dict directly. Deliberately kept vault retrieval and the
  `litellm.completion` streaming call **outside** the lock — serializing those
  would defeat this session's own caching work and freeze every other
  persona/thread behind one slow chat.
- **072.3 (bounded pool)** — implemented, **not** as a literal
  `ThreadPoolExecutor`. Its worker threads are non-daemon by design (the
  module's `atexit` hook joins them), which would make CLI `quit` block on any
  in-flight background LLM call — a real regression against the "zero
  time-delay" persona rules. Used a semaphore-gated pool of daemon threads
  instead (`compactor.run_hygiene_task`), matching the pattern `slack.py`
  already uses for its per-channel semaphore. Same bounded-concurrency
  guarantee, no exit-blocking behavior change.
- **072.4 (single-flight compaction)** — implemented via an in-flight-path set
  guarded by the existing `_GLOBAL_LOCK`.

Verified with three throwaway smoke tests (12 threads hammering engine state
for 2s — no deadlock; MCP-side out-of-order routing, see ADR-065 amendment
below; 20 concurrent compaction triggers on one file → exactly 1 run), deleted
after passing. `.venv/bin/pytest` 101/101 throughout. Implemented in commit
`9dc12a3` on `chore/backend-architecture-review-and-fixes`; see the
[implementation journal entry](./2026-09-04_backend-hardening-implementation.md).

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
