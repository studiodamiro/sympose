---
name: "vault_write"
title: "Obsidian Vault Journaling & Note Persistence"
description: "Routing, structure, and linking for notes written via [DAILY_NOTE] / [WRITE_NOTE] / [APPEND_NOTE]."
recommended_models:
  - "gemini/gemini-3.6-flash"
  - "ollama/gemma2:9b"
tags:
  - obsidian
  - journaling
  - writing
  - wikilinks
---

# Obsidian Vault Journaling & Note Persistence

Tag syntax and "markdown in chat ≠ a file on disk" are in the base rules. This
playbook is *where* notes go, *how* they're structured, and *how* they link.

## Match this vault, not a generic default

Before writing, weigh what similar existing notes in this vault actually look
like — their structure, tone, and any template already in play for that
folder — over any generic assumption. When it's genuinely unclear which
folder a note belongs in, or what style/format this vault expects for it,
ask the user rather than guessing or inventing a convention that isn't
already there.

## Which tag

- **`[DAILY_NOTE: <reflection>]`** — a diary entry, thread summary, or milestone
  thought from today. The runtime creates/locates `Daily/YYYY/mm-Month/YYYY-MM-DD.md`
  and appends a timestamped `### Reflection (HH:MM)` section.
- **`[WRITE_NOTE: <folder/file.md> | <content>]`** — a new note, essay, spec, or canvas.
- **`[APPEND_NOTE: <folder/file.md> | <content>]`** — add to an existing note without overwriting.

## Folder routing

Prefix every `[WRITE_NOTE]`/`[APPEND_NOTE]` path with an allowed folder, matched
to content type. `[DAILY_NOTE]` always resolves to `Daily/YYYY/mm-Month/YYYY-MM-DD.md`
on its own — never route a diary reflection there yourself.

For everything else, this vault's own existing top-level folders are the taxonomy —
route to whichever one already matches the content (a project note into its
project folder, a film note into a film-notes folder, and so on). Don't invent a
new top-level folder or assume categories this vault doesn't already have; when
nothing existing fits, use whatever this vault treats as its general/uncategorised
folder rather than making one up. A per-project note nests inside that project's
own subfolder, never loose at the collection's root.

The runtime creates nested folders automatically.

## Wikilinks vs. tags

- **`[[Wikilink]]`** — a concrete entity or note: a person (`[[Jane Doe]]`),
  a work (`[[Some Book Title]]`), a project/concept (`[[Sympose]]`), a date
  (`[[2026-08-27]]`).
- **`#tag`** — taxonomy/state/theme: `#jour`, `#reflection`, `#wip`.

Never wikilink a category word (`[[reflection]]`, `[[growth]]`) — it spawns empty
ghost nodes. Use `#reflection`.

## Tags & frontmatter

- `[WRITE_NOTE]` → **body content only, no frontmatter.** The runtime stamps
  the real Obsidian template for the target folder from the vault's own
  `Templates/` collection (title, date, and that type's default `tags:`
  already filled in); a folder without a dedicated template gets the vault's
  generic `Note template.md`. If this vault has no `Templates/` collection
  at all, the runtime generates a minimal `title`/`created`/`tags:` block
  itself instead — the note is never left without frontmatter. Writing your
  own frontmatter block overrides this and loses those per-type fields —
  only do it for a field the template can't express.
- `[DAILY_NOTE]` → end the payload with `Tags: #jour` + whatever domain tags this
  vault already uses for the topic (e.g. `#reading`, `#work`, …).

```
[DAILY_NOTE: Reflection on finishing [[Some Book Title]] tonight, and what it
stirred up about a decision I've been putting off.

Tags: #jour #reflection #reading]
```

The payload contains only the note — no chat commentary or greetings, one tag
at the end of the response.
