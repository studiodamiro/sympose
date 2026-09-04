---
title: "ADR-067 — Intelligent Ghost Session Pruning & Substantive Conversation Gating"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-067 — Intelligent Ghost Session Pruning & Substantive Conversation Gating

- **Status:** Accepted — refines
  [ADR-054](./2026-08-29_adr-054-jsonl-conversation-persistence-context-hydration.md)
  /
  [ADR-055](./2026-08-29_adr-055-milestone-based-async-titling.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Renumbered from ADR-061 during the 2026-09 documentation-standard conformance
pass to resolve a numbering collision; no decision content changed.

Launching the CLI and typing ephemeral one-word commands (`history`, `3`, `q`,
greetings) still wrote a persistent `.jsonl` session file, cluttering `/history`
with trivial 1-turn `"New Conversation"` ghosts.

## Decision

1. **`SessionManager.prune_ghost_sessions`.** On listing, persona switch, and
   reset, delete 0-turn empty sessions and 1-turn generic-greeting sessions
   (`turns_count <= 1` with `"New Conversation"` / `"Untitled Session"` titles);
   currently-active in-memory sessions are preserved.
2. **Substantive history listing.** `/history` filters out trivial ghosts, so the
   list holds only meaningful multi-turn discussions.

## Consequences

**Positive**

- `/history` stays high-signal; no disk bloat from throwaway launches.

**Negative / costs**

- The 1-turn heuristic could prune a genuine but very short first turn before it
  becomes multi-turn — bounded to generic-title cases to limit that.

## Alternatives rejected

> Not captured in the original decision record.
