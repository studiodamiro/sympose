---
title: "ADR-109 — Pinned Notes Scoped to Root Folder, Not Vault-Wide"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-explorer
---

# ADR-109 — Pinned Notes Scoped to Root Folder, Not Vault-Wide

- **Status:** Accepted — implemented 2026-09-13. **Supersedes ADR-108's**
  vault-wide scope for Pinned.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-108 made Pinned vault-wide, mirroring Recent, after ADR-106's per-folder
reorder buried pinned notes too deep to be useful. In the same session
damiro refined that once more: Pinned should be scoped per **root folder** —
the top-level menu entry ("Daily", "Code", …) — not the whole vault. A note
pinned somewhere under "Daily" should show while browsing Daily regardless
of how deep it lives, but never mixed in with "Code"'s own pinned notes. He
also asked that a pinned row's full path only be shown when the root folder
it belongs to actually has subfolders in it (his example: Daily's
year/month structure) — a flat root folder's own filenames are already
unambiguous without one.

This lands between ADR-106 (scoped too narrow — the immediate parent
folder) and ADR-108 (scoped too wide — the whole vault): the right unit
turned out to be the root folder, which is also the one boundary the
sandboxed persona/vault-folder model (ADR-002-era) and the main menu rail
already treat as a first-class unit.

## Decision

**`activeNode` already *is* "the current root folder."** The content panel
never changes which top-level menu entry it's showing just because a nested
subfolder inside it gets expanded or collapsed (`AppShell`'s `panelNodes`
model — a top-level folder's own subtree renders as one `VaultTree`
instance with client-side disclosure, `resolvedActive` only moves on an
actual menu pick). So no new tracking was needed: `pinnedNodes` in
`AppShell` now filters `pinnedPaths` to `path.startsWith(activeRootFolder.path + "/")`
before resolving each to its real `VaultNode`, where `activeRootFolder` is
`activeNode` itself when it's a folder (`undefined` — so no Pinned group at
all — for Settings/Trash/Agent or a root-level note, none of which have a
meaningful "root folder" of their own).

**Path label is conditional, not automatic.** `VaultTree` traded its
always-on Pinned `showPath` for a caller-supplied `pinnedShowPath?: boolean`.
`AppShell` computes it as `activeRootFolder.children?.some(n => n.type === "folder")`
— true for "Daily" (year folders as direct children), false for a flat root
folder with only notes directly inside it. `VaultTreeRow`'s own `showPath`
prop and its `node.path`-vs-`node.name` label logic are unchanged; only
which value the caller passes changed.

**"Unpin all" and empty-state gating fall out for free.** Since the caption's
`onUnpinAll` already just unpins whatever paths are in the `pinnedNodes`
prop it was handed, scoping that prop to the root folder automatically
scopes the action too — no separate change needed. Likewise the
`<VaultTree>` render-gate (`searchedPanelNodes.length > 0 || pinnedNodes.length > 0 || recentNodes.length > 0`)
needed no logic change, only correctly-scoped data flowing into the same
check.

## Consequences

- Each root folder now behaves as its own bounded Pinned space — pinning a
  note in "Code" has zero visible effect while browsing "Daily," matching
  the mental model damiro described.
- A pinned note's path label appears only where it earns its keep: shown for
  Daily's nested year/month notes, skipped for a flat folder where the bare
  filename was never ambiguous to begin with.
- `usePinnedNotes()` itself is untouched — it still just tracks a flat,
  vault-wide `Set<string>` of pinned paths; the root-folder scoping is a
  presentation-layer filter in `AppShell`, the same way Recent's own
  vault-wide resolution already worked. Promoting pins to per-root-folder
  storage was never necessary.

## Alternatives rejected

- **Scope by immediate parent folder (ADR-106's original approach).**
  Already tried and explicitly walked back — the whole point of this pass
  was fixing that a pinned note nested several folders deep stayed
  invisible unless you drilled all the way down to its own parent.
- **Always show the full path on every Pinned row, root-folder subfolders or
  not.** Simpler, but damiro specifically asked for the conditional —
  showing a redundant path on a flat root folder's own already-unambiguous
  notes was unwanted noise.
- **Track pins per root folder in separate cookies/storage keyed by root.**
  Rejected — the existing single flat pinned-paths cookie already encodes
  enough information (the path prefix) to derive per-root scoping for free
  at read time; splitting storage would only add migration complexity for
  no behavioral gain.

## Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079).
- `.venv/bin/pytest` — 398 passed (backend untouched by this change).

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
