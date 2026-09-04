---
title: "ADR-019 — Automated Memory Compaction & Distillation Protocol"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-019 — Automated Memory Compaction & Distillation Protocol

- **Status:** Accepted — the compaction call's timeout and write-race handling
  are hardened by
  [ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md)
  (Standard 5) and
  [ADR-063](./2026-08-29_adr-063-system-wide-llm-timeout-hardening.md)
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`_memory.md` files accumulate duplicate assertions, superseded state (outdated
codes, abandoned frameworks), and formatting noise, bloating system-prompt
pre-fills and diluting attention.

## Decision

- Build `sympose/compactor.py` (`MemoryCompactor`) running LLM distillation
  passes over memory files.
- `config.yaml`: `memory.compaction_threshold: 25`, `memory.auto_compact: true`.
- Hook `MemoryCompactor.check_and_compact_async` into `append_memory()` so
  compaction runs on a background daemon thread without blocking chat turns.
- Add `/compact` and `/compact shared` slash commands with tab completion.

## Consequences

**Positive**

- Working memory stays high-density; ~31–38% line-count reductions measured on
  seeded files.
- Runs automatically once a file crosses the threshold.

**Negative / costs**

- Background compaction can race a foreground `append_memory()` write — the risk
  that Standard 5 of ADR-038 later closes with a mutex + snapshot reconcile.
- It is the most expensive LLM call in the system; a too-tight timeout drops it
  silently (fixed by ADR-063).

## Alternatives rejected

> Not captured in the original decision record.
