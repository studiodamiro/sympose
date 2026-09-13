---
title: "ADR-108 — Pinned Notes Promoted to a Vault-Wide Group; Recent Management + Toggle"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-explorer
---

# ADR-108 — Pinned Notes Promoted to a Vault-Wide Group; Recent Management + Toggle

- **Status:** Accepted — implemented 2026-09-13. **Supersedes ADR-106's**
  per-folder reorder for Pinned.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-106 deliberately scoped Pinned to a per-folder reorder — damiro's own
choice at the time, over the vault-wide alternative this session had
recommended first. Seeing it live changed his mind: a screenshot of the
`Daily` folder showed the "Recent" group (already vault-wide, ADR-107)
working exactly as intended at the top of the list, while "Pinned" was
nowhere near it — buried four levels deep at `Daily/2019/10-October`,
requiring the same folder navigation pinning was supposed to shortcut.
damiro asked for Pinned "visually outside of the folders," with the note's
path shown since it's no longer contextualized by its surrounding tree — in
effect, adopting ADR-106's original rejected alternative now that the
per-folder version had visibly failed to deliver "easy access." In the same
exchange he also asked for two management gaps in the newer Recent group:
a per-note "remove from recents" and a group-wide "clear recents," plus a
Settings toggle to turn the whole Recent group off.

## Decision

**Pinned becomes a vault-wide group, structurally identical to Recent
(ADR-107).** `usePinnedNotes()` now also returns `pinnedPaths: string[]`
(the full pinned set, not just what's visible in one folder); `AppShell`
resolves each against the *full* `vaultTree` via the same `findNodeByPath`
Recent already used, filters out anything that no longer resolves to a note
(renamed/deleted since), and passes the result as `VaultTree`'s new
`pinnedNodes` prop. The per-folder reorder machinery this replaced —
`sortPinnedFirst`, `countLeadingPinned`, and the nested caption/spacer block
inside `VaultTreeRow`'s folder branch — is deleted outright rather than left
dead; `onUnpinAll` moves from a per-row `RowActions` field to a plain
`VaultTree`-level prop, since "Unpin all" now acts on the vault-wide group,
not a level-scoped one.

**Pinned rows show their path, not just their name.** `VaultTreeRow` gained
a `showPath?: boolean` prop — when set, the row's label is the note's full
vault-relative path (`node.path`) run through the same `hideExtension`
handling as the bare-filename case, rather than `node.name`. Set only for
rows rendered inside the vault-wide Pinned group (Recent keeps its existing
bare-name look — damiro's complaint was about Pinned specifically, and
Recent's own screenshot read fine as-is). Deliberately the simplest fix
available: swap what text renders in the existing single-line row rather
than restructuring it into two lines, avoiding any layout risk to the many
other places this same row renders.

**Recent gets the same two management actions Pinned already had.**
`use-recent-notes.ts` gained `removeFromRecents(path)` and `clearRecents()`,
mirroring `usePinnedNotes()`'s per-item toggle and `unpinMany` batch-clear.
`RecentSectionCaption` grew a `menuItems` slot (like `PinnedSectionCaption`,
both now thin wrappers over the shared `GroupCaption`) offering "Clear
recents" through the same hover-`⋯`/right-click pattern. Each recent row
gets an `onRemoveFromRecents` callback threaded through a new
`VaultRowMenu` prop of the same name, rendering a "Remove from recents" item
(`Cancel01Icon`) in the note menu whenever set — `undefined` everywhere else,
so no other row is affected.

**Recent gets a Settings on/off toggle.** `useRecentNotes()` gained
`enabled` / `setEnabled`, cookie-backed (`sympose:vault.recents_enabled`,
default on) and independent of the stored history — turning it off returns
an empty `recentPaths` without discarding what's tracked, so switching back
on immediately has something to show rather than starting cold. Wired into
`RecentNotesPreferencesSection` as a new top row, with the existing "Notes
shown" segmented control now only rendered while enabled.

## Consequences

- Both quick-access groups now behave identically end to end: vault-wide
  resolution, a group caption with a batch action, and a per-row way to
  leave the group — the only remaining difference is Pinned's path label vs.
  Recent's bare name.
- The nested per-folder Pinned caption/spacer/reorder code from ADR-106 is
  gone; a pinned note inside an expanded folder is now a completely ordinary
  row (still badge-marked via `isPinned`/`pinned`), no longer reordered
  in place.
- No new backend surface, no new round-trips — every addition here is
  cookie state and client-side tree lookups, consistent with the
  round-trip-frugality mandate.

## Alternatives rejected

- **Keep Pinned's per-folder reorder and add a *second*, separate vault-wide
  "Pinned (all)" surface elsewhere.** Rejected as needless duplication —
  once the vault-wide version exists and does what was actually wanted, the
  per-folder reorder has no remaining reason to exist alongside it.
- **Two-line pinned rows (name on top, folder path as a smaller caption
  underneath), matching `VaultContentSearch`'s snippet-row layout.**
  Considered for a cleaner visual hierarchy, but rejected for now — it would
  have meant restructuring `VaultTreeRow`'s shared button markup (used by
  every row in the tree, not just Pinned), for a case that a plain path swap
  already resolves at far lower risk.
- **A single global "Clear recents" without a per-row "remove one" — or vice
  versa.** Rejected; damiro asked for both explicitly, and they serve
  different moments (pruning one bad entry vs. resetting the whole list).

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- `.venv/bin/pytest` — 398 passed (backend untouched by this change).

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
