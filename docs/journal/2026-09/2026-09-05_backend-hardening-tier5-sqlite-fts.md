---
entry: 2026-09-05
created: 2026-09-05 00:30
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - adr
  - performance
---

# Sympose Engineering Log: `sqlite_fts` Indexed Vault Search (F3 / ADR-070.5)

> **Date:** Friday, September 5, 2026
> **Topic:** Implementing the one item left over from the 2026-09-04 backend
> review after PR #1 merged — the long-promised `sqlite_fts` search tier
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Implemented, tested, and verified end-to-end. This closes out
> every finding from the original 20-finding backend review.

---

## 1. Context

[PR #1](https://github.com/studiodamiro/sympose/pull/1) — the full backend
hardening pass covering Tiers 1 through 4 — merged into `main`. The only item
left from the original review was **F3**: `.env.example` and
[ADR-003](../2026-08/2026-08-24_adr-003-pluggable-multi-tier-vault-search.md)
advertised `direct | sqlite_fts | semantic` search modes, but only `direct`
(a full Python walk) was ever built. `direct` is fine at personal-vault
scale — the mtime-cached snapshot from Tier 2 already keeps repeat queries
cheap — but it's a linear scan with no ranking, and both docs promising
`sqlite_fts` while shipping nothing was itself a small honesty gap worth
closing.

## 2. What shipped

**New module `sympose/vault_index.py`** (~200 LOC) — a stdlib `sqlite3` FTS5
index, no new dependency:

- **One index file per master vault**, stored under the *workspace* at
  `.vault_index/<sha1(vault_path)>.sqlite3` — deliberately gitignored and
  deliberately never written inside the user's actual Obsidian vault folder.
  ADR-070.5's original wording didn't specify where the index should live;
  putting product cache files inside someone's personal vault would have
  been its own small sovereignty violation, so the workspace was the only
  real answer.
- **Two-layer freshness.** `VaultManager.write_note`/`append_note` now call
  `vault_index.upsert_note()` right after a successful disk write — an exact
  single-row insert/replace, so a note Sympose itself just wrote is
  searchable on the very next query with no dependency on filesystem mtime
  timing. Separately, `vault_index.ensure_fresh()` triggers a full rebuild
  whenever the tracked directory-mtime watermark drifts, catching edits made
  outside Sympose (Obsidian itself, iCloud/Dropbox sync, `git pull`). Both
  paths reuse the *existing* Tier 2 snapshot cache (`_get_vault_snapshot`) as
  the rebuild's data source rather than re-walking the vault a second way.
- **BM25 ranking**, title-weighted above body, prefix-matched per query
  token — a real improvement over `direct`'s raw substring scan, not just a
  faster version of the same algorithm.
- **Graceful degradation.** If the running Python's `sqlite3` wasn't
  compiled with the FTS5 extension, every function in the module returns
  "unusable" rather than raising, and `VaultManager.search_structured` falls
  straight through to `direct` with no visible error to the user.
- **Zero-cost when off.** `direct` remains the default (`vault.search_mode`
  in `config.yaml`, unchanged); none of the new code path — not the upsert
  hook, not the index directory — runs or gets created unless a workspace
  opts in.

**`sympose/vault.py`** wiring: `_workspace_dir()` (derives the workspace from
`config_manager.config_path`, the same value `app.py` already resolves at
boot), `_reindex_note_if_enabled()` (the upsert hook, no-op unless
`sqlite_fts` is active), `_search_fts()` (the new branch in
`search_structured`, falling through to the untouched `direct` path if the
index isn't usable this run).

**Docs**: `.env.example`'s `VAULT_SEARCH_MODE` env var was dead code — never
read anywhere; `vault.search_mode` in `config.yaml` was always the real
switch. Fixed the comment to point at the actual mechanism rather than ship
a second stale doc bug right next to the one this session fixed. Documented
the new mode in `config.yaml` itself and in the
[Latency & Performance Tuning Guide](../../wiki/guides/latency-tuning.md).

## 3. Verification

Two new test files, 24 tests, none throwaway:

- `tests/unit/test_vault_index.py` — the module in isolation (rebuild
  indexing a snapshot, no-match returns `[]` not `None`, directory-scope
  filtering, a second `ensure_fresh()` call skipping rebuild when mtime
  hasn't drifted, upsert-then-immediately-queryable, upsert replacing stale
  content, and a simulated FTS5-unavailable Python build degrading cleanly)
  plus `TestVaultManagerSqliteFtsWiring` — the same behavior end-to-end
  through `VaultManager.write_note`/`append_note`/`search_structured`,
  including an explicit assertion the index directory never appears inside
  the vault fixture itself, and a sanity check that `direct` mode (no config
  override) creates no index at all.
- A from-scratch manual smoke test against a real scratch vault + workspace
  (not just pytest fixtures) before the automated tests were written:
  wrote a note through `VaultManager`, confirmed it was searchable in the
  same process via `sqlite_fts`, confirmed a pre-existing note was picked up
  by the full-rebuild path, and confirmed the index db actually landed under
  the workspace directory, not the vault.
- Confirmed `direct` mode is completely unaffected (no index files created,
  identical search behavior) and confirmed the FTS5-unavailable fallback via
  a monkeypatched `sqlite3.connect` that raises on `CREATE VIRTUAL TABLE`.

`.venv/bin/pytest` — 132/132 (118 prior + 14 new).

## 4. Commits

Two commits on `feat/sqlite-fts-vault-search` (branched off `main` after PR #1
merged; author `damiro <hello.damiro@gmail.com>`, no AI attribution trailer
per the repository's standing hygiene rule):

```
cc4c6e6 feat(vault): sqlite_fts indexed search tier (ADR-070.5, F3)
39567fe feat(vault): wire sqlite_fts into VaultManager, fix dead VAULT_SEARCH_MODE env var
724931c docs: accept ADR-070.5, journal the sqlite_fts implementation
```

## 5. Next Immediate Objective

Every finding from the 2026-09-04 backend architecture review is now decided
and shipped. No open items remain from that review.
