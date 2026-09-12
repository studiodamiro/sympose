---
title: "ADR-102 — `thumb` Motion Tier: Editor/Vault Entrances Match the Scrollbar (amends ADR-101)"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
---

# ADR-102 — `thumb` Motion Tier: Editor/Vault Entrances Match the Scrollbar (amends ADR-101)

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

ADR-101 gave the wikilink-pill and vault-tree-row entrance animations a
`snappy` (150ms `ease-out`) tier alongside `mode` (350ms `ease-in-out`) for
panel-level reveals. damiro's own read, after seeing both in the running app:
the row/pill entrances should instead carry the exact timing of
`<ScrollThumb>`'s hover-fade (ADR-100, `duration-300 ease-out`) — the
animation he already found convincing — and asked, more broadly, for that
same timing on every appearing/disappearing element in the editor and vault,
explicitly *excluding* Settings and the Agent panel.

That scope needed a decision: the shadcn overlay primitives it touches
(`<DropdownMenuContent>`, `<ContextMenuContent>`, `<HoverCardContent>`) are
shared components rendered in Settings and the Agent panel too — the note
actions menu, the vault row menu, and the wikilink hover-card are just
particular *usages* of them, in editor/vault-only components. The primitives'
own defaults couldn't be changed without also retiming every Settings/Agent
popover, which wasn't asked for and wasn't wanted.

## Decision

**A third tier, `thumb`** — 300ms, reusing `snappy`'s `ease-out` curve
(`ui/src/index.css`):

```css
@utility duration-thumb {
    transition-duration: 300ms;
}
```

No separate `ease-thumb` — the easing is identical to `ease-snappy`, so the
existing token covers it (`duration-thumb ease-snappy`).

**`<ScrollThumb>` itself now reads from this token** rather than its own
literal `duration-300 ease-out` — the fade that motivated the whole tier is
now the same shared definition as everything matching it, not a coincidental
lookalike that could drift on a future edit.

**Applied only at editor/vault call sites**, not inside the shared
primitives, so Settings and the Agent panel are untouched:

- `markdown-panel.tsx` — the wikilink-pill row and each pill (was `snappy`)
- `vault-tree.tsx` — the note and folder row entrance (was `snappy`)
- `note-actions-menu.tsx` — the editor toolbar's `⋯` `<DropdownMenuContent>`
- `vault-row-menu.tsx` — the vault row's `<DropdownMenuContent>` and
  `<ContextMenuContent>` (the `⋯` button and right-click menu)
- `wiki-link.tsx` — the wikilink hover-card preview

Each is a `className` override on that specific usage
(`duration-thumb ease-snappy`), not a change to `dropdown-menu.tsx`,
`context-menu.tsx`, or `hover-card.tsx` — `tailwind-merge` (already the
project's `cn()`) resolves the conflict with each component's own
`duration-100` default, so only that call site's instance changes.

## Consequences

- The row/pill entrances, the wikilink preview, and both vault/editor context
  menus now visibly share one timing with the scrollbar fade — the
  consistency damiro was actually asking for.
- Settings and the Agent panel keep the shadcn defaults (`duration-100`)
  unchanged — popovers, dialogs, tooltips, `<select>` elsewhere in the app are
  untouched by this ADR.
- `snappy` (150ms) is now scoped down to small collapse/width toggles only
  (`control-section.tsx`, the vault-tree rename-input reveal in
  `app-shell.tsx`) — it no longer covers "an item entering," which fully
  moved to `thumb`.

## Alternatives rejected

- **Changing `snappy` itself to 300ms** instead of adding a third tier.
  Rejected: `snappy` is still the right timing for the collapse/width
  toggles it covers (control-section accordions, the rename-field reveal) —
  bumping those to 300ms would have slowed down interactions nobody asked to
  slow down, just to reuse a name.
- **Retiming the shared primitives' own defaults** (`dropdown-menu.tsx`,
  `context-menu.tsx`, `hover-card.tsx`, and by extension `popover.tsx`,
  `dialog.tsx`, `tooltip.tsx`, `select.tsx`, `sheet.tsx`). Rejected per
  damiro's explicit instruction: Settings and the Agent panel render several
  of these same primitives and were to stay untouched, which a shared-default
  change couldn't do — the per-usage `className` override was the only way
  to scope this to editor/vault without a prop threaded through every
  consumer.
- **Retiming `confirm()`'s dialog** (`lib/confirm.tsx` /
  `confirm-dialog.tsx`), which vault deletes call. Left alone: it's a single
  globally-mounted dialog invoked from both editor/vault and Settings-style
  flows with no per-call "origin" concept today — giving it a different
  timing for vault callers would mean threading a variant/option through
  every `confirm()` call site, a materially bigger change than a `className`
  swap. Not addressed here; flagged as a gap, not silently skipped.

## Deferred (additive)

- `confirm()`'s dialog timing for vault-originated confirmations (delete
  note/folder) — needs a per-call variant option if ever wanted, not just a
  token.
- The vault-tree inline rename field's width reveal
  (`vault-row-menu.tsx`) and the "new note here" folder-create input
  (`app-shell.tsx`) stay on `snappy`, not `thumb` — they're a width clip, not
  an item entering, so weren't re-evaluated here. Worth a deliberate look if
  they end up feeling inconsistent next to the menus around them.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
