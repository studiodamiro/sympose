---
title: "ADR-016 — Skill-Driven Sub-Agent Worker Model Auto-Resolution"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-016 — Skill-Driven Sub-Agent Worker Model Auto-Resolution

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Specialist skills (`code_review`, `system_architecture`) perform best with
high-precision models; simple lookup skills can run on lightweight ones. Workers
had no way to pick the right model automatically.

## Decision

A 4-tier worker model resolution hierarchy in `sympose/workers.py`:

1. Explicit task override — `WorkerTask(..., model="...")`.
2. Skill frontmatter — first entry of `recommended_models:` in the skill's
   `SKILL.md`.
3. Global env var — `DEFAULT_MODEL` in `.env`.
4. System fallback — a fast default model.

## Consequences

**Positive**

- Each skill runs on an appropriate model with no per-call configuration.
- Overrides remain available at the top of the chain.

**Negative / costs**

- A recommended model in a skill file can drift from installed local weights
  (fuzzy alignment added by
  [ADR-026](./2026-08-25_adr-026-subagent-worker-spatial-environment-sandbox.md)).

## Alternatives rejected

> Not captured in the original decision record.
