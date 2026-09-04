---
title: "ADR-018 — Multi-Model Concierge Integration (sympose_mastery)"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-018 — Multi-Model Concierge Integration (`sympose_mastery`)

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Users asking natural-language questions about model choice or provider setup
should be guided conversationally by the orchestrator rather than sent to docs.

## Decision

Add Section 7 ("Multi-Model & OpenRouter Concierge") to
`skills/sympose_mastery/SKILL.md`, guiding the orchestrator (Samantha) on
task-specific model selection (coding vs reasoning vs distillation) and
interactive `/model` command usage.

## Consequences

**Positive**

- Model selection guidance lives in a playbook, not scattered documentation.

**Negative / costs**

- The concierge is only as current as the playbook text; live pricing / context
  data still comes from `/model find`
  ([ADR-017](./2026-08-25_adr-017-openrouter-model-discovery-live-catalog.md)).

## Alternatives rejected

> Not captured in the original decision record.
