---
title: "ADR-048 — Dynamic 3-Tier Model Hierarchy & Runtime Fallback Architecture"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-048 — Dynamic 3-Tier Model Hierarchy & Runtime Fallback Architecture

- **Status:** Accepted — generalises the per-call key injection of
  [ADR-015](./2026-08-25_adr-015-multi-provider-routing-openrouter-key-injection.md);
  `DEFAULT_CHAT_MODEL` / `DEFAULT_WORKER_MODEL` are later centralised by
  [ADR-065](./2026-08-30_adr-065-mcp-client-threading-logging-standard.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Hardcoded model strings (`gemini/gemini-3.5-flash-lite`) caused 401 auth
exceptions when LiteLLM fell back to enterprise Google Vertex endpoints.

## Decision

A strict **3-tier model resolution hierarchy**:

1. **Tier 1 — global system default.** `.env` `DEFAULT_MODEL`.
2. **Tier 2 — per-persona specialization.** `profiles/<handle>.yaml` `model:`.
3. **Tier 3 — summarizer & live overrides.** `config.yaml`
   (`session.exit_behavior.summarization_model`), `/model <id>`, `/setup`.

## Consequences

**Positive**

- No hardcoded model lock-in; a bad global default is overridable at three
  levels.
- Removes the Vertex-fallback 401 class of failures.

**Negative / costs**

- Three sources to reason about when a model resolves unexpectedly.

## Alternatives rejected

- **Hardcoded model identifiers in source.** Rejected: caused 401s on enterprise
  Vertex fallback and required a code edit to change a model.
