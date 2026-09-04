---
title: "ADR-015 — Multi-Provider Routing & Explicit OpenRouter Key Injection"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-015 — Multi-Provider Routing & Explicit OpenRouter Key Injection

- **Status:** Accepted — the resolution order is generalised by
  [ADR-048](./2026-08-29_adr-048-dynamic-3-tier-model-hierarchy.md)
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Sympose routes completions through `litellm`. The explicit key handshake in
`engine.py`, `workers.py`, and `memory.py` had no branch for `openrouter/`
models, which was ambiguous for users with OpenRouter credits.

## Decision

- Explicitly inject `OPENROUTER_API_KEY` at every completion call site whenever
  an `openrouter/*` model is targeted.
- Standardize model-name prefixes: `openrouter/<provider>/<model>`,
  `gemini/<model>`, `anthropic/<model>`, `openai/<model>`, `ollama/<model>`.
- Update `.env.example` and the quickstart to make OpenRouter a first-class
  provider.

## Consequences

**Positive**

- OpenRouter works out of the box with a single documented env var.
- Prefix convention makes the target provider unambiguous.

**Negative / costs**

- Key injection is duplicated per call site — the maintenance point that
  [ADR-048](./2026-08-29_adr-048-dynamic-3-tier-model-hierarchy.md) later
  addresses with a single resolution hierarchy.

## Alternatives rejected

- **Relying on LiteLLM's implicit env-var pickup alone.** Rejected: left
  `openrouter/*` routing ambiguous and produced auth failures when LiteLLM fell
  back to enterprise Vertex endpoints.
