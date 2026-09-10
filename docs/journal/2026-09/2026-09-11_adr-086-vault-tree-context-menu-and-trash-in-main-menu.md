---
title: "ADR-086 — Vault Tree Context Menu & Trash in the Main Menu"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-086 — Vault Tree Context Menu & Trash in the Main Menu

- **Status:** Accepted — implemented 2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Reworks two affordances shipped as follow-ups to ADR-084 / ADR-085: the vault
  tree row actions and the entry point to the trash view.

## Context

**Row actions.** ADR-084's same-day follow-up hung Rename / Delete / New-note
off the vault tree rows via `<VaultRowMenu>`, but right-clicking a row just
force-opened the `⋯` hover button's dropdown — a `Menu` anchored to a fixed,
`opacity-0` element. The menu appeared pinned to the row's right edge, never
where the pointer was, and there was no touch path at all: the parent row owned
a controlled `open` boolean and toggled it from `onContextMenu`.

**Trash.** ADR-085 reached the trash view through an icon-button in the vault
panel header that flipped a local `trashView` boolean. It sat next to the
New-note button, was easy to miss, and was structurally a one-off — the panel
had a hidden mode the main menu knew nothing about.

**Editor parity.** The vendored stylo editor already has its own right-click
menu (`cm-inplace-menu`), compact and squared-off, with a `@media (pointer:
coarse)` variant for touch. Ours looked nothing like it.

## Decision

### 1. Trash is a main-menu row

- New sentinel **`MENU_TRASH_ID`** in `main-menu.tsx`, alongside
  `MENU_SETTINGS_ID` / `MENU_ACCOUNT_ID`, with an `onSelectTrash` prop. It
  renders in the footer cluster **just above Settings**, and — unlike Settings
  and the account rows — stays visible on phone (`hideChrome`), since it has no
  `TopBar` home.
- In the app shell, `trashView` is now **derived** (`active === MENU_TRASH_ID`),
  not a `useState`. `MENU_TRASH_ID` joins the `isSentinel` set so it survives
  `resolvedActive` reconciliation, and `selectSection` clears any half-typed
  new-note name on the way in. The header trash button is gone.

### 2. `+` for New note

The vault panel's New-note affordance uses `Add01Icon` (a bare plus) instead of
`NoteAddIcon`. The context menu's "New note here" row keeps `NoteAddIcon` — it
carries a text label, so the glyph is decoration, not the whole affordance.

### 3. A real vault tree context menu

- **`components/ui/context-menu.tsx`** — a thin wrapper over Base UI's
  `ContextMenu` (`@base-ui/react/context-menu`): native `contextmenu` on a fine
  pointer, a ~450 ms long-press on touch / pen, popup positioned at the contact
  point. `ContextMenuContent` reuses the exported **`menuPopupClass`** from
  `dropdown-menu.tsx` and the existing `DropdownMenuItem` parts verbatim —
  `ContextMenu.Item` *is* `Menu.Item` — so a right-click menu and a button
  dropdown are the same translucent component.
- **`@media (pointer: coarse)`** in `index.css`, keyed off
  `[data-slot="context-menu-content"]`, opens the rows, font size and glyphs up
  for a fingertip, mirroring stylo's own touch treatment. Fine pointers keep the
  compact dropdown metrics.
- **`<VaultRowMenu>` restructured** to wrap the row's interactive line. It takes
  the row `<button>` as `children` and renders the `group/row` flex container as
  the `ContextMenuTrigger`, hosting *both* ways in — the `⋯` hover dropdown and
  the context menu — off **one shared row list** and one copy of the inline
  rename field (keeping the focus fixes from the same day: `modal={false}`,
  deferred entry via `onOpenChangeComplete`, imperative next-frame focus, and a
  blur that only cancels once the field has actually held focus). `vault-tree.tsx`
  loses its `menuOpen` state and `onContextMenu` handler.

### 4. stylo's editor menu, matched

`index.css` extends the existing `[data-slot="markdown-panel"]
.cm-inplace-menu-*` block — radius, padding, row size, a soft drop shadow over a
hairline ring instead of a hard border — so stylo's right-click menu lands on
the same footprint as the Sympose one. Every right-click menu in the app now
reads as one component. `!important` throughout: stylo injects these as a
CodeMirror `EditorView.theme()` stylesheet whose insertion order is not
dependable.

## Consequences

- Right-clicking anywhere on a vault row (or long-pressing on touch) now opens
  the menu at the pointer, as a normal context menu does. The `⋯` button stays
  as the discoverable, hover-visible affordance.
- Every tree row mounts a `ContextMenu.Root` **and** a `DropdownMenu.Root`.
  Both are context providers with no portal until opened, so the cost is small;
  the persona-scoped tree is not large. Not worth optimising now.
- The touch path depends on Base UI suppressing the click that trails a
  long-press, so a long-press does not also select the note / toggle the
  folder. If a device slips through, the row's `onClick` would still fire —
  acceptable (it just navigates), and revisit if it shows up.
- Trash is now discoverable from the primary navigation on every breakpoint,
  and the vault panel no longer carries a hidden mode of its own.
- stylo overrides are `!important` and pinned to stylo's current class names
  (`cm-inplace-menu-panel` / `-item` / `-sep`); a stylo release that renames
  them silently drops the match. Low risk, and the menu stays usable on
  stylo's own defaults if it happens.

## Alternatives rejected

- **Keep the anchored-dropdown trick.** No code to write, but it can never open
  at the pointer and has no touch story. The whole point of "design the
  right-click menu properly" was to make it behave like a real one.
- **Hand-roll long-press detection.** Base UI's `ContextMenu` already does it,
  tuned the same way stylo's `attachLongPress` is (≈450 ms, generous slop,
  ignore mouse). No reason to carry our own timer.
- **A compact, flat menu matching stylo's default look.** Considered first.
  Rejected: damiro chose the Sympose translucent style for *every* right-click
  menu, so stylo's editor menu is restyled toward Sympose, not the reverse.
- **Trash as the last row of the folder list** ("with the folders, last").
  Rejected in favour of the footer, above Settings, so it groups with the
  navigation destinations and holds its position as the folder list scrolls.
- **Restyle the shared `dropdown-menu` primitive globally.** Would drag the
  agent picker and every other dropdown along with it. The context menu already
  reuses the same shell (`menuPopupClass` + the item parts), so there is
  nothing to gain.
- **Two independent `VaultRowMenu` instances, one per trigger.** Each would
  keep its own `renaming` state — picking Rename in one would not surface the
  inline field the other renders. One component owning both triggers is the
  only way the state stays single.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
