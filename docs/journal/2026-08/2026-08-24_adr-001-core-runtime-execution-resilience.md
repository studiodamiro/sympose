---
title: "ADR-001 — Core Runtime & Execution Resilience"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-001 — Core Runtime & Execution Resilience

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Sympose's first runtime pass surfaced five recurring failure modes that had to be
settled before any feature work: conversational amnesia from aggressive history
truncation; unguarded Obsidian file access; hard hangs when a local Ollama model
is offline; an undisciplined build order mixing CLI, Slack, and dashboard work;
and multi-second stalls on the first token caused by Google Cloud Vertex ADC
credential discovery.

## Decision

Adopt five sub-decisions as the runtime baseline:

- **ADR-001.1 — Smart context sliding window.** Use a smart sliding window
  (15–20 turns) rather than a rigid 6-turn cutoff, preventing amnesia while
  keeping token cost bounded.
- **ADR-001.2 — Defensive Obsidian access.** Enforce directory-existence checks
  and atomic operations before reading or writing notes.
- **ADR-001.3 — Ollama offline resilience.** Wrap local model execution in
  graceful exception handlers with actionable troubleshooting guidance.
- **ADR-001.4 — Phased execution discipline.** Build in strict isolation:
  CLI first → slash commands → Slack daemon → Obsidian & dashboard.
- **ADR-001.5 — Zero-latency API key resolution.** Explicitly inject API keys
  into `litellm.completion` to bypass the ~75-second Google Cloud Vertex ADC
  discovery timeout, holding first-token streaming under 1.0s.

## Consequences

**Positive**

- Long refactor discussions retain early context without unbounded token growth.
- Vault I/O cannot corrupt notes or crash on a missing directory.
- A missing local model degrades to a clear message instead of a frozen process.
- Consistent sub-1.0s TTFT once ADC discovery is bypassed.

**Negative / costs**

- The sliding window still evicts context on very long sessions — mitigated later
  by write-through persistence ([ADR-029](./2026-08-25_adr-029-assume-interruption-write-through-state.md)).
- Explicit key injection must be repeated at every completion call site, a
  maintenance point revisited by [ADR-048](./2026-08-29_adr-048-dynamic-3-tier-model-hierarchy.md).

## Alternatives rejected

- **Rigid 6-turn history cutoff.** Rejected: caused amnesia mid-task for a
  marginal token saving.
- **Relying on Google Cloud ADC auto-discovery for credentials.** Rejected: adds
  a ~75-second first-call stall on machines without GCE metadata, fatal to the
  TTFT SLA.
