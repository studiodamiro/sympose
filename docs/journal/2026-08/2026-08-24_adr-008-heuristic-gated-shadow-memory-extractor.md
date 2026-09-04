---
title: "ADR-008 — Heuristic-Gated Shadow Memory Extractor"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-008 — Heuristic-Gated Shadow Memory Extractor (Zero-Friction Autonomic Persistence)

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Requiring the user to say "remember" or run `/remember` imposes artificial
cognitive friction. Naively calling an extractor LLM on every turn roughly
doubles token cost and risks API rate limits.

## Decision

- **Heuristic regex filter gate.** Evaluate each incoming user turn in
  < 0.01 ms; bypass greetings, short Q&A, and casual chatter with zero extra
  tokens.
- **Detached async daemon thread.** For turns that pass the gate, spawn
  `threading.Thread(daemon=True)` running background distillation on a fast
  model — 0.00 s added to TTFT.
- **Memory deduplication.** `append_memory()` deduplicates lines so repeated
  facts do not accumulate.
- Publish `docs/wiki/memory/architecture-standard.md` as the reference.

## Consequences

**Positive**

- Durable facts are captured with no keyword ritual and no latency cost.
- ~80%+ of chit-chat turns skip the extractor entirely.

**Negative / costs**

- A regex gate has false negatives — some genuinely memorable turns are skipped
  until restated.
- Background extraction is best-effort; a swallowed exception drops silently
  (later hardened by
  [ADR-063](./2026-08-29_adr-063-system-wide-llm-timeout-hardening.md)).

## Alternatives rejected

- **Calling the extractor on every turn.** Rejected: doubles token cost and
  invites rate limiting for a marginal recall gain over the gated approach.
- **Requiring explicit `/remember` / "remember that".** Rejected: the friction
  it adds is exactly what the hub is meant to eliminate.
