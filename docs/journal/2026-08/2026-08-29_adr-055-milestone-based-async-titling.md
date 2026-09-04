---
title: "ADR-055 — Milestone-Based Asynchronous Titling & Generic Prompt Filtering"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-055 — Milestone-Based Asynchronous Titling & Generic Prompt Filtering

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Freezing a conversation title at turn 1 locks in generic greetings ("hi",
"hey @samantha"). Re-titling with an LLM every turn burns ~10,000 tokens per
session and thrashes the `/history` UI.

## Decision

A 3-tier milestone titling pipeline in `SessionManager`:

1. **Turn 1 heuristic gate.** Regex on generic greetings (length < 12) → keep
   `"New Conversation"` until the first substantive prompt.
2. **Turn 3 one-shot background pass.** At `turns_count == 3` a detached daemon
   thread runs a ~20-token synthesis for a 4–6 word headline
   (~400 in / ~8 out, < $0.000005).
3. **Exit / save sync.** `/save` or exit writes the final title back into the
   `.jsonl` header at $0.

## Consequences

**Positive**

- Titles are stable and semantically accurate; no session stays titled "hi".
- Exactly one background pass per conversation.

**Negative / costs**

- A conversation that ends before turn 3 keeps `"New Conversation"` unless the
  turn-1 substantive prompt upgraded it.

## Alternatives rejected

- **Freezing the title at turn 1.** Rejected: locks in "hi" / "quick question".
- **Re-titling with an LLM on every turn.** Rejected: ~10,000 tokens per session
  and constant UI title thrashing.
