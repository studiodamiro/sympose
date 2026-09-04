---
title: "ADR-043 — Three-Layer Architectural Separation (Soul vs Skill vs System Physics)"
created: 2026-08-27
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-043 — Three-Layer Architectural Separation (Soul vs. Skill vs. System Physics)

- **Status:** Accepted
- **Date:** 2026-08-27
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Persona soul files were accumulating 40+ lines of operational rules (Slack
etiquette, group moderation, YAML schemas, grounding rules), diluting each
agent's character voice.

## Decision

Three strictly separated layers:

1. **Soul (`profiles/*_soul.md`)** — *who the agent is*: personality, demeanor,
   voice, emotional depth, cadence, wit.
2. **Skills (`skills/*/SKILL.md`)** — *what the agent does*: Slack etiquette,
   moderation, vault-write protocols, web-search playbooks.
3. **Workspace rules (`workspace_rules.md`)** — the *universal physics of
   Sympose*: amnesia boundary, zero guessing, assume interruption,
   anti-helplessness.

## Consequences

**Positive**

- Souls read as characters again; operational rules live once, centrally.
- Adding a rule touches one layer, not every soul.

**Negative / costs**

- Contributors must know which layer a new directive belongs in.

## Alternatives rejected

> Not captured in the original decision record.
