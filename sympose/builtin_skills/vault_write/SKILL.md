---
name: "vault_write"
title: "Obsidian Vault Journaling & Note Persistence"
description: "Routing, structure, and linking for notes written via [DAILY_NOTE] / [WRITE_NOTE] / [APPEND_NOTE]."
recommended_models:
  - "gemini/gemini-3.6-flash"
  - "ollama/richardyoung/qwen2.5-14b-instruct-abliterated"
tags:
  - obsidian
  - journaling
  - writing
  - wikilinks
---

# Obsidian Vault Journaling & Note Persistence

Tag syntax and "markdown in chat ≠ a file on disk" are in the base rules. This
playbook is *where* notes go, *how* they're structured, and *how* they link.

## Which tag

- **`[DAILY_NOTE: <reflection>]`** — a diary entry, thread summary, or milestone
  thought from today. The runtime creates/locates `Daily/YYYY/mm-Month/YYYY-MM-DD.md`
  and appends a timestamped `### Reflection (HH:MM)` section.
- **`[WRITE_NOTE: <folder/file.md> | <content>]`** — a new note, essay, spec, or canvas.
- **`[APPEND_NOTE: <folder/file.md> | <content>]`** — add to an existing note without overwriting.

## Folder routing

Prefix every `[WRITE_NOTE]`/`[APPEND_NOTE]` path with an allowed folder, matched
to content type. Don't invent folders or assume a taxonomy beyond your sandbox.

| Folder | Content |
| :--- | :--- |
| `Daily/` | Diary reflections *(via `[DAILY_NOTE]`)* |
| `General/` | Cross-cutting canvases, roadmaps, team notes |
| `Projects/<Project>/` | Per-project blueprints — nested in the project subfolder, never loose in `Projects/` root |
| `Thoughts/` | Essays, philosophy, brainstorming |
| `People/` | Bios and profiles |
| `Movies/`, `Reading/` | Film and literature notes |
| `Quotes/` | Excerpts and aphorisms |
| `Limbo/` | Uncategorised fleeting ideas |

The runtime creates nested folders automatically. Channel canvases → `General/`;
project canvases → `Projects/<Project>/<Topic>.md`.

## Wikilinks vs. tags

- **`[[Wikilink]]`** — a concrete entity or note: people (`[[Anaïs Nin]]`),
  works (`[[If I Stay]]`), projects/concepts (`[[Sympose]]`), dates (`[[2026-08-27]]`).
- **`#tag`** — taxonomy/state/theme: `#jour`, `#reflection`, `#wip`, `#music`.

Never wikilink a category word (`[[reflection]]`, `[[growth]]`) — it spawns empty
ghost nodes. Use `#reflection`.

## Tags & frontmatter

- `[WRITE_NOTE]` → a `tags:` list in YAML frontmatter (plus `type:`, `created:`).
- `[DAILY_NOTE]` → end the payload with `Tags: #jour` + domain tags (`#cinema`, `#trading`, …).

```
[DAILY_NOTE: Reflection with [[Anaïs Nin]] on [[Rilke]]'s Duino Elegies and a long evening of [[Chopin]] — on longing, and returning to the desk.

Tags: #jour #reflection #music]
```

The payload contains only the note — no chat commentary or greetings. One tag,
at the end of the response, single clean frontmatter block.
