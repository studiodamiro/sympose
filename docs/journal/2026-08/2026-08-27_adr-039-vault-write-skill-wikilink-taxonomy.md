---
title: "ADR-039 — Modular vault_write Skill, Obsidian Wikilink Taxonomy & Nested Hierarchies"
created: 2026-08-27
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-039 — Modular `vault_write` Skill, Obsidian Wikilink Taxonomy & Nested Hierarchies

- **Status:** Accepted
- **Date:** 2026-08-27
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Agents had no formal knowledge of Obsidian graph conventions — mixing `#tags`
with `[[wikilinks]]`, writing flat project files to the vault root, and dumping
full Markdown notes into Slack chat instead of writing silently.

## Decision

- Create `skills/vault_write/SKILL.md` codifying the **6-category wikilink
  taxonomy**: People, Dates / Daily Notes (`[[YYYY-MM-DD]]`), Projects &
  Products, Tech & Frameworks, Collections / MOCs, Media / Books / Music —
  wikilinks for entities, `#tags` for categories.
- Enforce nested project hierarchies: `Projects/<Project Name>/<file>.md`, not
  loose root files.
- Enforce the **Conversational Efficiency Contract**: a 2–3 sentence natural
  summary in chat; the Markdown payload delivered silently via action tags, no
  raw code blocks dumped into Slack.

## Consequences

**Positive**

- Agent-written notes look native in the Obsidian graph.
- Chat stays readable; the note goes to disk.

**Negative / costs**

- The taxonomy is prompt text the model must follow consistently; edge entities
  can still be mis-categorised.

## Alternatives rejected

> Not captured in the original decision record.
