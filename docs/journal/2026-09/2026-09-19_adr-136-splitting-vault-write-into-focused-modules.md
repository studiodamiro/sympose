---
title: "ADR-136 — Splitting vault_write.py Into Focused, Under-200-LOC Modules"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-136 — Splitting vault_write.py Into Focused, Under-200-LOC Modules

- **Status:** Implemented. Raised during a `code-review` pass covering the
  ADR-129 concurrency-guard fixes: `sympose/vault_write.py` had grown to
  988 lines (nearly 5x this project's own 200-LOC-per-file ceiling,
  `.agents/rules/execution_guidelines.md`) — flagged as pre-existing debt
  during that review, then addressed on its own once the concurrency work
  landed, per damiro's "resolve it, don't let it sit" preference (echoing
  ADR-125's original framing).
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`vault_write.py` is one of `vault.py`'s satellite modules (ADR-125): pure
filesystem mechanics for every note/folder mutation, called through thin
`VaultManager` wrapper methods. Its content clustered by operation —
create, write/append, overwrite, resolve-existing-note, delete, rename
(with wikilink retargeting), daily/session notes, templates — with almost
no cross-cluster coupling beyond a handful of shared sentinels
(`NOTE_NOT_FOUND`/`NOTE_DENIED`/`NOTE_EXISTS`) and small helpers
(`_workspace_dir`, `resolve_existing_note`). Unlike `vault.py`/`engine.py`
(ADR-125), this is a module of free functions, not a class, so the split
uses plain module imports rather than a mixin-class pattern.

The only caller that references this module by name is `vault.py`, always
as `vault_write.<function>(...)` (module-qualified, never `from
sympose.vault_write import <name>`) — confirmed by grepping every call
site. This meant the split could target zero changes to `vault.py` at all.

## Decision

A thin facade (`vault_write.py` itself) re-exporting from eight new
sibling modules, mirroring config_schema.py's re-export pattern (ADR-126)
rather than ADR-125's mixin-class pattern, since this module has no class
to attach mixins to:

- **`vault_write_status.py`** (17 lines) — `NOTE_NOT_FOUND`/`NOTE_DENIED`/
  `NOTE_EXISTS` sentinels and the `_NOOP_HOOK`/`_NOOP_CALLBACK` defaults.
  Split out first: every other new module imports from here, and this one
  imports from none of them.
- **`vault_write_resolve.py`** (73 lines) — `resolve_existing_note` and its
  three lookup tiers, shared by `overwrite_note`/`rename_note`/
  `delete_note`.
- **`vault_write_core.py`** (143 lines) — the daily-root/workspace-dir
  helpers, Obsidian template resolution, and `overwrite_note`.
- **`vault_write_note.py`** (172 lines) — `write_note`/`_write_note_locked`/
  `append_note` (kept together since `append_note` calls
  `_write_note_locked` directly to avoid acquiring `get_file_lock` twice on
  one thread — see the same-day concurrency-guard fixes).
- **`vault_write_create.py`** (125 lines) — `create_note`/`create_folder`.
- **`vault_write_delete.py`** (176 lines) — folder-trash helpers,
  `delete_folder`, `delete_note`.
- **`vault_write_rename.py`** (248 lines) — wikilink retargeting and
  `rename_note`. The one module that didn't clear 200 lines — see
  Consequences.
- **`vault_write_daily.py`** (139 lines) — `sync_frontmatter_tags`,
  `write_daily_note`, `write_session_note`.
- **`vault_write.py`** (60 lines, from 988) — imports and re-exports every
  public name unchanged, so `vault.py`'s `vault_write.write_note(...)`-style
  calls need no changes.

Import layering has no cycles: `status`/`resolve` depend on nothing new;
`core` depends on `status`+`resolve`; `note`/`create`/`delete`/`rename`
depend on `status`+`resolve`+`core`; `daily` depends on `note` (for
`append_note`); the facade depends on everything.

## Consequences

**Positive**

- `vault_write.py` dropped from 988 to 60 lines; seven of the eight new
  modules cleared the 200-LOC ceiling.
- Zero external API change — `vault.py` (the only caller) needed no edits;
  confirmed by the full test suite passing unchanged (1169 tests, up from
  1166 pre-split with new concurrency-guard tests already landed).
- The split surfaced and fixed a real latent bug in transit:
  `write_daily_note`'s `reindex_hook`/`manifest_hook` defaults were
  transcribed as `None` instead of `_NOOP_HOOK` while drafting
  `vault_write_daily.py` — caught by re-reading the new file immediately
  after writing it, before running any test, and fixed before it could
  ship as a `TypeError` waiting for the first caller that omits both hooks.

**Negative / costs**

- `vault_write_rename.py` (248 lines) still exceeds the 200-LOC guidance.
  Rename + wikilink-retargeting is one cohesive feature (`rename_note`
  can't be understood without `rewrite_wikilink_targets`'s retargeting
  rules); fragmenting it further to chase the line count was judged to
  cost more in split-across-files readability than it would gain, the
  same trade-off ADR-125 accepted for `vault_turn_context.py` (475),
  `vault_recall.py` (377), and `engine_grounding.py` (352).
- Total line count across all `vault_write*.py` files grew from 988 to
  1201 — expected and accepted, per-file docstring/import overhead across
  nine files instead of one, the same pattern ADR-125 observed.
- One more file to open when tracing a given operation's full behavior;
  mitigated the same way as ADR-125: `vault_write.py`'s re-exports remain
  the one stable import path `vault.py` already uses.

## Alternatives rejected

- **Leave `vault_write.py` at 988 lines as accepted debt.** Rejected —
  the code-review that surfaced it explicitly flagged it as a standing
  violation of this project's own rule, and the same file was already
  being edited for the concurrency-guard fixes; deferring again would
  repeat ADR-125's original "grows on every touch" complaint.
- **A mixin-class split, matching ADR-125's `vault.py`/`engine.py`
  pattern.** Rejected — `vault_write.py` has no class; its functions take
  explicit parameters (`profile`, `note_name`, hook callbacks) rather than
  closing over `self`/`cls` state, so plain module-level functions with
  explicit imports are the natural fit, matching how `vault_write.py`
  itself was already structured before this split.
- **Fragment `vault_write_rename.py` further to force it under 200
  lines.** Rejected for the reason stated in Consequences — cohesion of
  one genuinely single feature outweighs a mechanical line-count target,
  consistent with ADR-125's own precedent for accepting some satellite
  files over the line.
