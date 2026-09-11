---
title: "ADR-092 — Vault & Editor UX Batch: Pin/Unpin Notes, Hidden File Extensions, ContentPanel Footer Slot"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-explorer
  - settings
---

# ADR-092 — Vault & Editor UX Batch: Pin/Unpin Notes, Hidden File Extensions, ContentPanel Footer Slot

- **Status:** Accepted — implemented 2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

> **Note on authorship:** like ADR-091, this entry documents already-built,
> uncommitted work found during a later tidy-up pass. Decision/Consequences
> are read off the diff and its own code comments; Alternatives rejected is
> this pass's reconstruction, not a transcript of the original call.

## Context

Three small, independent vault/editor UX gaps got closed in the same pass:

1. **No way to pin a note.** The vault-row context menu and the editor
   toolbar's `⋯` menu had Rename/Delete (ADR-084) but nothing to mark a note
   as a favorite ahead of an eventual Pinned/Recent surface.
2. **Note labels always carried `.md`.** The vault tree and main menu showed
   the raw filename verbatim; Obsidian (the vault format this product reads)
   hides the extension by convention, and the editor's existing "File
   extensions" preference row (`hideExtension` in `EditorPreferences`) wasn't
   actually wired to anything yet — it existed as a knob description without
   an effect.
3. **The Settings footer was a one-off hack.** The Slack-status/theme row
   pinned to the bottom of the Settings page was built with negative margins
   canceling the scroll surface's own padding (`-mx-8 -mb-8`, phone's
   `-mx-4 -mb-6`) directly on the Settings JSX fragment — a pattern that only
   works because Settings happens to be the one page needing it, and that
   silently breaks if the surrounding padding ever changes.

## Decision

**Pin/unpin (local-only prep).** `use-pinned-notes.ts` adds `usePinnedNotes()`
— a `Set<string>` of vault-relative paths, persisted as a comma-joined
`sympose:vault.pinned` cookie, exposing `isPinned(path)` / `togglePin(path)`.
Deliberately local-only: no vault write, no frontmatter field, no round-trip —
"pinning something costs nothing more than a few bytes in a cookie," per the
hook's own doc comment. Wired into both surfaces that can act on a note:

- `VaultRowMenu` / `VaultTree` — a `pinned` flag and `onTogglePin` prop thread
  down to each row; the row shows a small pin glyph when pinned, and a
  Pin/Unpin item is prepended to its `⋯` menu whenever `onTogglePin` is
  supplied (independent of the rest of the menu's `persona`/API wiring, since
  toggling a pin needs neither).
- `NoteActionsMenu` (the editor toolbar's `⋯` menu) / `MarkdownPanel` — the
  same `pinned` / `onTogglePin` pair, so the open note can be pinned from the
  editor without going back to the tree.
- `AppShell` holds the one `usePinnedNotes()` instance and threads
  `isPinned`/`togglePin` to both.

**Hidden file extensions.** `VaultTree` gains a `hideExtension` prop; when set,
row labels run through a new `stripMdExtension()` helper (`lib/utils.ts`,
case-insensitive trailing-`.md` strip, other filenames pass through
unchanged) instead of showing the raw name. `AppShell` wires this from the
existing `editorPrefs.hideExtension` cookie value to both `VaultTree` and the
main-menu's own `menuItems` labels, so the vault tree and the menu rail's note
rows agree.

**`ContentPanel` footer slot.** A new optional `footer?: React.ReactNode`
prop. When present, `ContentPanel` switches to `flex flex-col`: the scroll
surface becomes a `flex-1 min-h-0` sibling instead of the only child, and
`footer` renders below it as a `shrink-0` bordered strip — pinned below the
scroll the same way `<MarkdownPanel>`'s own "Links" row stays put under the
note body, rather than the ad-hoc negative-margin trick the Settings page
used before. `AppShell` now passes the Slack-status/theme row as
`footer={...}` instead of appending it inside the Settings JSX itself; the
corner-rounding logic (`rounded-br-lg` / `rounded-bl-lg`) shifts to whichever
of the scroll surface or the footer is actually the bottom edge.

## Consequences

- Pinning is instant and free (a cookie write, no network) but not yet
  durable across devices or visible anywhere but the row glyph — there is no
  Pinned/Recent list yet. Promoting it to a real frontmatter-backed,
  cross-device pin is an explicitly deferred later call (the hook's own
  comment flags this).
- `hideExtension` now actually does something; previously-set cookie values
  from before this change take effect immediately, no migration needed.
- Any future page that wants a pinned-bottom row (not just Settings) gets it
  for free via `ContentPanel`'s `footer` prop instead of reinventing the
  negative-margin trick.

## Alternatives rejected

- **Persist pins as vault frontmatter (`pinned: true`) instead of a cookie.**
  Durable and cross-device, but a real vault write for what's explicitly
  prep work ahead of the actual Pinned/Recent feature — premature cost for a
  glyph with no consuming UI yet.
- **A dedicated `<PanelFooter>` wrapper component instead of a `ContentPanel`
  prop.** Slightly more explicit call site, but `ContentPanel` already owns
  the scroll surface and its corner-rounding logic; splitting the footer into
  a sibling component outside `ContentPanel` would need to duplicate that
  rounding logic rather than adjust it in one place.
- **Hide extensions by default with no toggle**, since Obsidian does. Rejected
  because the preference already existed as a described-but-unwired Settings
  row before this change — removing the choice would contradict a knob damiro
  had already asked for.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
