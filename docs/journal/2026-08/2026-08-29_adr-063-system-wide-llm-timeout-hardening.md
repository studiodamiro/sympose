---
title: "ADR-063 — System-Wide LLM Timeout Hardening"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-063 — System-Wide LLM Timeout Hardening

- **Status:** Accepted — hardens the background calls from
  [ADR-008](./2026-08-24_adr-008-heuristic-gated-shadow-memory-extractor.md),
  [ADR-019](./2026-08-25_adr-019-automated-memory-compaction-distillation.md),
  and
  [ADR-005](./2026-08-24_adr-005-config-yaml-session-summarization-memory.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Three background LLM call sites hardcoded timeouts and ignored `config.yaml`:
`compactor.py` (10.0s), `memory.py` heuristic extractor (5.0s), `memory.py`
session archivist (10.0s). Under a cold Gemini connection the 10.0s ceiling was
regularly breached, causing `litellm.Timeout` compaction failures and silent
memory-extraction drops.

## Decision

Every LLM call site reads
`float(config_manager.get("performance.request_timeout", 30.0))` — no site
hardcodes a timeout. Global default raised `10.0s → 30.0s` across `config.yaml`,
`sympose/config.py` (global + `DEFAULT_CONFIG`), and `sympose/engine.py`
(`_build_kwargs` fallback). `local_request_timeout` (Ollama) raised
`60.0s → 120.0s`. Tunable at runtime via
`/config set performance.request_timeout 45.0`.

## Consequences

**Positive**

- Memory compaction, extraction, and session summarization are resilient to
  normal network jitter.
- One knob governs every timeout, adjustable without a restart.

**Negative / costs**

- A higher ceiling means a genuinely stuck call now blocks its background thread
  for up to 30 s (120 s local) before failing.

## Alternatives rejected

> Not captured in the original decision record.
