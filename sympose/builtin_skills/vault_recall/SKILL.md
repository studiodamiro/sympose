---
name: "vault_recall"
title: "Obsidian Vault Historical Synthesis & Recall"
description: "Tiered retrieval protocol to locate, inspect, and synthesise historical notes and daily reflections from the Obsidian vault."
recommended_models:
  - "gemini/gemini-3.5-flash-lite"
  - "ollama/qwen2.5:14b"
  - "ollama/gemma2:9b"
tags:
  - memory
  - retrieval
  - obsidian
  - history
---

# Obsidian Vault Historical Recall

The Markdown files on disk are the single source of truth. Anti-fabrication and
verbatim-quoting rules are in the Universal Workspace Rules — if a topic has no
matching note, say "I have no record of that in your vault."

## Discovery (don't assume structure)

Vaults vary (Flat, PARA, Johnny Decimal, Zettelkasten, date-nested). Find notes
dynamically with non-destructive inspection (`find`, `ls`, pattern matching)
across multiple anchors:

- **Keywords** in filenames (`*database*`, `*theology*`).
- **Dates** in any schema (`YYYY-MM-DD`, `YYYY/MM/DD`, `YYYYMMDD`).
- **Frontmatter** keys (`tags:`, `type:`, `project:`, `category:`).
- **Wikilinks & backlinks** — follow `[[Note]]` outward and query incoming
  references to a concept/person/project to gather every entry that touches it.

Ignore hidden dirs (`.obsidian/`, `.git/`, `.trash/`) and binary/asset folders.

## Extraction — small to big

Don't ingest whole transcripts when targeted sections exist. Pull frontmatter
(`entry:`, `type:`, `project:`, `tags:`) and high-signal headings
(`## Key Decisions`, `## Action Items & Next Steps`, `### Reflection (HH:MM)`).
Narrow to the 2–4 most relevant notes before synthesising.

## Output — match the question, don't force a template

- **Single note requested** → quote the verbatim Markdown with its path and
  created/updated date. No extra "Timeline" headings.
- **Multi-note history / milestone evolution** → structured synthesis:
  ```
  ### Historical Synthesis: <Topic>

  #### Primary Sources
  - `Projects/<Project>/TECH_DEBT.md` (2026-08-20)
  - `Daily/2026/08-August/2026-08-15.md` (2026-08-15)

  #### Key Decisions & Chronology
  1. **<Decision>** — what was agreed and why.
  ```
- **Specific fact** ("what was the DB port?") → the direct answer and its exact
  quotation, no wrapper headings.
