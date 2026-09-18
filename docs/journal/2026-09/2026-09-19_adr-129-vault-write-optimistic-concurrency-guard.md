---
title: "ADR-129 — Vault-Write Optimistic-Concurrency Guard"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-129 — Vault-Write Optimistic-Concurrency Guard

- **Status:** Implemented.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Investigating the codebase for the Tier 2 ("multiple writers into a shared
vault") work surfaced a real gap: `vault_write.py`'s `write_note`,
`append_note`, and `overwrite_note` have zero conflict detection today —
no mtime/hash precondition, no locking of any kind. Two writers racing on
the same file (two Sympose processes, two threads, or two machines sharing
a vault) silently last-write-wins. `append_note` was additionally the one
non-atomic writer left in the module: a raw `open(target_file, "a")`,
where `write_note`/`overwrite_note`/`create_note` all already go through
`vault_manifest.write_atomic_text`'s tmp-file-then-`os.replace` pattern.

damiro flagged one framing correction on the original plan for this ADR:
it had assumed Obsidian Sync as the relevant cross-machine mechanism —
"this should be knobed, some users may not want it." Not every user pays
for Obsidian Sync; some use Dropbox, Syncthing, git, or a single machine
only. The guard built here is deliberately sync-mechanism-agnostic: it
detects any two writers racing on the same local file, regardless of what
(if anything) moved that file between machines.

## Decision

- **`sympose/vault_write_concurrency.py`** (46 lines) — `NOTE_CONFLICT`
  sentinel (same style as the existing `NOTE_NOT_FOUND`/`NOTE_DENIED`),
  `current_mtime(path)` (`None` if the file doesn't exist), and
  `mtime_matches(path, expected)` (`True` when `expected is None` — the
  no-precondition default — or when the file's current mtime matches).
  A file that no longer exists only "matches" an `expected` of `None`, so
  a caller that thought the file existed correctly sees a conflict rather
  than silently creating a new one.
- **`sympose/vault_write.py`**: `write_note`, `append_note`, and
  `overwrite_note` each gain a keyword-only `expected_mtime: float | None
  = None`. A mismatch returns `NOTE_CONFLICT` before any write happens.
  Default `None` preserves every existing caller's behavior exactly — this
  shipped with zero risk to anything already calling these functions.
- **`append_note`'s raw `open(..., "a")` is gone** — it now reads the
  existing content and writes the concatenated result through the same
  `vault_manifest.write_atomic_text` every other writer uses, closing the
  one non-atomic gap in the module in the same change (the mtime check
  needs a stat-then-write window anyway, so this was the natural point to
  fix it).
- **`sympose/vault.py`**: `NOTE_CONFLICT` re-exported alongside the other
  sentinels; `write_note`/`append_note`/`overwrite_note` thread
  `expected_mtime` through to `vault_write.py`; a new `get_note_mtime(profile,
  note_name)` classmethod resolves the same file `read_note` would open
  and returns its current mtime (or `None`) — the precondition a caller
  round-trips back on a later write.
- **`sympose/config_settings_vault.py`**: new `vault.multi_writer_safety`
  (bool, default `False`) — not read inside `vault_write.py` itself
  (which stays a pure "check the precondition if given" module); it's a
  signal for callers (the dashboard) to decide whether they bother
  reading and passing `expected_mtime` at all. Off by default, a
  single-writer user's requests never carry the field and pay zero cost.
  Explicitly documented as sync-mechanism-agnostic — no Obsidian Sync
  assumption baked in, per damiro's correction.
- **`sympose/server.py`**: `GET /api/vault/note` now returns the note's
  `mtime` alongside `path`/`content`. `PUT /api/vault/note`'s `NoteWrite`
  body gains an optional `expected_mtime`; `_translate_vault_result` gains
  a `conflict` parameter mapping `NOTE_CONFLICT` → HTTP 409, alongside the
  existing 404/409(exists)/403 mappings.
- **True cross-machine coordination stays explicitly out of scope.**
  Whatever sync layer a user runs (or doesn't) is responsible for
  reconciling files that changed on two machines before Sympose ever sees
  them; `vault_manifest.py`/`vault_index.py` being per-workspace derived
  caches is fine as-is — each machine just re-derives its own view of
  whatever local disk state it has. A real distributed lock is a future
  ADR if ever actually needed, not this one.
- 22 new unit tests: `tests/unit/test_vault_write_concurrency.py` (the
  pure helpers), a new `TestOptimisticConcurrencyGuard` class in
  `tests/unit/test_vault_write.py` (all three writers' conflict/success
  paths, plus a dedicated regression test that `append_note` now survives
  an `os.replace` failure without corrupting the file — the exact
  guarantee its old raw-`open` mode never had), and two new `test_server.py`
  cases (409 on `NOTE_CONFLICT`, `mtime` present on read).

## Consequences

**Positive**

- Closes a real, previously-undetected silent-clobber gap for every
  existing single-process caller too, not just future multi-writer
  scenarios — `append_note` is now crash-safe the same way its siblings
  already were.
- Fully opt-in and backward-compatible: nothing currently sets
  `expected_mtime`, so today's behavior (including every passing test
  before this ADR) is unchanged; the dashboard editor wiring up the
  round-trip (read `mtime` → send it back on save) is a follow-on UI
  change, not required by this ADR to be safe to ship.
- Framing corrected before shipping rather than after: the guard makes no
  claim about *which* sync mechanism (if any) a user runs, addressing
  damiro's flagged concern directly in both the code comment and the
  `Setting` description a user will actually read in `/config`.

**Negative / costs**

- Still no protection against a conflict Sympose never gets a chance to
  see — e.g. two machines both writing while briefly offline from each
  other, then syncing later. That remains genuinely out of scope (see
  Decision); this ADR only guards writes Sympose itself performs against
  each other.
- The dashboard's actual save flow doesn't yet send `expected_mtime` —
  the mechanism is live and tested, but a user won't see a 409 in practice
  until the editor UI is wired to round-trip the value from its last read.
  Tracked as follow-on work, not blocking this ADR.

## Alternatives rejected

- **`fcntl`/file-based cross-process locking.** Rejected — this is
  meaningfully more infrastructure (lock files, staleness/cleanup
  semantics, platform differences) for a guarantee this ADR doesn't
  promise (true mutual exclusion across processes), and would count as a
  new mechanism needing its own ADR under the no-new-background-services
  rule. An optimistic check costs nothing when unused and catches the
  overwhelmingly common case (two writes far enough apart to race) without
  any of that machinery.
- **Hash/content-diff preconditions instead of mtime.** Rejected — mtime
  is what `vault_manifest.py`'s own freshness-watermark logic already
  standardizes on elsewhere in this codebase, so this stays consistent
  with an existing convention and is far cheaper to compute than hashing
  file contents on every read and write.
- **Reading `vault.multi_writer_safety` inside `vault_write.py` itself
  to decide whether to enforce the check.** Rejected — that would make a
  supposedly pure "check the precondition if one was given" module reach
  into global config, and would mean a caller's explicit `expected_mtime`
  could be silently ignored based on an unrelated setting. Keeping the
  setting purely as a signal for *callers* to decide whether to pass the
  field at all is simpler and keeps `vault_write.py`'s functions honest
  about what they were actually asked to do.
