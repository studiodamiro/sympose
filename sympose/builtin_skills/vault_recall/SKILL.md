---
name: "vault_recall"
title: "Obsidian Vault Historical Synthesis & Recall"
description: "Tiered retrieval to locate, inspect, and synthesise historical notes and daily reflections from the vault."
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

The files on disk are the source of truth (anti-fabrication and verbatim quoting
are in the base rules). No matching note → "I have no record of that in your vault."

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
