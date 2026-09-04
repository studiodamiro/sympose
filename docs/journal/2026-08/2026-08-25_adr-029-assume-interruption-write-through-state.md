---
title: "ADR-029 — Assume Interruption Meta-Directive & Write-Through State Checkpointing"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-029 — Assume Interruption Meta-Directive & Write-Through State Checkpointing

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

LLM agents assume conversational history persists forever, so intermediate
decisions, test results, and user constraints stay trapped in a volatile token
buffer. Sympose's 15-turn sliding window
([ADR-001](./2026-08-24_adr-001-core-runtime-execution-resilience.md)), `/clear`,
and cross-client switches (terminal ↔ IDE ↔ Slack mobile) all lose that state.

## Decision

Inject the universal **"ASSUME INTERRUPTION"** meta-directive into the prompt
engine and every soul:

> "Your context window is bounded and might be reset at any moment... Proactively
> checkpoint architectural decisions, milestone progress, and user facts using
> `[REMEMBER: <fact>]` or `[WRITE_NOTE: <filename> | <content>]`."

Agents emit checkpoint tags on reaching a milestone rather than waiting for
`/save` or exit; progress is on disk before the next step runs.

## Consequences

**Positive**

- Unexpected termination loses nothing — the next session recovers from memory
  files on turn 1.
- Work started in one client is immediately visible in another.
- Zero runtime latency, zero new dependencies.

**Negative / costs**

- More frequent `[REMEMBER]` / `[WRITE_NOTE]` emissions — noisier badge output,
  more small memory writes (deduplicated by
  [ADR-019](./2026-08-25_adr-019-automated-memory-compaction-distillation.md)).

## Alternatives rejected

- **Persisting state only on explicit `/save` or session exit.** Rejected: any
  crash, truncation, or client switch before that point loses the work.
