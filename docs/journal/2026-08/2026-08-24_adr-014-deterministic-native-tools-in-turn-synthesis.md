---
title: "ADR-014 — Deterministic Native Tools & In-Turn Proactive Synthesis"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-014 — Deterministic Native Tools & In-Turn Proactive Synthesis

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

When sub-agents lacked real terminal execution, models simulated or hallucinated
plausible mock outputs. Users also had to ask multiple follow-up turns to get an
orchestrator summary of a worker run.

## Decision

- Build `sympose/native_tools.py` (`run_command`, `read_file`) providing real,
  safe `subprocess.run` execution on macOS.
- Add strict anti-simulation directives forbidding fabricated
  `> 🛠️ Sub-Agent Worker Report` badges.
- Implement **in-turn proactive synthesis** in `sympose/engine.py`: on worker
  completion, the primary agent immediately streams its executive synthesis and
  recommendations in the same response turn.

## Consequences

**Positive**

- Ground-truth tool output; no simulated results.
- One turn delivers both the tool run and the orchestrator's synthesis.

**Negative / costs**

- Native execution is a real capability that must stay inside the sandbox
  boundaries (inheritance rules added by
  [ADR-026](./2026-08-25_adr-026-subagent-worker-spatial-environment-sandbox.md)).

## Alternatives rejected

> Not captured in the original decision record.
