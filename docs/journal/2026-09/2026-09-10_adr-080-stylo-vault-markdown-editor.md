---
title: "ADR-080 — Stylo as the Vault Markdown Editor"
created: 2026-09-10
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - editor
---

# ADR-080 — Stylo as the Vault Markdown Editor

- **Status:** Accepted — implemented 2026-09-09/10.
- **Date:** 2026-09-10
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Replaces the fully-mocked reader in `<MarkdownPanel>` built in
  [2026-08-31 — App-Shell Stage Build-Out](../2026-08/2026-08-31_web_dashboard_chat_and_markdown_panels.md).
- Implementation detail lives in
  [2026-09-10 — Stylo Integration: Vault Wiring, Editor Preferences & UI Polish](./2026-09-10_stylo-editor-integration-and-polish.md).

## Context

`<MarkdownPanel>` rendered a static mock: hand-written sample frontmatter,
hard-coded inline formatting buttons that did nothing, a hard-coded links
footer. The dashboard's vault API (`GET /api/vault/note`) already returned
real file content; nothing rendered it as an actual editable surface.

Sympose's own vault philosophy — the file on disk is the only truth, no
shadow model — argues against a ProseMirror/Lexical-style editor with an
internal document tree that has to be serialized back to Markdown and can
silently mangle frontmatter, `[[wikilinks]]`, or embedded math on a
round-trip. The editor needed to be canonical-Markdown-in, canonical-
Markdown-out, matching how `vault_write` and every other part of the system
already treats a note.

`@damiro/stylo` (`github:studiodamiro/stylo`), a sibling project, already
took that exact stance: `value` is a plain Markdown string, CodeMirker 6 owns
editing, a live "in-place" decoration canvas (ADR-002/ADR-004 in its own
journal) renders headings/emphasis/wikilinks inline without leaving source
mode. It was pulled and audited before adoption — health checks, architecture
read, a full install-and-wire dry run — rather than taken on faith; see the
"Stylo Audit" report referenced in the implementation entry for the full
write-up, including the deficiencies found along the way.

## Decision

**Adopt `@damiro/stylo` as `<MarkdownPanel>`'s editing surface, in its
default `in-place` mode, loading real vault content read-only for this
pass.**

1. **Install as a git dependency.** `ui/package.json` gains
   `"@damiro/stylo": "github:studiodamiro/stylo"` plus its CodeMirror/Lezer
   peers (`@codemirror/state`, `@codemirror/view`, `@codemirror/commands`,
   `@codemirror/language`, `@codemirror/lang-markdown`, `@lezer/common`,
   `@lezer/highlight`, `@codemirror/language-data` for fenced-code syntax
   coloring) and `yaml` for the frontmatter card. No new *runtime service* —
   this is a client-side library, same category as any other UI dependency
   already in `ui/package.json`.
2. **Load-only for this pass.** `GET /api/vault/note` feeds `<Stylo
   value={body} onChange={setBody}>`; there is no `PUT /api/vault/note` yet,
   so stylo's own `save` toolbar button renders disabled (`onSave` left
   unset). Conflict detection on a future write endpoint is called out as a
   follow-up, not solved here — Sympose is a multi-agent hub, so a persona's
   own tool-calling backend could write the same note a human has open.
3. **Frontmatter is a separate, editable card — not stylo's own `---`
   render.** `splitFrontmatter()` (stylo) hands the raw block to a
   `<FrontmatterCard>` built on the `yaml` package (not a hand-rolled
   parser, given real vault frontmatter uses varied YAML shapes); array
   fields render as removable/addable pills, `[[wikilink]]`-valued fields
   render as clickable links with the brackets dropped. Stylo never sees the
   frontmatter text — only the body is passed as `value`.
4. **The `--stylo-*` token contract absorbs Sympose's theme** (ADR-047/051
   design tokens) rather than a fork: background, text, muted text, border,
   accent, link, focus ring, radius, and (added during the polish pass) the
   fenced-code syntax palette all bridge to existing OKLCH tokens, so dark
   mode needs no separate override block.
5. **`toolbar.sticky` is deliberately left unset.** The panel already gives
   stylo a bounded height (`min-h-0 flex-1`); stylo's own CHANGELOG
   documents a week-long fight with iOS Safari's compositing behavior that a
   bounded-height layout sidesteps entirely — no `position: fixed`, no
   `requestAnimationFrame` watchdog. Confirmed, not just assumed: the
   toolbar-above-scrolling-body shape needed zero changes to host stylo
   cleanly.

## Consequences

- The vault markdown panel is a real, live-editing surface for the first
  time — headings, emphasis, lists, wikilinks (clickable, opening the target
  note), inline code, and fenced code (syntax-colored via
  `@codemirror/language-data`) all render and edit in place, sourced from
  the actual file on disk.
- A new git-install dependency (not an npm registry package) — pin a commit
  or tag rather than tracking `main`, since stylo is pre-1.0 and its own
  changelog shows one precedent breaking change (CodeMirror moved to peer
  deps).
- No write path yet. `[[wikilink]]` autocomplete, in-note find/replace, an
  unsaved-changes indicator, and `![[embed]]` transclusion are documented
  gaps, not silently missing — see the implementation entry's "Gaps & next
  steps" for the recommended build order once the save pass starts.
- Several of stylo's own internal (undocumented) CSS class names had to be
  reached into — its floating chrome (context menu, selection bar) shares a
  background token with the base canvas, `.cm-editor`'s font-size is set
  directly rather than inherited, and the selection-formatting bar has no
  built-in awareness of the right-click menu opening over it. Each is a real
  cost paid for going first; flagged upstream rather than forked.

## Alternatives rejected

- **Keep the mock, build a custom editor.** A hand-rolled CodeMirror wiring
  reinvents exactly what stylo already solved (frontmatter fence handling,
  wikilink scanning shared between render and edit-time, an in-place
  decoration layer) — reinventing it in-house is strictly more maintenance
  for the identical plain-text-canonical outcome stylo already commits to.
- **A ProseMirror/Lexical/TipTap-style rich editor.** Keeps its own document
  model as the source of truth and serializes to Markdown on save — the
  exact round-trip-fidelity risk (frontmatter, wikilinks, math surviving
  intact) the vault's "file on disk is truth" posture rules out.
- **`preview`/`split` mode as the default instead of `in-place`.** Splits
  editing from rendering (a raw-source pane plus a rendered pane, or a
  toggle between them) rather than one live canvas — a worse match for "the
  note reads like the note" and pulls in the `react-markdown` + `remark-gfm`
  + KaTeX render chunk on every load instead of only when a fenced-math or
  preview surface is actually used.
- **Wait for a write endpoint before shipping anything.** Read-only wiring
  is a complete, independently useful slice on its own (the panel is
  finally showing real content instead of a static mock) and de-risks the
  library adoption before the harder conflict-detection design work on
  `PUT /api/vault/note` begins.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
