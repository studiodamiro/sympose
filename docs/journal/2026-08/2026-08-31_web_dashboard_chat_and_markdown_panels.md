---
entry: 2026-08-31
created: 2026-08-31 06:04
type: daily-log
project: sympose
tags:
  - jour
  - sympose/journal
  - dashboard
  - ui
  - chat-panel
  - markdown-editor
  - app-shell
---

# Sympose Daily Log: 2026-08-31

> **Session Focus:** App-shell stage build-out — the multi-agent chat panel and the markdown editor/reader panel, mocked at `/shell` for design review.
> **Lead Architect:** damiro
> **Engineering Partner:** Claude (Sonnet 5, Claude Code)

---

## 1. Summary

Wireframe-driven mockup session. The `/shell` route previously ended at
`MainMenu + ContentPanel` followed by an empty "stage". This session filled that
stage with two new components, iterating each against hand-drawn wireframes:

1. **`ChatPanel`** (`src/components/sympose/chat-panel.tsx`) — a centred reading
   column for the multi-agent chat: transcript scrolls, composer docks at the
   bottom on the same axis, column caps at a comfortable measure and centres
   itself in whatever width it is given.
2. **`MarkdownPanel`** (`src/components/sympose/markdown-panel.tsx`) — a
   reader-first markdown surface with an editing toolbar, a read-only frontmatter
   header, prose with a real type hierarchy, and an outbound-links footer.

The stage is now a draggable split: `MarkdownPanel │ handle │ ChatPanel`,
defaulting to half each. `ChatMessage` gained a `reaction` slot. Everything is
still a **mock** — toolbar and composer controls are inert, sample content is
hard-coded.

---

## 2. Key Decisions

### 2.1 Chat reading column — centre in the empty space, cap the measure

The chat column is `mx-auto`, capped at `42rem` (the measure the gallery chat
section and `ChatMessage`'s own `74ch` body already use). On a wide stage the
slack falls away evenly on both sides so the column sits dead-centre of the empty
space; on a narrow stage the cap yields and the column runs full width, held off
the edges only by its gutter. Transcript is bottom-anchored (`justify-end`) so a
short conversation hugs the composer.

### 2.2 Contrast dialled down to the panel level

Original chat rendered a near-white user bubble (`bg-primary`) on dark — "painful
in the eyes". Reset to the working-panel palette:

| Element | Before | After |
| :-- | :-- | :-- |
| user bubble fill | `bg-primary` | `bg-panel` (same as `ContentPanel`) |
| user bubble text | `text-primary-foreground` | `text-muted-foreground` |
| persona body text | `text-foreground` | `text-muted-foreground` |
| user bubble corner | all four `rounded-lg` | square top-right, other three `rounded-*-lg` |
| user bubble padding | `px-3 py-2` | `px-4 pt-3`, `pb-7` when a reaction is present |

This is knowingly softer than the design brief's "AAA body copy / no grey-on-grey"
line ([`UI_DESIGN_REFERENCE.md`](../../UI_DESIGN_REFERENCE.md) §2) — flagged for
damiro; kept because it reads calmer and matches the panels.

### 2.3 `[REACT]` badges are line icons, not emoji

`ChatMessage` now takes a `reaction` node; for `role="user"` it is chipped
(`bg-chip`, no border, `h-6 px-1.5`) and floated `-bottom-2.5 left-3` so it
straddles the bubble's bottom-left edge. Reaction glyphs are **Hugeicons line
icons**, not emoji — considered shadcn's set (lucide) and rejected it: the app
standardizes on `@hugeicons/react` everywhere, and one icon system keeps stroke
weight, sizing, and `currentColor` theming consistent. Emoji also render
per-platform and clash with the flat/Swiss aesthetic.
`UI_DESIGN_REFERENCE.md` §7 `[REACT]` row updated from "animated emoji on the
bubble" to the icon-chip description.

### 2.4 Markdown panel — fill, margins, inner inversion

- **Fill:** `bg-panel`, identical to `ContentPanel`, so the editor reads as a
  sibling working panel and pops off the stage. `--panel` is distinct from
  `--background` in both themes; `--card` is not (in light).
- **Inner cards inverted:** the frontmatter block and the link-pills use
  `bg-background` + a hairline border so they lift off the panel fill.
- **Uniform spacing:** the wrapper mirrors `ContentPanel`'s insets (`py-2 pe-2`).
  All four distances are one `space-2` (8px) step — the gap between the two
  panels, the panel's top margin, its bottom margin, and the gap to the chat.
- **Minimum width matches `ContentPanel`:** both are `shellRowWidth / 4`,
  measured off the same viewport-wide shell row (`MarkdownPanel` walks two
  ancestors up and observes it with a `ResizeObserver`, because its own parent's
  width only settles a frame after `ContentPanel` commits — a plain
  `window.resize` listener, which `ContentPanel` can rely on, misses that).

### 2.5 Editor toolbar — first cut

`H1 / H2 · B / I / U / S · bullet + numbered list · code block · blockquote` and
a **save** action. The save button uses a **diskette** (`FloppyDiskIcon`), not a
paper-plane — a note editor *persists to the vault*, which is "save", not "send".
Open question for the next session: if the vault autosaves (Obsidian-style), the
button should become a passive "Saved ✓ / Saving…" status instead.

Reader-mode wikilinks render **de-bracketed in `--brand`** per the wireframe.
This diverges from `WikiLink` / §6.5, which show `[[bracketed]]` links in
`--entity` — i.e. reader mode ≠ source mode. Unresolved; noted for damiro.

Deliberately **out of scope for v1:** heading-level dropdown, tables UI, slash
menu, image paste/embed, raw ↔ preview toggle, grouped-pill toolbar styling
(the wireframe shows segmented button groups; the current bar is a flat row with
thin dividers).

### 2.6 Panel reveal / hide — one slide animation, two triggers

Both working panels now collapse and reveal with the same 300ms transition: a
negative `margin-inline-start` of one panel-width parks the panel off to the
left (clipped by an `overflow-hidden` ancestor), and opening tweens it back to
`0` while `opacity` goes `0 → 1`, so it fades and slides in left→right; hide
reverses it. **Width itself never animates**, so prose never reflows mid-slide.
The transition is suppressed while dragging (`data-dragging:transition-none`).

| Panel | Trigger | Behaviour |
| :-- | :-- | :-- |
| `MarkdownPanel` | the `[WRITE_NOTE]` "Note saved" `ActionBadge` in a chat turn | starts hidden; the badge toggles it. `ActionBadge` gained an `aria-pressed` affordance (brand-tinted border/fill, chevron flips) |
| `ContentPanel` | any `MainMenu` row — folders **plus the Settings and account footer rows** | starts open. `selectSection(id)` in `AppShell`: re-click the active row → toggle; click a different row → switch section and re-open. `activeId` is passed as `undefined` while closed, so no orphaned fused row is left on the menu edge |

`MainMenu` changes: the Settings and account rows are now real `<button>`s with
active-aware styling (`aria-current`, `ROW_ACTIVE` / `ROW_MUTED`); a new
`onSelectAccount` prop; exported `MENU_SETTINGS_ID` / `MENU_ACCOUNT_ID`
sentinels for `activeId` comparison. The menu carries `z-20` in the shell so the
content panel tucks *behind* it on hide rather than sliding over it.

### 2.7 Fused-corner fix for the account row

When the account row (the last footer row, bottom-aligned with the panel) is the
active row, `ContentPanel`'s rounded bottom-left corner left a sliver of
background inside the seam. New `flushBottomLeft` prop squares that one corner
(`rounded-bl-none`); `AppShell` sets it only when the account row is active and
the panel is open. Per-corner radii are set explicitly rather than
`rounded-lg` + an override — the shorthand re-rounds the corner (same caveat
already documented in `main-menu.tsx`).

---

## 3. Files

| File | Change |
| :-- | :-- |
| `ui/src/components/sympose/chat-panel.tsx` | **new** — centred chat reading column + docked composer mock |
| `ui/src/components/sympose/markdown-panel.tsx` | **new** — markdown reader + editing toolbar + frontmatter + links footer; `bg-panel` fill, `ContentPanel`-matched resize bounds; `open` prop drives the slide/fade reveal |
| `ui/src/components/sympose/content-panel.tsx` | `open` prop (slide/fade reveal) + `flushBottomLeft` prop (square the seam corner for the active account row) |
| `ui/src/components/sympose/chat-message.tsx` | `reaction` prop (floated chip, user role); contrast reset to panel palette; square top-right corner; more bottom padding |
| `ui/src/components/sympose/main-menu.tsx` | Settings + account rows are buttons with active styling; `onSelectAccount` prop; `MENU_SETTINGS_ID` / `MENU_ACCOUNT_ID` exports |
| `ui/src/components/sympose/action-badge.tsx` | `aria-pressed` affordance (border/fill + chevron flip) for toggle use |
| `ui/src/components/sympose/index.ts` | export `ChatPanel`, `MarkdownPanel`, `MENU_SETTINGS_ID`, `MENU_ACCOUNT_ID` |
| `ui/src/routes/app-shell.tsx` | stage is `MarkdownPanel │ handle │ ChatPanel`; `panelOpen` / `mdOpen` state + `selectSection`; sample transcript with a reaction + a toggling `WRITE_NOTE` `ActionBadge` |
| `docs/UI_DESIGN_REFERENCE.md` | §7 `[REACT]` row → line-icon reaction chip |

---

## 4. Action Items & Next Steps

- [ ] Decide the save-button question — explicit action vs. passive autosave status.
- [ ] Reconcile reader-mode vs source-mode wikilinks (`--brand` de-bracketed vs `--entity` `[[…]]`).
- [ ] Decide whether MD prose body stays at `text-muted-foreground` or goes higher-contrast for long-form reading.
- [ ] Toolbar: switch the flat divider row to the segmented button-group styling from the wireframe (if wanted).
- [ ] Narrow-viewport behaviour: below ~1180px the three columns crowd the chat. Manual collapse now exists (menu rows toggle `ContentPanel`, the badge toggles `MarkdownPanel`); still want an automatic collapse at that breakpoint.
- [ ] Persist `panelOpen` / `mdOpen` to cookies like the panel widths (currently reset on reload).
- [ ] Wire the panels to real data: `GET /api/vault/note`, `POST /api/vault/note`, `POST /api/chat/message` + SSE stream.
- [ ] Replace inert toolbar / composer controls with a real editor (candidate: a lightweight ProseMirror or CodeMirror markdown mode).
