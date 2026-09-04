---
title: "ADR-022 — Local-First Hierarchical Retrieval & Noise Pruning (vault_recall)"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-022 — Local-First Hierarchical Retrieval & Noise Pruning (`vault_recall`)

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Brute-force vault search with frontier LLMs is expensive, pollutes context, and
raises privacy concerns for personal reflections. Naive local-LLM search over raw
files hits context limits and high latency.

## Decision

Establish the **3-tier triage & deep-dive retrieval funnel**:

1. **Tier 0 — deterministic filter.** Mechanical path / regex matching
   (~0.005 s, 0 tokens).
2. **Tier 1 — local LLM triage ($0).** An ephemeral worker on a local model
   (`ollama/qwen2.5:7b` or `gemma2:9b`) parses frontmatter, `## Key Decisions`,
   `## Action Items` to filter candidates and build timelines.
3. **Tier 2 — frontier deep reasoning (optional, paid).** A frontier model does
   deep synthesis using only the pre-cleaned high-signal files.

Ship `skills/vault_recall/SKILL.md` with recommended local models and deliverable
schemas.

## Consequences

**Positive**

- Most retrieval never leaves the machine or costs a token.
- Frontier spend is reserved for genuine deep-reasoning passes on clean input.

**Negative / costs**

- Three tiers to orchestrate; Tier 1 quality is bounded by the local model.

## Alternatives rejected

- **Brute-force frontier-LLM vault search.** Rejected: token cost, context
  pollution, and privacy exposure of personal notes.
- **Naive local-LLM search over raw files.** Rejected: context-limit failures
  and high latency without the deterministic pre-filter.
