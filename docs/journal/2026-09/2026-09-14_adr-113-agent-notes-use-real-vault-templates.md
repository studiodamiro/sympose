---
title: "ADR-113 — Notes Use the Vault's Real Templates, Agent and Dashboard Alike (amends ADR-039, ADR-076, ADR-083)"
created: 2026-09-14
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - vault
  - skills
---

# ADR-113 — Notes Use the Vault's Real Templates, Agent and Dashboard Alike (amends ADR-039, ADR-076, ADR-083)

- **Status:** Accepted — implemented 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)
- Amends the `vault_write` skill introduced in
  [ADR-039](./2026-08-27_adr-039-vault-write-skill-wikilink-taxonomy.md) and
  compressed in [ADR-076](./2026-09-07_adr-076-skill-playbook-single-source-and-compression.md),
  and the dashboard's editor-seeded stub from
  [ADR-083](./2026-09-10_adr-083-editor-note-creation-and-frontmatter-fidelity.md).

## Context

damiro asked whether note creation could be automated from his vault's own
`Templates/` folder, where each file (`Movie template.md`, `People
template.md`, `Quote template.md`, …) is the default frontmatter skeleton for
notes in the correspondingly-named folder, and `Note template.md` is the
fallback for any folder without one — the same convention already expressed
in the vault's `obsidian-hotkeys-for-templates` plugin config. He wanted both
the human and any Sympose agent writing to the vault to draw from the same
real templates, not two divergent notions of "default frontmatter."

Investigating turned up that `VaultManager.get_template_for_path`
(`sympose/vault.py`) already existed and already did most of this — matching
a note's target folder against `Templates/*.md` and rendering `{{date}}` /
`{{time}}` / `{{title}}` placeholders — but two things undercut it:

1. Its folder→template mapping was a 5-entry hardcoded dict (`daily/`,
   `thoughts/`, `people/`, `movies/`, `quotes/`), duplicating information
   already present as the actual filenames in `Templates/`. Adding, renaming,
   or removing a template required a matching code change or the note silently
   fell back to the generic template.
2. `builtin_skills/vault_write/SKILL.md` instructed the agent to author its
   own `[WRITE_NOTE]` frontmatter (`tags:`, `type:`, `created:`) on every note.
   `VaultManager.write_note` treats any payload already starting with `---` as
   final content and skips template resolution entirely — so every
   agent-written note got the generic block instead of the real per-folder
   template, losing type-specific fields (a Movie note's `release`/`rating`/
   `imdb`, a Person's `birthday`/`phone`/`email`, …) that the human-authored
   convention already defines.
3. `VaultManager.create_note` — the backend behind every "new note" affordance
   in the dashboard (`vault-row-menu.tsx`'s context-menu action and
   `app-shell.tsx`'s toolbar action, both calling the client's
   `createVaultNote`, which never sends `content`) — never called
   `get_template_for_path` at all. Its own hardcoded stub (`title:`/`created:`/
   `tags: []`) from ADR-083 ran unconditionally, so a note created from the
   dashboard had the identical generic-frontmatter problem as an agent-written
   one, just via a second, independent code path.

## Decision

- **ADR-113.1 — Derive the folder↔template match from `Templates/` itself.**
  `get_template_for_path` now lists `Templates/*.md`, strips each filename's
  trailing `template.md`, and matches the result against the note's top-level
  folder exactly or as a singular/plural pair (`Movies` ↔ `Movie`, `Quotes` ↔
  `Quote`, `People` ↔ `People`, `Daily` ↔ `Daily`, …). `Note template.md` is
  excluded from the candidate set and kept as the always-present fallback for
  a folder with no dedicated template. The vault's own template collection is
  the single source of truth; no code change is needed to add or rename one.
- **ADR-113.2 — `[WRITE_NOTE]` payloads carry body content only.** The
  `vault_write` skill (`sympose/builtin_skills/vault_write/SKILL.md`, the
  single source per ADR-076 — the top-level `skills/` copy is gitignored and
  only re-seeded when absent, mirrored here for this checkout) no longer tells
  the agent to author its own `tags:`/`type:`/`created:` frontmatter. It now
  says to write body content only, so the runtime's real per-folder template
  applies; writing frontmatter by hand remains possible for a field no
  template can express, but is now the documented exception rather than the
  default.
- **ADR-113.3 — `create_note`'s stub-seeding calls the same
  `get_template_for_path` / `_render_template` path.** A new
  `VaultManager._render_template` static helper (the `{{date}}`/`{{time}}`/
  `{{title}}`/`{{date:YYYY}}` substitution) is factored out of `write_note` and
  reused by `create_note`, so both the agent's `[WRITE_NOTE]` path and every
  dashboard "new note" button resolve the folder's real template through one
  shared implementation instead of two copies. `create_note`'s own generic
  stub survives only as the fallback for a vault with no `Templates/` folder,
  or a folder matching no template at all.

## Consequences

**Positive**

- A Movie, Person, Quote, or Thoughts note — whether written by an agent or
  created from any "new note" button in the dashboard — now carries the same
  fields and default tags as one created by hand in Obsidian: one template
  convention, one code path, not three.
- The mapping self-updates when damiro edits `Templates/`; no sympose release
  needed for a new note type.
- Regression coverage added: `tests/unit/test_vault.py::TestGetTemplateForPath`
  (exact match, singular/plural match, unmapped-folder fallback, a
  newly-added template file matched with no code change, no-`Templates/`
  vault); two `TestWriteNote` cases (template applied when the payload has no
  frontmatter; a model-supplied frontmatter block still wins verbatim); one
  `TestCreateNote` case (a dashboard-created note in a mapped folder gets the
  real template, not the generic stub).

**Negative / costs**

- An agent still has no way to populate a template's blank type-specific
  fields (a Quote's `author`, a Person's `phone`) from conversation content —
  those land blank, exactly as a human's fresh "New note from template" would,
  and get filled in later. Structured field population is future work, not
  addressed here.
- The singular/plural heuristic (trailing `s`) doesn't generalize to
  irregular plurals; an oddly-named future template (e.g. `Colloquy template.md`
  for a `Colloquies/` folder) would need an exact-name match instead and fall
  back to `Note template.md` otherwise — an acceptable, visible degradation,
  not a hard failure.

## Alternatives rejected

- **Keep the hardcoded mapping, just add the missing folders.** Simpler diff,
  but re-introduces the same drift risk this ADR removes: every new template
  file would still need a matching code change. Rejected.
- **Have the agent emit frontmatter and merge it onto the template
  server-side.** Gets the agent partial credit for fields it actually knows,
  but requires a merge/precedence policy per field and a schema per template
  the runtime doesn't have. Deferred — the current fix already closes the
  actual bug (agent frontmatter completely overriding the real template); an
  eventual "sensible field injection" pass over the merge policy is separate
  and not blocking.
- **A standalone system-level Python script instead of a skill/runtime fix.**
  The original framing (a script the user or a system icon could invoke). Once
  it became clear the agent path already existed as `vault_write` and simply
  had a bug, patching the existing mechanism and extending it to the
  dashboard's `create_note` was preferred over adding a second, parallel
  system — one round-trip-frugal code path for both human and agent note
  creation, per the identity directive's round-trip frugality principle.
- **A separate template-resolution helper for `create_note`.** Would have kept
  `write_note` and `create_note` fully independent, but duplicates the exact
  same placeholder substitution a second time — the thing ADR-113.1 was
  already removing one copy of. `_render_template` is shared instead.
