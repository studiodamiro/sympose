---
entry: 2026-09-17
created: 2026-09-17 18:10
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/vault
  - sympose/ui
  - reliability
  - code-review
---

# Sympose Engineering Log: Code-Audit Tier 2 — Moderate Fixes, Grouped Where the Report Said To

> **Date:** Thursday, September 17, 2026
> **Topic:** Closing Tier 2 of the fact-checked 34-finding code audit
> (see [Tier 1's entry](./2026-09-17_code-audit-tier1-quick-fixes.md) for
> the verification methodology) — the 12 "moderate" findings, fixed in the
> report's own recommended grouping.
> **Status:** 10 of 12 fixed and regression-tested. E7/E8 deferred — both
> explicitly depend on D6 (Tier 3, not yet done), and doing them first would
> route more reads through a cache whose staleness bug isn't fixed yet.

## 1. G1 + G2 together — `vault.ignore_folders` / `vault.search_triggers`

**G1**: `vault.ignore_folders`'s fallback literal was copy-pasted at 9 call
sites across `vault.py`, `vault_links.py`, and `vault_write.py` — 7 of the 9
missing `"Drawings"` relative to the schema default. Since
`ConfigManager.get()` already falls back to the schema default internally
for any key with a non-None default (materialized into `self.data` at load
time), the actual fix is simpler than re-adding another literal: drop the
`or [...]` entirely and call `config_manager.get("vault.ignore_folders")`
bare at all 9 sites.

**G2**: `vault.search_triggers`'s `or [...]` fallback *replaced* the
built-ins instead of extending them, contradicting the setting's own
schema description ("added to the built-ins"). Worse, two independently
hardcoded built-in lists had drifted apart — verification found the real
split is 18 items (`vault.py`, case 7's directory-discovery trigger) vs. 5
(`vault_recall.py`'s `has_recall_intent`), not the "10 vs. 5" the original
report guessed. Merged into one canonical list — `vault_recall._BUILTIN_
SEARCH_TRIGGERS` plus a new `vault_recall.search_triggers()` that unions it
additively with the configured extras — and pointed both call sites at it.

## 2. F1 + F2 together — `use-panels.ts`'s `open()`

Both bugs lived in the same function, confirmed live rather than just by
inspection. **F1**: eviction under a lowered breakpoint cap deleted the
evicted panel from the *persisted* `order`, not just the visible slice —
permanently losing it even after widening back. **F2**: a single shared
timer ref meant a second `open()`/`close()` within `SEQUENCE_MS` (320ms)
of a pending eviction silently cancelled it, dropping the first panel.

Fix: `order` is now reordered but never trimmed (there are only ever 3
possible panels, so it can't grow unbounded) — capping to the breakpoint is
`visibleSlice`'s job alone. A `pendingEvicts` set hides an evicted panel
from `visible` immediately so its slide-out animation still plays, without
touching `order` until the newcomer actually lands. Timers are now keyed
per panel (an object, not one shared ref) so unrelated evictions in flight
at once can't cancel each other.

Verified live (no JS test runner in this project — `ui/`'s primary
commands are typecheck/build only, so this needed the actual app): opened
all three panels at desktop width, narrowed to phone (cap 1 — down to a
single visible panel), then widened back to desktop. Before this fix that
would have permanently lost the two evicted panels; after it, all three
reappeared exactly as they were. Screenshots in this session's scratchpad.

## 3. Standalone fixes

- **C1** (`config.py`) — a bare `performance:` key in `config.yaml` parses
  to `None`, not `{}`; `_deep_merge` clobbered the whole materialized
  defaults subtree with it, crashing `_apply_runtime_settings` at startup
  (`None.get(...)`). Guarded the merge against a `None` override for a
  dict-typed base key. Also: the `10.0` request-timeout literal fallback
  disagreed with the schema's declared `30.0` default — replaced both
  fallbacks (`request_timeout`, `drop_unsupported_params`) with
  `default_for(...)` lookups instead of a second hardcoded copy (ADR-077),
  and made the `perf` lookup itself tolerate a `None` value defensively.
- **C2** (`engine.py`) — persona chat history was mutated (`history.extend`)
  outside `self._lock`, while the very next line's reassignment was inside
  it. `get_history()` hands back the live, shared list object (not a copy),
  so two concurrent turns for the same session could race. Moved the
  mutation inside the existing lock.
- **C7** (`sub_agents.py`) — `_content_unread`'s citation check compared
  bare basenames, so a fabricated citation to `OtherFolder/Foo.md` passed
  as "read" merely because a different `Foo.md` was actually read. Fixed to
  compare trailing path segments instead of the bare filename alone — but
  a naive full-path or fixed-segment-count comparison breaks two existing,
  intentional behaviors: `read_paths` can hold an absolute path against a
  vault-relative citation of the same file, and `VAULT_PATH_TOKEN_RE` itself
  can sweep a few words of leading prose into what it treats as the first
  path segment (its pattern tolerates spaces, to match real folder names
  like "Book Notes"). Landed on a substring check — a read path's own last
  two segments (folder + filename) must appear verbatim in the citation —
  which fixes the cross-folder collision without breaking either existing
  case. Two new regression tests added (a real cross-folder collision, and
  the absolute-vs-relative case) alongside the two the fix could easily
  have silently broken.
- **D4** (`vault_trash.py`) — the "clash suffix" regex
  (`-\d{14}(?=\.md$)`) that reconstructs a trashed note's original path by
  stripping a inferred timestamp suffix false-positived on a legitimately
  timestamp-named file (e.g. a real `Meeting-20240315120000.md`), computing
  the wrong restore target. Replaced inference with an explicit record: a
  `.trash/.trash-index.json` sidecar, written only when `delete_note`
  actually needs to disambiguate a same-path clash (the common case needs
  no entry at all, since a trashed path that never clashed already *is* its
  own original path), consulted by `list_trashed`/`restore`/`purge`, and
  cleaned up on restore/purge so it doesn't accumulate stale rows. Reused
  `compactor.get_or_create_lock` (today's own E9 extraction) for the
  sidecar's write lock. Rewrote the three tests that had encoded the old
  (buggy) regex behavior as their expected outcome, and added an end-to-end
  test that deletes the same path twice through the real `delete_note` and
  confirms the suffixed copy restores to the *true* original, not a guess.
- **E2** (`vault-row-menu.tsx`, `note-actions-menu.tsx`) — the inline-rename
  flow (including the Base UI focus-restoration workaround) and the
  move-to-trash call were duplicated near-identically across both
  components. Extracted `useVaultNoteActions` (`ui/src/lib/`) owning the
  shared state, the focus workaround, `submitRename`, and `runDelete`; each
  component still owns its own menu items, its own rename `<input>`
  styling/positioning, and (for the row menu) folder-specific extras
  (create, delete-folder) the hook was never meant to cover.
- **E4** (`app-shell.tsx`) — `menuItems`/`noteIds`, `panelNodes`/
  `searchedPanelNodes`/`beyondFolderMatches`, and `pinnedNodes`/
  `pinnedShowPath`/`recentNodes` recomputed on every render, including ones
  unrelated to the vault tree. Wrapped each in `useMemo` with its actual
  dependencies, matching `VaultTree`'s own existing pattern for the
  equivalent computation.

## 4. Verification

778 backend tests pass (`.venv/bin/pytest`, up from 775 — two new
`test_sub_agents.py` cases for C7, two rewritten and one new
`test_vault_trash.py` case for D4). `ui/` typecheck and build are clean.
F1/F2 and the E2/E4 UI surfaces were additionally driven live in a real
headless-Chromium session against the dev server (no `chromium-cli` install
in this environment, so a small ad hoc Playwright script did the driving) —
`chromium-cli` availability and a project `run` skill are both worth
setting up before the next UI-behavioral fix needs this again.

## 5. What's next

Tier 3, in the sequence the report specifies: D6 first (the mtime-only
staleness watermark — unblocks E7/E8, deferred from this pass), D1 (atomic
note writes), D2+D3 together (path-keyed manifest/backlink identity
migration), then S1 (the static-asset auth bypass). Tier 4 still needs one
decision — see Tier 1's entry.
