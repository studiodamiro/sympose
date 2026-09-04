---
title: "ADR-061 — Sub-Agent [READ_NOTE] Explicit-Intent Gating"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-061 — Sub-Agent `[READ_NOTE]` Explicit-Intent Gating

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`prompts/worker_system.md` Directive 2 told workers to emit `[READ_NOTE]` "when
retrieving, finding, or presenting notes". Workers then fired the full
`MultiSectionPanel` note viewer even for "pick a random movie" — a 27-line note
dump instead of a one-line pick.

## Decision

Rewrite Directive 2:

> **Emit `[READ_NOTE]` ONLY** when the task explicitly asks to *read, view, pull
> up, or open* a full note. **For search, query, random-pick, or fact
> extraction** — return a concise factual answer directly in text.

Split into sub-rules with concrete examples ("pick a random movie" → no
`[READ_NOTE]`; "pull up Her" → `[READ_NOTE]`).

## Consequences

**Positive**

- Picks, searches, and Q&A return clean prose; the terminal isn't flooded.
- `[READ_NOTE]` still fires on genuine pull-up requests.

**Negative / costs**

- The gate is prompt guidance, so a model can still misjudge intent on an
  ambiguous request.

## Alternatives rejected

- **Leaving the broad "whenever presenting notes" instruction in place.**
  Rejected: it over-triggered the full note viewer for non-reading tasks.
