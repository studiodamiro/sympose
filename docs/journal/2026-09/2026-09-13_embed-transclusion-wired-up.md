---
entry: 2026-09-13
created: 2026-09-13 00:00
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/ui
  - editor
---

# Sympose Engineering Log: `![[embed]]` Transclusion Wired Up

> **Date:** Sunday, September 13, 2026
> **Topic:** `![[ref]]` transclusion was flagged as a documented gap in
> ADR-080 (2026-09-10) alongside wikilink autocomplete, tag autocomplete,
> and an unsaved-changes indicator. The first two have since shipped; this
> closes the third. Unlike tag autocomplete, stylo's `embedSource` prop
> already existed — this was pure Sympose-side work, not an upstream ask.
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Implemented. Image and whole-note embeds resolve; heading/
> block-id-scoped embeds recognize the suffix but transclude the whole note
> (not yet sliced) — see §3.

## 1. What shipped

- **Backend** (`sympose/vault.py`, `sympose/server.py`): a new
  `VaultManager.resolve_asset_path` (mirrors `read_note`'s three-tier
  lookup — direct join, basename-in-allowed-dir, recursive filename match
  — but for any file, matched on the full filename since an asset ref
  always carries its extension) backing a new `GET /api/vault/asset` route
  that streams the resolved file via `FileResponse`, scoped to the
  persona's sandbox the same way every other vault route is. Deliberately
  does **not** consult `vault.ignore_folders` — that list's own default
  names "Attachments," exactly where embedded images live, so applying it
  here would make them unreachable; only dot-directories are skipped.
  Covered in `tests/unit/test_vault.py::TestResolveAssetPath` (including a
  regression test that an `Attachments/` folder is actually reachable) and
  `tests/unit/test_server.py::TestVaultAsset`.
- **Frontend** (`ui/src/lib/vault-asset-api.ts`, `ui/src/lib/resolve-embed.tsx`):
  `resolveEmbed(tree, persona, ref)` — an image ref (`.png`/`.jpg`/`.gif`/
  `.svg`/`.webp`/`.bmp`/`.avif`, checked by extension) becomes an `<img>`
  pointed at the new asset route, with `|300` / `|300x200` size-hint
  parsing; anything else is looked up against the vault tree via the
  existing `findNoteByWikilink` (the same resolver `[[wikilink]]` clicks
  already use) and, if found, fetched and rendered read-only through a
  nested `<Stylo mode="preview">`. Returns `null` — stylo's "keep it
  literal" signal — when nothing resolves.
- **Wiring** (`ui/src/routes/app-shell.tsx`, `markdown-panel.tsx`):
  `embedSource` threaded through the same ref-plus-stable-callback pattern
  `wikiLinkSource`/`tagSource` already use, plus a new `activePersonaRef`
  (a persona switch alone doesn't remount `<Stylo>`, so the callback needs
  a live read on it same as the tree).

## 2. Verified live, not assumed

Static reading alone wasn't trusted here — same discipline as
`stylo/docs/requests/2026-09-13_preview-full-parity-with-in-place.md`'s own
cautionary tale (a sibling request withdrawn after being filed on an
unverified premise). Built an isolated Vite harness (real `@damiro/stylo`,
real `resolve-embed.tsx`, a mocked `fetch` standing in for the backend) and
rendered all five branches — image with a size hint, image without one, a
resolved note, a note ref carrying a `#Heading` suffix, and an unresolved
ref — confirming each produced the exact expected DOM (`<img>` with the
right `src`/`width`/`height`, a nested `.preview` tree with the fetched
note's rendered content, or `null`). Full backend suite
(`.venv/bin/pytest`, 406 tests) and `ui/` typecheck both pass.

## 3. Known gap, on record rather than silently missing

`#Heading` / `#^blockid` suffixes are parsed and stripped before resolving
(so `![[Note#Section]]` still finds `Note`), but there is no
heading-scoped or block-scoped extraction — the *whole* note transcludes
regardless of the suffix. No backend support for slicing a note down to one
section exists yet. Worth a follow-up once (if) it becomes a live need;
deliberately not built speculatively here, same call ADR-080 made about
its own four gaps.

Also deliberately capped at one level of nesting: the nested
`<Stylo mode="preview">` used for a note embed is given no `embedSource` of
its own, so an `![[…]]` inside an embedded note renders literally instead
of resolving. The simplest way to rule out circular transclusion
(A embeds B embeds A) without tracking a resolution chain — not expected to
be a real-world limitation, Obsidian-style vaults rarely nest transclusion
that deep.
