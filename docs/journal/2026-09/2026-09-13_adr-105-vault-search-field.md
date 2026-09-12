---
title: "ADR-105 — Vault Search Field: Instant Client Filter, Backend Content Tier, Folder-Scoped Results"
created: 2026-09-13
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault-search
---

# ADR-105 — Vault Search Field: Instant Client Filter, Backend Content Tier, Folder-Scoped Results

- **Status:** Accepted — implemented 2026-09-13.
- **Date:** 2026-09-13
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

The content panel's toolbar has carried a `Search vault…` field for a while —
fully dead, a plain controlled `<input>` with its own comment noting there was
"no vault search engine to wire it to yet." damiro asked to wire it up, then
steered scope and layout live across several rounds as gaps surfaced one at a
time: title-only vs. tags vs. wikilinks, whether a query should reach past
the folder currently open, and — after a live test against his real vault
("searched 'quote' in the `Code` folder, expecting to see items from the
`Quotes` folder, but got nothing") — a genuine classification bug in the
existing search engine, not a staleness issue. The shape settled into two
tiers, a bug fix, and a small Settings surface for it.

## Decision

**Two search tiers, deliberately, not one** — the round-trip-frugality
mandate (`identity.md`) argues against a query firing a backend round-trip on
every keystroke, but a backend is the only place that can search note
*bodies* (never loaded client-side). So:

1. **Instant, client-side, zero round-trips** — `filterTreeByQuery` and its
   flat counterpart `flatSearchTree` (`ui/src/components/sympose/vault-tree.tsx`)
   match a query against a note's full vault-relative `path` (not just its
   leaf filename, so a query matching an *ancestor folder's* name surfaces
   everything under it), its frontmatter `tags`, and its wikilink neighbours
   (both outgoing targets and incoming backlinks). This works off data
   already in memory — `GET /api/vault/tree` now projects `tags` and `links`
   onto each `VaultNode` straight from the manifest it already reads for that
   call (`sympose/vault_tree.py`), no extra vault read, no separate endpoint.
2. **Debounced (300ms, 2-char minimum), backend, only for what tier 1
   structurally can't do** — `GET /api/vault/search` (`sympose/server.py`)
   wraps the existing `VaultManager.search_structured()` engine (ADR-003,
   ADR-057 — the same dual-tier `direct`/`sqlite_fts` search the CLI/Slack
   `/vault` command already used), adding content-body matches and any tag
   matches the instant pass missed.

**Results split by folder scope, not flattened.** The panel's own tree
(`panelNodes`, whatever folder is currently open) still only ever searches
itself — matching damiro's explicit correction after a first attempt made
the instant filter vault-wide and flattened a sibling folder's contents
directly under the open folder's heading, which read as if it were a child
of it. A second, separate merged list — `<VaultContentSearch>`
(`ui/src/components/sympose/vault-content-search.tsx`) — covers everything
*outside* the folder in view: tier-1's instant path/tag/wikilink matches
(shown immediately) plus tier-2's debounced content matches, de-duplicated by
path, captioned **"N matches beyond {folder}."** Per damiro: no nested
folder tree for this list — flat rows, pathname plus a one-line reason
(`#tag`, `↔ wikilink-target`, or the content snippet; nothing extra for a
plain path match, since the path already shows where it lives).

## Bug found via live testing, fixed in the same change

**A folder-name coincidence silently emptied the results.** `search_structured`'s
title-match check compared the query against a note's *whole* `rel_path`,
not just its filename. Searching "quote" therefore matched every note under
`Quotes/` purely because the *folder* is named `Quotes` — none of those were
real title matches, but with `title_matches` listed first they filled the
`max_results` cap entirely, and the frontend deliberately drops
`match_type: "title"` rows (already covered by tier 1's own path matching) —
net effect, total silence for a query that in fact had real matches (every
one of those notes is genuinely tagged `#quote`). Fixed in both engines:
`is_title_match` in `sympose/vault.py` and the FTS row classifier in
`sympose/vault_index.py` now check only the note's own filename. Tags were
also made a first-class `match_type: "tag"` (was silently absorbed into
`"title"` by the bug, or hardcoded to `"content"` with `tags: []` in the FTS
path) — a tag match's snippet is the matched tag itself.

## Also in this change

- **Settings → Search** (`ui/src/components/sympose/search-preferences-section.tsx`,
  cookie-backed via `ui/src/lib/use-search-preferences.ts`, same
  declare-once `SPEC`-table pattern as `use-nebula-preferences.ts`): a
  **"Search beyond current folder"** on/off toggle (default on — off skips
  tier 1 and 2 both, and never mounts `<VaultContentSearch>` at all, so no
  backend call fires), and **"Results per page"** (10 / 25 / 50, default 10)
  for the merged list, with Previous/Next paging that resets to page 1 on a
  new query or a changed page size.
- The search field's leading icon now swaps from a magnifying glass to a
  clickable **×** (`Cancel01Icon`, the same close-icon convention already
  used in dialogs/sheets/frontmatter chips) once there's text typed, clearing
  the query.
- Both the merged results list and the pre-existing vault Bin list
  (`<TrashList>`) were bumped from `text-xs` / `text-[11px]` to `text-sm` /
  `text-xs` — there's no distinct "medium" token between those two in this
  project's scale, `text-sm` is the very next step up and is what the
  folder-tree's own note rows already use, tried live at damiro's request for
  visual consistency and kept.

## Consequences

- Vault search now matches on name/path, folder name, tags, and wikilinks —
  instantly — plus note content, deferred to a debounced backend call, with
  zero backend traffic at all unless a query is 2+ characters and typing has
  paused.
- The classification fix generalizes beyond this feature: any future caller
  of `VaultManager.search_structured()` (the CLI/Slack `/vault` command
  included) now gets correct `title`/`tag`/`content` labels instead of a
  folder-name coincidence masquerading as a title match.
- `flatSearchTree` and `filterTreeByQuery` are independent, purpose-built
  matchers (tree-shaped vs. flat) over the same `VaultNode` shape — not one
  forced to serve both the folder-tree view and the flat "beyond" list.

## Alternatives rejected

- **A single vault-wide instant list, folder distinction dropped entirely.**
  Tried first; rejected by damiro directly — flattening a sibling folder's
  contents under the currently-open folder's heading misrepresented it as
  that folder's own contents.
- **Two separate flat lists** ("beyond folder" instant matches, and the
  backend's "beyond the name" content matches, side by side). Offered as an
  option; damiro chose merging them into one de-duplicated list instead,
  since both tiers can find the same note (e.g. by tag) and showing it twice
  under two headings would have read as two different results.
- **Reusing the Knowledge Nebula's tag/graph data as the search source.**
  Considered for tag matching specifically; rejected — that graph is
  whole-vault (not persona-scoped like the vault tree) and falls back to a
  bundled offline sample until its own `/api/vault/graph` fetch resolves, so
  it could have surfaced fake sample-derived matches. The tree endpoint's own
  manifest read was already grounded and persona-scoped, and free.
- **Filtering the backend's vault-wide content matches down to "outside the
  current folder" to avoid duplicating tier 1's own in-folder matches.**
  Rejected — the folder-tree view has no content-matching capability at all,
  so a content-only match *inside* the current folder would otherwise never
  surface anywhere; letting the backend stay vault-wide and de-duplicating
  only by path (against tier 1's actual results) keeps that case covered.

## Verification

- `.venv/bin/pytest` — 398 passed, including three new regression tests
  reproducing the folder-name-flooding bug directly (`tests/unit/test_vault_index.py`):
  a filename match still classifies `title`, a tag-only match classifies
  `tag` with the matched tag as its snippet, and a note whose only relation
  to the query is living in a coincidentally-named folder no longer appears
  at all when it has no real match of its own.
- `cd ui && npm run typecheck` — clean, every round.
- `cd ui && npm run build` — rebuilt `sympose/webui/` (ADR-079) after every
  round.
- Manually verified `VaultManager.search_structured()` directly against
  damiro's real vault (`MASTER_VAULT_PATH`) outside the dashboard's HTTP auth
  layer, both before and after the classification fix, confirming the exact
  regression damiro reported and its resolution (15 `Quotes/` notes, each
  genuinely tagged `#quote`, went from 100% mislabeled `title` — and
  therefore invisible — to 100% correctly labeled `tag` and visible).

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` updated in the same
change.
