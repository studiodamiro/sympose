---
entry: 2026-09-10
created: 2026-09-10 00:30
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/ui
  - sympose/dashboard
  - editor
---

# Sympose Engineering Log: Stylo Integration — Vault Wiring, Editor Preferences & UI Polish

> **Date:** Tuesday–Wednesday, September 9–10, 2026
> **Topic:** Wiring `@damiro/stylo` (ADR-080) into `<MarkdownPanel>` as a real,
> live vault editor — real content loading, an editable frontmatter card,
> wikilink navigation, a Settings > Markdown editor preferences section, and
> a multi-round polish pass driven entirely by using the thing against real
> notes.
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Implemented, `npm run typecheck` clean, `.venv/bin/pytest` 309
> passing (no Python touched — verified as part of closing this out), shipped
> in `sympose/webui/`.

---

## 1. What shipped

### Real vault content, read-only

- `ui/src/lib/vault-note-api.ts` — `fetchVaultNote(path, persona)` against
  `GET /api/vault/note`, mirroring the existing `vault-tree-api.ts` pattern.
- `<MarkdownPanel>` fetches on `path`/`persona` change, splits frontmatter
  via stylo's own `splitFrontmatter()`, and feeds only the body to `<Stylo>`.
  `note` state ("empty" / "loading" / "error" / "ready") is derived from
  `path` at render time rather than synced in an effect, matching the
  existing `fetchVaultTree` convention (and avoiding a
  `react-hooks/set-state-in-effect` lint trip along the way).
- `ui/src/lib/extract-wikilinks.ts` — outbound `[[target]]` scan for the
  panel's Links footer, mirroring stylo's own internal pattern (not exported
  by the library); `parseWikilink()` added alongside it for a value that is
  *entirely* a wikilink (frontmatter fields), anchored start-to-end rather
  than scanning running text.
- `ui/src/lib/find-note-by-wikilink.ts` — resolves a clicked `[[target]]` to
  a vault path by filename-stem match, used to open the target note.
- `<AppShell>` wires `onWikiLinkClick` through to `setSelectedNote` +
  `panels.open("editor")`.

### Editable frontmatter card

- `ui/src/lib/frontmatter.ts` — `parseFrontmatter`/`serializeFrontmatter`
  wrapping the `yaml` package. `null` for anything that isn't a flat mapping
  YAML can round-trip cleanly (a bare list, invalid YAML, deep nesting) —
  the card declines to render rather than risk mangling it.
- `ui/src/components/sympose/frontmatter-card.tsx` (new) — array fields as
  removable pills plus an add affordance; scalar fields as click-to-edit
  text; a `[[wikilink]]`-valued field (scalar or inside a pill) renders as a
  clickable, bracket-free link instead of a plain string, wired to the same
  `onWikiLinkClick` the note body uses.
- Stylo's own `---` block render is never used — the card owns frontmatter
  entirely, riding stylo's `toolbar.render` slot so it lands *between* the
  toolbar and the canvas (see §2, toolbar alignment).

### Settings > Markdown editor

- `ui/src/lib/use-editor-preferences.ts` — cookie-backed
  (`sympose:editor.*`) preferences: editing surface (seamless/plain text),
  formatting-mark reveal (near cursor/always hidden), selection UI
  (right-click menu/floating bar), focus outline (hidden/shown). A single
  hook call lives in `<AppShell>` and is threaded down as props to both
  `<EditorPreferencesSection>` and `<MarkdownPanel>` — the established
  pattern from `useActivePersona`, not an independent hook call per
  component (the first cut got this wrong: each component called the hook
  itself, so a Settings change never reached the mounted editor; caught via
  a Playwright screenshot showing the stale in-place rendering after
  toggling "Plain text").
- `ui/src/components/sympose/editor-preferences-section.tsx` (new) — renders
  under the existing `<ControlSection>`/`<ControlRow>` + `<SegmentedControl>`
  kit; no new dependency needed.
- `mode`/`inPlace` are applied-at-mount per stylo's own contract, so the
  `<Stylo>` `key` includes `surface`/`reveal`/`selectionUI` to force a clean
  remount on a preference change.

## 2. The polish pass — what using it surfaced

Every item below came from actually living in the panel against real notes,
not from reading the source. Verified with a scratch Playwright + Chromium
install (no `chromium-cli` in this environment) driving the real dev server
against mocked `GET /api/vault/tree`/`GET /api/vault/note` responses —
screenshotted before calling any of it done.

- **Full panel width.** Dropped the `mx-auto max-w-[68ch]` reading-column cap
  on the editor container; widened stylo's own `.cm-content` gutter
  (`0.75rem` default) to match the established `px-6 sm:px-8` every other
  panel uses, `!important` because `EditorView.theme` compiles to a selector
  this specific already.
- **Toolbar-first layout.** The frontmatter card previously sat *before*
  `<Stylo>`, pushing its toolbar down below the card. Moved the card into
  stylo's `toolbar.render` slot instead — `render: (bar) => <>{bar}<card
  /></>` — so the toolbar is the panel's literal first row, flush and
  visually aligned with the stage's floating new-chat/bookmark action group
  (their alignment was already tuned for this shape; the frontmatter card
  was the thing actually out of place).
- **Frontmatter card visual pass**, in order of what got corrected:
  1. Pill-based array fields (tags, `up`) per the reference mockup, real
     `yaml` parsing rather than a hand-rolled one.
  2. `bg-background` restored after an intermediate no-card version dropped
     it — kept the borderless, full-width shape but brought the shaded
     section back.
  3. `mx-2` side margin — the same thin inter-panel gap `<ContentPanel>` and
     `<MarkdownPanel>` already use between each other — plus a matching
     `mt-2`, so the card reads as its own inset block rather than flush
     top/sides against the toolbar and panel edges. `rounded-lg` follows
     from no longer being flush.
  4. `items-start` → `items-center` on the label/value grid: a plain-text
     value and a pill row (the pill's own `py-0.5` chrome) don't share a
     height, so pinning both to the row's top left the label sitting above
     a pill row's true center by a few pixels every time. Centering both
     against whichever is taller needed no per-row-type padding to
     compensate — caught from the user's own screenshot with reference
     lines drawn across a row.
  5. Content padding reduced to `px-4 sm:px-6` inside that `mx-2` margin, so
     labels land back on the note body's own left edge (the sum of margin +
     padding matches the body's own gutter) rather than reading as
     double-inset.
- **Right-click menu vs. background.** `--stylo-bg: transparent` (a natural
  choice embedding stylo in an existing card) silently made the right-click
  menu, its URL field, the selection bar, and the link-hover tooltip
  unreadable against page content — they share the base surface's
  background token with no separate "floating surface" token. Fixed with a
  real `--stylo-bg` plus a dedicated frosted `--popover`-tinted override for
  the four floating-chrome classes.
- **Selection bar vs. context menu overlap.** With `selectionUI: "bar"` (the
  library's own recommended touch default), right-clicking an active
  selection opened the context menu directly on top of the still-visible
  floating format bar — two floating-chrome systems with no shared "is
  something else open" state. Fixed host-side with
  `.cm-editor:has(.cm-inplace-menu:not([hidden])) .cm-inplace-selbar {
  display: none }`.
- **Fonts.** `.cm-content`'s hard-coded system font stack now bridges to
  `var(--font-sans)` (body) and `var(--font-heading)` (`h1`–`h6`, matching
  every page title in the app) — no `--stylo-font*` token exists to do this
  through the public contract.
- **Text color.** `--stylo-text` was `--panel-foreground` (near-white in
  dark mode) for *everything*, including body prose — every other panel
  (`<ChatMessage>`'s own text) uses `--muted-foreground` for body copy and
  reserves full contrast for headings/labels. Rebalanced: `--stylo-text` to
  `--muted-foreground`, `h1`–`h5` bumped back to `--fg-strong` so they still
  stand out (not `h6` — stylo already gives it its own deliberately-muted
  treatment one step further down).
- **Fenced-code syntax colors.** Never touched until this pass — stylo ships
  its own stock, fully-saturated hex palette (`tokens.css`) with no relation
  to Sympose's OKLCH accents. Rebuilt from the same small set the rest of
  the UI already draws from: `--brand` for keywords/functions/tags, `--ok`
  for strings, the amber `--chip-foreground` already used for inline code
  for literals, `--fg-muted` for comments, plain text for anything not worth
  calling out — only `invalid` keeps `--destructive`.
- **Font size.** `.cm-editor`'s base font-size is set directly by stylo's
  theme (`0.9375rem`, 15px) rather than inherited — a plain element-level
  declaration that never let the panel's own `text-sm` (14px) wrapper
  through. Every in-place heading is sized in `em` off that one value, so
  this wasn't just 1px on body text, it scaled every heading up with it.
  Forced to `0.875rem` (14px).
- **Minimal auto-hide scrollbar.** Generalized from a `.cm-scroller`-only
  rule to a global `* { scrollbar-width: thin; scrollbar-color: transparent
  transparent }` block, so the vault tree, chat transcript, settings, and
  the editor share one scrollbar treatment instead of the editor's custom
  one sitting next to the browser's stock ones everywhere else.
- **Settings/Agent panel width & animation.** Three separate, compounding
  bugs surfaced while widening `<ContentPanel>` for the "use the entire
  width" request:
  1. Toggling `fill` snapped between a fixed pixel `width` and `flex-1`'s
     auto width — two layout modes CSS cannot tween between — so the
     Settings/Agent reveal had no width animation at all, and (with the
     resize handle dropped outright while filled) the panel was simply not
     draggable there.
  2. Redesigned around `size` as the single source of truth for width in
     both states, `fill` only ever seeding or restoring it — real `width`
     transitions the panel exactly like any other resize, and the handle is
     never dropped.
  3. Dragging while filled shared `storageKey` with the vault view's own
     persisted width, so resizing Settings silently overwrote the vault
     view's remembered width the next time it was opened. Gave `fill` its
     own cookie (`${storageKey}.fill`).
  4. Reconsidered the *default* itself after using it: full-stage-width on
     first entry read as more disruptive than useful for a toggle-row
     settings page — changed the un-dragged default to the same one-third
     of the stage the vault view itself defaults to, leaving the ceiling
     lifted to full stage width for anyone who drags it there on purpose.
     Full width remains correct on the phone shell, which this prop plays
     no part in at all.
  - Separately, `<ContentPanel>`'s hide transition used `ease-out` while
    `<MarkdownPanel>` and the chat slot both use `ease-in-out` — the same
    curve run in reverse read asymmetric next to the other two panels
    closing alongside it. Matched to `ease-in-out`.
- **Editor not filling freed space.** On desktop, the chat slot's `max-width`
  stayed at its full share of the stage even while closed (a deliberate
  choice to avoid layout jank, on the theory a full-bleed editor read
  uncomfortably wide) — so closing chat, or the content panel, left the
  freed space blank instead of growing the editor into it. Since the
  editor's own canvas no longer caps its reading measure either (the
  full-width pass above), that blank reservation had no remaining benefit.
  Dropped the desktop-only reservation and the `editorFill` breakpoint gate
  that paired with it — the editor now grows into whatever's free to its
  right on every breakpoint, not just the smaller ones.
- **Minimum panel widths halved**, `<ContentPanel>` and `<MarkdownPanel>`
  in lockstep (an eighth of the stage instead of a quarter — the two are
  kept in sync by their own doc comments so neither can be dragged narrower
  than the other).

## 3. Deficiencies found in stylo, tracked upstream

The full write-up — health checks, architecture read, the sticky-toolbar
iOS Safari saga, dependency footprint, and every gap below with its own
"who closes it" call — lives in the "Stylo Audit" report (published
artifact, not checked into the repo). Summarized here for the record:

- No conflict detection on save (Sympose's own gap — a real risk given the
  multi-agent hub could write the same note a human has open).
- No `[[wikilink]]` autocomplete, no in-note find/replace, no unsaved-changes
  indicator (Sympose-side, buildable on `getView()`/the vault tree already
  fetched — none of it needs a stylo change).
- `![[embed]]` transclusion doesn't exist upstream — filed there rather than
  forked.
- Floating chrome sharing the base surface's background token, `.cm-editor`
  setting font-size directly instead of inheriting, the selection bar having
  no awareness of the context menu opening over it, and the syntax palette
  having no relation to a host's own theme — four upstream gaps this
  integration had to reach past stylo's public `--stylo-*` contract into
  undocumented internal class names to work around. Real cost even where it
  worked, since those classes aren't part of the API stylo commits to
  keeping stable.

## 4. Verification

- `cd ui && npm run typecheck` — clean after every change in this pass.
- `cd ui && npm run build` — rebuilt `sympose/webui/` after every round (see
  ADR-079); shipped for `chat.sh --dashboard`, not just the `npm run dev`
  surface.
- `.venv/bin/pytest` — 309 passing; no Python touched by this work, run as
  part of closing it out per the project's verification standard.
- No automated UI test harness exists for this surface yet — every fix above
  was confirmed by driving the real dev server with a scratch Playwright +
  Chromium install against mocked vault API responses and screenshotting
  the result, not assumed from reading the diff.

## 5. Follow-ups (not done here)

In the order the audit recommends once the save pass starts:

1. `PUT /api/vault/note` designed around conflict detection first (mtime or
   content-hash check) — the one gap here with real data-loss risk.
2. `@codemirror/search` wired in — drop-in, no vault awareness needed,
   independent of the save pass.
3. Wikilink autocomplete off the vault tree already fetched on load.
4. An unsaved-changes indicator alongside the save button.
5. `![[embeds]]` left as a known gap, filed upstream, revisited only if real
   vault content shows it's load-bearing.
