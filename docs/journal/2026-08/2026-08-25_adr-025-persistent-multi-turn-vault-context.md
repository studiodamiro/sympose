---
title: "ADR-025 — Persistent Multi-Turn Vault Context & Conversational Intent Stripping"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-025 — Persistent Multi-Turn Vault Context & Conversational Intent Stripping

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Pre-turn retrieval injected search results on turn 1, but turn 2 ("just pick
one") rebuilt the prompt without the keywords, wiping the context and blinding
the model into hallucination. Casual compound prompts ("hey bro.. search my
daily notes about my career?") also broke sentence-start regex anchors, so the
search ran on `"hey bro"` and returned nothing.

## Decision

1. **Stateful active context.** `PersonaEngine.active_vault_ctx: Dict[str, str]`
   keeps turn-1 notes in the prompt across follow-ups until a new topic is
   queried or `/reset` is called.
2. **Greeting & preamble normalizer.** `_resolve_vault_context()` strips opening
   greetings and document boilerplate and isolates the semantic target topic
   (`career`, `health`, `interview`, ...).

## Consequences

**Positive**

- Follow-up turns ("just pick one", "show me the text") keep working against the
  retrieved notes.
- Conversational phrasing no longer defeats the search.

**Negative / costs**

- Held context must be invalidated correctly on topic change or a stale note set
  lingers.

## Alternatives rejected

> Not captured in the original decision record.
