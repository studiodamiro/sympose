---
title: "ADR-007 — Strict Memory Grounding, Anti-Hallucination & Honest Ignorance"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-007 — Strict Memory Grounding, Anti-Hallucination & Honest Ignorance Standard

- **Status:** Accepted — extended by
  [ADR-024](./2026-08-25_adr-024-ground-truth-sovereignty-axiom.md),
  [ADR-030](./2026-08-26_adr-030-high-density-folder-digests-zero-delay.md), and
  [ADR-035](./2026-08-26_adr-035-evidence-based-grounding-epistemic-humility.md)
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Base LLMs default to agreeableness and conversational fabrication on memory
queries — inventing past study plans or user facts that were never recorded.
Separately, local macOS machines hung for 10s–300s on unroutable GCE metadata IP
probes (`169.254.169.254`).

## Decision

- Enshrine a zero-tolerance anti-hallucination protocol for working memory: an
  agent states honest ignorance rather than inventing a fact, decision, or plan
  not present in its memory files or the turn context.
- Set `NO_GCE_CHECK=True` and `GOOGLE_CLOUD_DISABLE_METADATA=true` to eliminate
  the metadata-probe socket hang on macOS.

## Consequences

**Positive**

- Memory answers are trustworthy: absence of a fact is reported, not filled in.
- The 10s–300s startup / first-call hang on macOS is gone.

**Negative / costs**

- Agents will more often say "that is not in my records" — correct, but blunter
  than a confident guess.

## Alternatives rejected

> Not captured in the original decision record.
