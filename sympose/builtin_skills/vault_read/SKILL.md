---
name: "vault_read"
title: "Obsidian Vault Historical Synthesis & Recall"
description: "Tiered retrieval to locate, inspect, and synthesise historical notes and daily reflections from the vault."
recommended_models:
  - "gemini/gemini-3.6-flash"
  - "ollama/qwen2.5:14b"
  - "ollama/gemma2:9b"
minimum_capability_tier: "standard"
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

- Before spawning anything, check what's already in front of you: a note
  already shown to you this session, a Vault Structure Map, the last few
  turns of conversation. A vague or pronoun reference ("that note", "it",
  "this one") almost always points at something already discussed —
  resolve it from what you already have first. Only spawn when the answer
  genuinely isn't anywhere in your current context.
- Answer not already in your pre-turn context → emit
  `[SPAWN_SUB_AGENT: vault_read | <what to find>]` and stop; wait for the
  report. The task string must be a real, self-contained instruction, not
  a one- or two-word fragment: name the specific file or subject if you
  already know it, and state what's actually being asked — e.g.
  `[SPAWN_SUB_AGENT: vault_read | read Thoughts/Ideaverse.md in full and
  summarize the App Ideas section]`, never a bare `[SPAWN_SUB_AGENT:
  vault_read | that]`.
- Never fall back to web `[SEARCH]` for the user's own notes, journal, or history.
- Retrieval comes back empty → "I have no record of that in your vault." Nothing more.

## Discovery — use the vault tools first, don't shell out

Two dedicated tools already do what a hand-built `find`/`grep`/`shuf` chain
was standing in for — use them first:

- **`vault_search(query, folder=None, max_results=10)`** — full-text search
  over the indexed vault, ranked, with snippets, optionally scoped to one
  folder. Use it for any keyword, topic, or date lookup instead of `grep`.
- **`vault_sample(folder, count=1)`** — returns the *real, full content* of
  one or more randomly sampled notes from a folder in a single call. Use it
  whenever the request names a folder without naming a specific note —
  "pick a random note," "surprise me," "what's a note from Daily" — it
  hands you the actual text directly, no separate read step after it.

When a **Vault Structure Map** is in your context (folder counts, top tags,
most-linked notes), it is the disk-true shape of the vault this turn — use
it to decide *which* folder to search or sample, and to answer whatever it
already settles outright (a note count, which folders exist, what links
where) with no tool call at all. It holds no note text, so it tells you
*where*, never *what a note says*.

Vaults vary (Flat, PARA, Johnny Decimal, Zettelkasten, date-nested) — feed
`vault_search` whatever anchor fits what you're looking for:

- **Keywords** likely in the title or body.
- **Dates** in any schema (`YYYY-MM-DD`, `YYYY/MM/DD`, `YYYYMMDD`).
- **Frontmatter** keys (`tags:`, `type:`, `project:`).
- **Wikilinks & backlinks** — follow `[[Note]]` outward and query incoming
  references to a concept/person/project to gather every entry touching it.

Fall back to `find`/`ls`/`read_file` only for what the two tools above
genuinely can't do — opening a specific path you already have, or a
non-markdown asset. Never use them to reconstruct a search or a random pick
that `vault_search` / `vault_sample` already does in one call; that
reconstruction is slower, burns tool-call budget on redundant attempts, and
is exactly what left past runs quoting invented content for notes they'd
never actually opened.

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
