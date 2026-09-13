---
title: "ADR-107 — Recent Notes: A Vault-Wide Group Under Pinned"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-explorer
---

# ADR-107 — Recent Notes: A Vault-Wide Group Under Pinned

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

Immediately following ADR-106 (Pinned notes reorder to the top of their own
folder level), damiro asked for a second group: "Recent" notes, count
knobbed from Settings, placed under Pinned, for jumping back to whatever
note he was just working on.

Unlike Pinned's reorder — deliberately scoped to a folder's own direct
children (ADR-106) — recency has no natural per-folder scope: the note you
were just working on could be anywhere in the vault, and requiring a folder
visit first to surface it would defeat "jump back to it." So Recent is
vault-wide from the start, resolved against the full vault tree regardless of
which folder the panel happens to be showing.

## Decision

**Tracking**: `use-recent-notes.ts` (`usePinnedNotes()`'s sibling, same
local-only convention — ADR-092) keeps an ordered, deduped history of opened
note paths in a `sympose:vault.recents` cookie, capped at 20 stored
regardless of how many are shown. `recordVisit(path)` moves a path to the
front. A second cookie, `sympose:vault.recents_shown`, holds the Settings
knob (3 / 5 / 10, default 5) — kept separate from the stored history so
raising the knob later isn't limited by how many were ever kept before.
`recordVisit` is wired through one `selectNote()` helper in `AppShell`, used
at every genuine "the user opened a note" site (tree row click, wikilink,
search result, note creation) — but deliberately not at the two sites that
just *remap* the already-open note's path after a rename, or clear it after
a delete, since neither is a new visit.

**Resolution**: a recent path alone can't render a row — `VaultTree` only
ever sees the current folder's own nodes. `find-node-by-path.ts` (mirroring
`find-note-by-wikilink.ts`'s depth-first-search shape) resolves each recent
path against the *full* `vaultTree` in `AppShell`; a path that no longer
resolves (renamed or deleted since) or that resolves to a folder is silently
dropped, not shown broken.

**Rendering**: `VaultTree` gained a `recentNodes?: VaultNode[]` prop —
already resolved and capped by the caller, rendered top-level only (never
repeated inside each expanded folder the way Pinned's own reorder is, since
recency isn't a per-folder concept to begin with). Recent rows reuse
`VaultTreeRow` at `depth={0}` — the same rename / delete / pin machinery a
normal row gets, for free, since a recent note is a real vault node, not a
lookup-only stub. They sit outside `useAnimatedNodeList`'s add/remove
tracking entirely: unlike a folder's own children, "falling out of Recent"
isn't a vault event worth an exit animation, and — same lesson as
ADR-106 — that hook's position-preserving behavior would fight the one thing
that actually matters here, a revisited note jumping back to the front on
every reopen.

**Caption generalized.** ADR-106's `PinnedSectionCaption` became `GroupCaption`
— icon, label, and an optional `menuItems` slot for the hover-`⋯`/right-click
treatment — with `PinnedSectionCaption` (keeps "Unpin all") and the new
`RecentSectionCaption` (`Clock01Icon`, "Recent", no menu — nothing to act on
beyond the Settings knob) as thin wrappers over it.

**Layout**: the list is now three plain groups in sequence — pinned rows,
recent rows, the rest — each separated by a 12px spacer only when both
neighboring groups are non-empty, matching ADR-106's own spacing addendum.
`AppShell`'s content panel also had to stop gating `<VaultTree>` behind
"does this folder have anything in it": an empty or zero-search-match folder
used to swap the tree out for a plain message entirely, which would have
hidden Recent (vault-wide, unrelated to the current folder's own contents)
along with it. The folder-empty / no-matches messages still show under the
same conditions as before; `<VaultTree>` now additionally renders whenever
`recentNodes` is non-empty, even if the folder itself has nothing.

## Consequences

- "Jump back to your working note" now actually works from anywhere in the
  vault panel, not just the folder it lives in.
- New Settings → Recent notes section, one knob (3 / 5 / 10 shown).
- Same known limitation Pinned already carries (ADR-092/106): a rename
  leaves a stale path behind in its cookie (pinned or recent) until it ages
  out naturally; not fixed here, not a new regression.
- `GroupCaption` is now the one place any future "N notes, one glance" group
  in this list would plug into.

## Alternatives rejected

- **Scope Recent to the current folder, mirroring Pinned's reorder.**
  Rejected on the same reasoning that shaped the request itself — the whole
  point is finding a note without already knowing (or having navigated to)
  where it lives.
- **A vault-wide flat Pinned section (ADR-106's rejected alternative)
  revisited for Recent.** Recent already *is* vault-wide by necessity —  no
  equivalent "smaller" per-folder option existed to choose over it here.
- **Feeding recent paths through `useAnimatedNodeList` for consistency with
  the rest of the tree.** Rejected — that hook intentionally keeps an
  existing row pinned to its last position, which is exactly wrong for a
  list whose entire value is showing the most-recently-touched note first.

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- `.venv/bin/pytest` — 398 passed (backend untouched by this change).

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
