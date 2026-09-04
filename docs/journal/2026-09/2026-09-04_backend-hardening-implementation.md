---
entry: 2026-09-04
created: 2026-09-04 23:04
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - adr
---

# Sympose Engineering Log: Backend Hardening Implementation (Tiers 1–3)

> **Date:** Thursday, September 4, 2026
> **Topic:** Implementing the findings from the same-day backend review — defect
> fixes, latency caching, and engine/MCP concurrency hardening
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Tiers 1–3 implemented, tested, and committed. Tier 4 (F5, F13,
> F14-full) still open, blocked on decisions only damiro can make.

---

## 1. Executive Summary

Same-day follow-up to the
[Backend Architecture & Objective-Effectiveness Review](./2026-09-04_backend-architecture-effectiveness-review.md).
That review's 20 findings were regrouped by implementation ease and dependency
and worked through in three tiers, plus a separate fix to a real product-scope
gap found along the way: **Grace and Anaïs were git-tracked**, so a fresh
`git clone` silently loaded them alongside Samantha, contradicting ADR-046's
already-decided "Samantha-only clean slate."

A mid-session conversation about round-trip cost as Sympose's actual founding
constraint (cheap, low-latency, direct dialogue with an Obsidian vault — not a
maximally-robust agent framework) **reframed two of the review's own
recommendations before they were built**: ADR-071's original preference for
full function-calling migration and ADR-070's retrieval-as-a-tool option were
both dropped in favor of the round-trip-frugal path. Both ADRs were updated in
place to record that reframing rather than silently building the original plan.

---

## 2. What shipped

### Repository hygiene
- **Untracked `profiles/grace.yaml`, `grace_soul.md`, `anais.yaml`,
  `anais_soul.md`**, plus leftover `profiles/_archived/aurelius/*` and
  `.../ranking/*` committed before `profiles/_archived/` was gitignored.
  `.gitignore` generalized: only `samantha.yaml` / `samantha_soul.md` can ever
  be tracked under `profiles/` again. Files stay on disk — this is damiro's
  personal local customization, not product content (ADR-046).
- Restored `.agents/rules/` (missing from this workspace, present in sibling
  repos) and re-synced `CLAUDE.md`'s summaries against it.

### Tier 1 — defects & small hardening (no dependencies)
- **F16/F17**: `ModelCatalog.get_cached_models()` referenced an undefined
  `STATIC_CATALOG` → `AttributeError` fully offline with no cache file. Falls
  back to `DEFAULT_RECOMMENDATIONS`; its schema fixed (`context` →
  `context_length`) to match what readers actually expect.
- **F15**: `is_safe_path()` now resolves symlinks (`os.path.realpath`) before
  comparing — a symlink inside an allowed vault folder pointing outside it
  previously passed the sandbox check.
- **F6**: deleted the "model forgot the `[DAILY_NOTE:]` tag" fallback that
  scraped the model's prose and wrote it to the vault on a regex guess about
  intent — directly against the ground-truth sovereignty standard (ADR-024).
- **F7**: `execute_actions` takes a `depth` parameter (`MAX_ACTION_DEPTH = 1`),
  capping `SPAWN_WORKER`'s recursive re-parse of worker output.
- **F12**: MCP subprocess `stderr` is now drained on a daemon thread — was
  never read, risking a pipe-buffer deadlock on a chatty server.
- **F14 (interim)**: dashboard defaults to `127.0.0.1`;
  `SYMPOSE_DASHBOARD_HOST` env var opts into LAN exposure explicitly. The full
  auth pass (ADR-064) is still not built.
- **F1 (partial)**: `vault.search_triggers` narrowed from 27 bare stop-words
  to ~19 actual retrieval-intent phrases, in both `config.yaml` and the
  code-level fallback that governs any workspace lacking that config key.

### Tier 2 — vault & prompt-assembly caching
- **F2**: new `VaultManager._get_vault_snapshot()` — an mtime-cached flat
  listing of every note, mirroring `_BACKLINK_CACHE`'s invalidation strategy.
  `search_structured()` and `get_folder_digest()` both read it instead of
  re-walking + re-reading the whole vault on every call.
- **F4**: `ProfileManager._read_file_safe()` mtime-caches per resolved path, so
  `build_system_prompt`'s ~6 file reads per turn (soul, user card,
  shared/persona memory, workspace rules) skip disk on unchanged files.
- Verified with a throwaway smoke test against a temp vault (title match,
  content match + snippet, folder digest with frontmatter, cache
  identity-stable across repeat calls, cache invalidates on a new file) — the
  existing suite has zero coverage of either function.

### Tier 3 — engine & MCP concurrency
- **F9**: `VaultManager._last_searches` dropped its shared `"default"`
  fallback key — persona A's search results could previously leak into
  persona B's `/read <n>` if B hadn't searched yet in the same process.
  *Not fully closed*: two Slack threads on the *same* persona still share that
  persona's last-search cursor; full session-scoping is a bigger change,
  flagged rather than silently declared solved.
- **F8**: `PersonaEngine._lock` (`threading.RLock`) guards `histories`,
  `active_vault_ctx`, `active_sessions`, `model_overrides` — one engine is
  shared across every Slack daemon thread. Added `get/set/clear_model_override()`
  so `commands.py`'s `/model` handler stops mutating the dict directly.
  Retrieval and the `litellm.completion` stream stay outside the lock —
  serializing those would freeze every other persona/thread behind one slow chat.
- **F10**: replaced unbounded `threading.Thread(...).start()` in memory
  extraction, session titling, and compaction with a shared
  `compactor.run_hygiene_task()` — a semaphore-gated pool of daemon threads,
  deliberately **not** `concurrent.futures.ThreadPoolExecutor` (its worker
  threads are non-daemon by design and would make CLI `quit` block on any
  in-flight background LLM call). Compaction is single-flight per file via an
  in-flight-path set.
- **F11**: rewrote `MCPClient`'s request/response cycle. The old code held one
  lock across write+poll+read and kept only the stdout line whose id matched
  the request it was polling for — any other message (a response to a
  *different* in-flight request, arriving out of order) was silently
  discarded, leaving that request to hang until its own timeout. Replaced with
  one background reader thread per connection resolving a `{id: Future}` map;
  concurrent requests no longer block each other and out-of-order responses
  route to the correct caller. Amends [ADR-065](../2026-08/2026-08-30_adr-065-mcp-client-threading-logging-standard.md)
  (its original decision stands; this is a correctness fix within it, not a
  reversal, so it wasn't given a new ADR number).
- Verified with three throwaway smoke tests, none of which the existing suite
  covers: 12 threads hammering engine state for 2s (no deadlock, no
  exceptions); MCP client replying to two concurrent requests **in reverse
  order** (each caller got its own correct response) plus a timeout case and a
  process-exit case; 20 concurrent compaction triggers on one file resolving
  to exactly 1 real compaction run.

`.venv/bin/pytest` — 101/101 passed after every tier and again on the final
committed tree.

---

## 3. A mistake made and caught mid-commit

Splitting the work into atomic commits, the first attempt at the
"untrack personas" commit used `git commit -- .gitignore profiles/`. That
reads the **working tree**, not the index, for the given paths — and since
`git rm --cached` leaves the file on disk, it silently re-staged and
re-committed the personas as still-tracked, with the diffstat only showing the
`.gitignore` change. Caught by checking `git show --stat` against what was
expected rather than trusting the commit's success message; fixed by redoing
`git rm --cached` and `git commit --amend`, then verifying with `git ls-files`
(no longer tracked) and `ls` (still on disk).

---

## 4. Decisions revised mid-implementation (not silently built as originally scoped)

- **ADR-070.2** (bounded concurrent pre-fetch budget) and **ADR-070.4**
  (retrieval-as-a-tool) — rejected, not deferred. Both add a round-trip or
  complexity the round-trip-frugal north star argues against; 070.1 (trigger
  discipline) + 070.3 (mtime cache) get most of the latency win without them.
- **ADR-071**'s A/B choice on action dispatch — neither was decided. A
  same-day conversation surfaced a third framing (fire-and-forget vs.
  answer-gating actions — the former can get schema validation via a
  same-completion tool call, at zero added round-trips, which neither original
  option captured) as the live candidate. Recorded in ADR-071's Implementation
  Note; the dispatch mechanism itself is unchanged pending that decision.
- **ADR-072.3**'s literal `ThreadPoolExecutor` wording — implemented instead as
  a semaphore-gated daemon-thread pool, because `ThreadPoolExecutor`'s
  non-daemon worker threads would make CLI `quit` block on in-flight
  background work. Same bounded-concurrency guarantee, no behavior regression
  on exit.

---

## 5. Commits

Ten commits on `chore/backend-architecture-review-and-fixes` (branched off
`main`; author `damiro <hello.damiro@gmail.com>`, no AI attribution trailer
per the repository's standing hygiene rule):

```
82d9a99 docs: backend architecture & objective-effectiveness review + ADR-070-073
65f3094 chore: untrack Grace/Anais personas and archived cruft - Samantha-only ships (ADR-046)
826dc67 fix(models): guard undefined STATIC_CATALOG fallback, fix context_length schema
a558647 fix(config): resolve symlinks in is_safe_path before comparing
c8b0e7f fix(actions): remove intent-guess DAILY_NOTE fallback, cap SPAWN_WORKER recursion
86aca37 fix(server): default dashboard to localhost, add SYMPOSE_DASHBOARD_HOST opt-in
2af7705 perf(vault): narrow search triggers, cache vault snapshot, fix cross-persona search leak
8106191 perf(profiles): cache system-prompt file reads (mtime-keyed)
9dc12a3 fix(engine): lock shared session/model-override state; bound background hygiene; single-flight compaction
0766ebf fix(mcp): replace per-request stdout polling with a future-mapped reader thread
```

---

## 6. Next Immediate Objective

Land the PR. Then decide the three items Tier 4 is blocked on:

- **F5 / ADR-071** — the fire-and-forget vs. answer-gating dispatch split.
- **F13 / ADR-073** — worker native-shell allowlist (A) vs. off-by-default flag (B).
- **F14 full / ADR-064** — password guard + self-signed TLS for the dashboard.

F3 (`sqlite_fts` indexed search tier) is unblocked but sizable — slot in
whenever there's a larger block of time.
