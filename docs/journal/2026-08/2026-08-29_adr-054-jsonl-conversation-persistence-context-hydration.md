---
title: "ADR-054 — Zero-Bloat Conversation Persistence (.jsonl), Decoupled UI History & Sliding Context Window Hydration"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-054 — Zero-Bloat Conversation Persistence (`.jsonl`), Decoupled UI History & Sliding Context Window Hydration

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

LLM APIs are stateless. Re-submitting long transcripts (50–100 turns) on
resumption is $O(N)$ token burn and degrades TTFT to 2.5–4.0 s. A database server
(PostgreSQL, Redis, Mongo) would violate the Zero-Maintenance Mandate
([ADR-020](./2026-08-25_adr-020-zero-maintenance-mandate.md)).

## Decision

1. **Local flat JSON Lines storage (`SessionManager`).**
   `~/.sympose/sessions/<handle>_<timestamp>_<uuid>.jsonl` — line 1 metadata,
   then `{user, assistant, timestamp}` per turn. Zero DB daemons, zero
   migrations, < 0.2 ms appends.
2. **Context-window decoupling & hydration standard.** On resume the UI replays
   recent turns; `PersonaEngine.resume_session()` hydrates
   `engine.histories` with only the last **K turns** (default 6 turns / 3 pairs),
   governed by `performance.resume_context_turns: 6`. Long-term facts come from
   `_soul.md` and `_memory.md`.

Measured on resume: ~600–1,100 input tokens and < 0.6 s TTFT versus
15,000–35,000 tokens and 2.5–4.5 s for full-transcript resumption.

## Consequences

**Positive**

- Full `/history` continuity with sub-second TTFT and penny token cost.
- No database to run, migrate, or back up.

**Negative / costs**

- The model's *active* context on resume is only the last few turns; anything
  older must have been captured to `_memory.md` or it is not in-context.

## Alternatives rejected

- **A database server (PostgreSQL / Redis / Mongo) for session storage.**
  Rejected: an operational surface the single user would maintain, against the
  Zero-Maintenance Mandate.
- **Re-submitting the full transcript on every resume.** Rejected: $O(N)$ token
  burn, 2.5–4.5 s TTFT.
