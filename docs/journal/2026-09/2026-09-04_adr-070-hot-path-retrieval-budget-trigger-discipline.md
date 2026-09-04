---
title: "ADR-070 — Hot-Path Vault Retrieval Budget, Trigger Discipline & Indexed Search Tier"
created: 2026-09-04
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - performance
---

# ADR-070 — Hot-Path Vault Retrieval Budget, Trigger Discipline & Indexed Search Tier

- **Status:** Accepted — 070.1, 070.3, and 070.5 implemented (070.5 on
  2026-09-05); 070.2 and 070.4 rejected in favor of round-trip frugality
  rather than deferred as originally scoped. See **Implementation Note**
  below. Extends
  [ADR-003](../2026-08/2026-08-24_adr-003-pluggable-multi-tier-vault-search.md)
  (pluggable search tiers) and
  [ADR-025](../2026-08/2026-08-25_adr-025-persistent-multi-turn-vault-context.md)
  (pre-turn vault context); consistent with
  [ADR-052](../2026-08/2026-08-29_adr-052-in-memory-metadata-caching-scalability.md).
  Source: [2026-09-04 Backend Architecture & Objective-Effectiveness Review](./2026-09-04_backend-architecture-effectiveness-review.md) (F1–F4).
- **Date:** 2026-09-04
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`PersonaEngine.chat_stream` calls `VaultManager.resolve_turn_context`
**synchronously on the main thread before the first `litellm.completion` call**
([engine.py:158](../../../sympose/engine.py#L158)). For any agent holding the
`vault_recall` skill (Samantha ships with it), that call can:

- run multiple `os.walk`s over the allowed vault dirs, and
- via `search` → `search_structured`
  ([vault.py:212](../../../sympose/vault.py#L212)), **read the entire body of
  every `.md` / `.markdown` / `.txt` file** in scope, every turn.

The trigger gate is `config.yaml` `vault.search_triggers`, which currently
includes bare stop-words — `what`, `who`, `which`, `have`, `know`, `get`,
`give`, `show`, `tell`, `check`. Almost any natural question fires the walk.

`build_backlink_index` already guards itself with a
`tuple(sorted(allowed_dirs)) → (mtime, index)` cache
([vault.py:471](../../../sympose/vault.py#L471)). `search_structured` and
`get_folder_digest` have **no such cache** and re-walk on every call.

Separately, `ProfileManager.build_system_prompt`
([profiles.py:183](../../../sympose/profiles.py#L183)) reads ~6 files from disk
(soul, user card, shared memory, persona memory, workspace rules, skills) on
**every turn of every thread**, uncached.

Net effect: the advertised `<0.8 s TTFT` SLA holds only for a trivially small
vault or a message that dodges the trigger list. `.env.example` and ADR-003 also
advertise `sqlite_fts` and `semantic` search modes that were never implemented —
`direct` (full Python walk) is the only path.

## Decision

Proposed, not yet implemented:

- **ADR-070.1 — Explicit-intent trigger gate.** Replace the bare-stop-word
  `search_triggers` list with intent phrases that require a retrieval verb plus
  an object (`search vault`, `what notes`, `pull up`, `find … note`,
  `backlinks for`, `in <folder>`). A message that matches no phrase skips
  `resolve_turn_context` entirely.
- **ADR-070.2 — Bounded pre-inference budget.** When retrieval does run, execute
  it concurrently with system-prompt assembly under a hard wall-clock budget
  (default `performance.retrieval_budget_ms: 150`). On timeout, proceed without
  the injected context; the model can still call the retrieval tool
  (ADR-070.4) mid-turn.
- **ADR-070.3 — mtime cache on all vault walks.** Apply the `_BACKLINK_CACHE`
  pattern to `search_structured` and `get_folder_digest`, and mtime-cache the
  `build_system_prompt` file reads (the latter tracked jointly with ADR-052).
- **ADR-070.4 — Retrieval as a callable tool.** Expose vault search / digest /
  read as a native tool (same `tools=[…]` path the worker engine already uses,
  [workers.py:217](../../../sympose/workers.py#L217)) so the model pulls context
  only when it decides it needs it — one extra round-trip, but only on relevant
  turns, and it streams.
- **ADR-070.5 — Indexed search tier.** Implement the long-promised `sqlite_fts`
  mode: a stdlib `sqlite3` FTS5 index kept in the workspace, updated incrementally
  on `write_note` / `append_note` and rebuilt on mtime drift. No new dependency,
  BM25 ranking included. `direct` remains the zero-state fallback.

## Consequences

**Positive** (anticipated — ADR-070 is not yet implemented)

- Most turns skip the vault walk; TTFT becomes prompt-assembly + network only.
- Repeat queries on an unchanged vault drop from O(vault) to O(1).
- The SLA becomes true for real-sized vaults, not just demo vaults.
- ADR-003's tier promise is finally honoured.

**Negative / costs**

- ADR-070.4 adds a round-trip on turns that genuinely need vault context
  (acceptable: those turns were already paying a multi-hundred-ms walk).
- ADR-070.5 adds an index file to keep coherent; the incremental-update +
  mtime-rebuild guard is the mitigation.
- Trigger tightening (ADR-070.1) risks *under*-retrieving; ADR-070.4 is the
  safety net (model can still ask).

## Implementation Note (2026-09-04)

A same-day follow-up conversation surfaced Sympose's actual founding
constraint more sharply than this ADR did when it was written: damiro built
Sympose to be a *cheap, low-round-trip* companion, not a maximally-robust one.
That reframes 070.2 and 070.4:

- **070.1 (explicit-intent trigger gate)** — implemented. `vault.search_triggers`
  narrowed from 27 bare stop-words to ~19 actual retrieval-intent phrases, in
  both `config.yaml` and the code-level default in
  `VaultManager.resolve_turn_context` (which governs any workspace lacking that
  config key — most fresh installs).
- **070.2 (bounded concurrent pre-fetch budget)** — **rejected**, not deferred.
  It was scoped as a mitigation for a heavier fetch; with 070.1 + 070.3 the
  fetch is fast enough on the common path that the added concurrency
  complexity isn't earning its cost.
- **070.3 (mtime cache on vault walks)** — implemented. `_get_vault_snapshot()`
  in `vault.py`, mirroring `_BACKLINK_CACHE`'s invalidation strategy; both
  `search_structured()` and `get_folder_digest()` read it instead of re-walking
  the vault on every call.
- **070.4 (retrieval as a callable tool)** — **rejected**, not deferred. It adds
  a round-trip on every turn that touches the vault. That's a direct cost
  against the round-trip-frugal north star and is no longer the recommended
  direction; 070.1 + 070.3 get most of the latency win without it.
- **070.5 (sqlite_fts indexed tier)** — implemented 2026-09-05 in
  `sympose/vault_index.py`, exactly as scoped: a stdlib `sqlite3` FTS5 index,
  no new dependency, BM25 ranking. One index file per master vault, stored
  under the *workspace* (`.vault_index/`, gitignored) — deliberately never
  inside the user's actual Obsidian vault folder, which the original wording
  didn't specify but the sovereignty axiom implies. Freshness is two-layered:
  `write_note`/`append_note` call an exact single-row upsert immediately (a
  note Sympose just wrote is searchable on the very next query, no mtime
  dependency), and a full rebuild runs whenever the tracked directory-mtime
  watermark drifts (catches edits made outside Sympose). `direct` stays the
  default; `sqlite_fts` is opt-in via `vault.search_mode` and degrades to
  "index unusable, fall back to `direct`" with no visible error if this
  Python's `sqlite3` wasn't built with FTS5. See the
  [Tier 5 implementation journal](./2026-09-05_backend-hardening-tier5-sqlite-fts.md).

Implemented in commit `2af7705` on `chore/backend-architecture-review-and-fixes`.
Verified via a smoke test (title match, content match + snippet, folder digest
with frontmatter, cache identity-stable across repeat calls, cache invalidates
on a new file) — see the [implementation journal entry](./2026-09-04_backend-hardening-implementation.md).

## Alternatives rejected

- **Keep the pre-fetch, just widen the ignore list.** Treats the symptom;
  the walk still runs on the hot path for every triggering message.
- **Always retrieve, on a background thread, inject next turn.** Simpler, but
  the context arrives one turn late — wrong for "what does note X say?" asked
  once.
- **Semantic / vector index now.** Rejected for current scope — reintroduces an
  embedding model or vector store, against the zero-infra sovereignty axiom
  (ADR-024). `sqlite_fts` covers the scaling need with stdlib only.
  **Revisit trigger:** FTS ranking proving insufficient for recall on a large,
  prose-heavy vault.
