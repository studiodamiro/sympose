---
name: "vault_recall"
title: "Obsidian Vault Historical Synthesis & Recall"
description: "Tiered retrieval to locate, inspect, and synthesise historical notes and daily reflections from the vault."
recommended_models:
  - "gemini/gemini-3.6-flash"
  - "ollama/qwen2.5:14b"
  - "ollama/gemma2:9b"
tags:
  - memory
  - retrieval
  - obsidian
  - history
---

# Obsidian Vault Historical Recall

**Ground rule.** The files on disk are the only source of truth. Every statement
you make about a note is a verbatim quote — path, dates, names, wording — from a
retrieval payload you were handed *this turn*. Never reconstruct a note from the
topic, the conversation, or what sounds plausible; never invent a date, quote, or
reflection.

- Answer not already in your pre-turn context → emit
  `[SPAWN_WORKER: vault_recall | <what to find>]` and stop; wait for the report.
- Never fall back to web `[SEARCH]` for the user's own notes, journal, or history.
- Retrieval comes back empty → "I have no record of that in your vault." Nothing more.

## Discovery — don't assume structure

Vaults vary (Flat, PARA, Johnny Decimal, Zettelkasten, date-nested). Find notes
with non-destructive inspection (`find`, `ls`, pattern matching) across anchors:

- **Keywords** in filenames.
- **Dates** in any schema (`YYYY-MM-DD`, `YYYY/MM/DD`, `YYYYMMDD`).
- **Frontmatter** keys (`tags:`, `type:`, `project:`).
- **Wikilinks & backlinks** — follow `[[Note]]` outward and query incoming
  references to a concept/person/project to gather every entry touching it.

Ignore hidden dirs (`.obsidian/`, `.git/`) and asset folders.

## Extraction — small to big

Pull frontmatter and high-signal headings (`## Key Decisions`,
`## Action Items`, `### Reflection (HH:MM)`) rather than whole transcripts.
Narrow to the 2–4 most relevant notes before synthesising.

## Output — match the question

- **One note** → quote the verbatim Markdown with its path and dates. No extra headings.
- **Multi-note history** → structured synthesis:
  ```
  ### Historical Synthesis: <Topic>

  #### Primary Sources
  - `Projects/<Project>/TECH_DEBT.md` (2026-08-20)

  #### Key Decisions & Chronology
  1. **<Decision>** — what was agreed and why.
  ```
- **Specific fact** → the direct answer and its exact quotation, no wrapper.
