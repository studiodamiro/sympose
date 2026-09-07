---
name: "vault_write"
title: "Obsidian Vault Journaling & Note Persistence"
description: "How to route, structure, and tag notes written into the Obsidian vault via the [DAILY_NOTE] / [WRITE_NOTE] / [APPEND_NOTE] action tags."
recommended_models:
  - "gemini/gemini-3.5-flash-lite"
  - "ollama/richardyoung/qwen2.5-14b-instruct-abliterated"
tags:
  - obsidian
  - journaling
  - writing
  - wikilinks
---

# Obsidian Vault Journaling & Note Persistence

The action-tag syntax and the "printing markdown ≠ writing to disk" rule are in the
Universal Workspace Rules. This playbook covers *where* notes go, *how* they are
structured, and *how* they link.

## Which tag

- **`[DAILY_NOTE: <reflection>]`** — a diary entry, a thread summary, milestone thoughts from today. The runtime locates/creates `Daily/YYYY/mm-Month/YYYY-MM-DD.md` and appends a timestamped `### Reflection (HH:MM)` section.
- **`[WRITE_NOTE: <folder/file.md> | <content>]`** — a new dedicated note, essay, spec, or canvas.
- **`[APPEND_NOTE: <folder/file.md> | <content>]`** — add a section/bullets to an existing note without overwriting it.

## Folder routing

Prefix every `[WRITE_NOTE]` / `[APPEND_NOTE]` path with an allowed folder. Match the
*content type* to the folder — do not invent folders, and do not assume a fixed
taxonomy beyond the ones your persona is sandboxed to:

| Folder | Content type |
| :--- | :--- |
| `Daily/` | Chronological diary reflections *(via `[DAILY_NOTE]`)* |
| `General/` | Cross-cutting canvases, roadmaps, team notes |
| `Projects/<Project>/` | Per-project blueprints and canvases — always nested in the project subfolder, never loose in `Projects/` root |
| `Thoughts/` | Essays, philosophy, psychoanalysis, brainstorming |
| `People/` | Bios, character and collaborator profiles |
| `Movies/`, `Reading/` | Film and literature notes |
| `Quotes/` | Excerpts and aphorisms |
| `Limbo/` | Uncategorised fleeting ideas |

The runtime creates nested folders on disk automatically. Route channel canvases to
`General/`; route project canvases to `Projects/<Project>/<Topic>.md`.

## Wikilinks vs. tags

Two different mechanisms — never conflate them:

- **`[[Wikilink]]`** — a concrete entity or note: people (`[[Anaïs Nin]]`), works (`[[If I Stay]]`), projects/concepts (`[[Sympose]]`, `[[Zettelkasten]]`), dates (`[[2026-08-27]]`).
- **`#tag`** — taxonomy, state, or theme: `#jour`, `#reflection`, `#wip`, `#architecture`, `#music`.

Never wrap a category word in a wikilink (`[[reflection]]`, `[[growth]]`) — it
spawns empty ghost nodes in the graph. Use `#reflection`, `#growth`.

## Tags & frontmatter

- **`[WRITE_NOTE]`**: include a `tags:` list in YAML frontmatter (`type:`, `created:`, plus topical tags).
- **`[DAILY_NOTE]`**: end the payload with `Tags: #jour` plus domain tags (`#reflection`, `#cinema`, `#trading`, `#growth`, …).

Example:
```
[DAILY_NOTE: Reflection with [[Anaïs Nin]] on [[Parting Time]] and memories of [[Lea]] — grief, closure, and [[Personal Growth]].

Tags: #jour #reflection #growth #music]
```

## Payload hygiene

The note payload contains ONLY the note. No chat commentary, greetings, or
"let me know if you'd like changes" inside the file. Emit exactly one action tag,
at the end of the response, with a single clean frontmatter block.
