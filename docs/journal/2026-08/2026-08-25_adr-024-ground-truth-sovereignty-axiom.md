---
title: "ADR-024 — The Ground-Truth Sovereignty Axiom & Anti-Simulation Directives"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-024 — The Ground-Truth Sovereignty Axiom & Anti-Simulation Directives

- **Status:** Accepted — extends
  [ADR-007](./2026-08-24_adr-007-memory-grounding-anti-hallucination.md)
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

When small open-weight models (Gemma 2 9B) lack grounded context, RLHF
"helpfulness" drives them to fabricate plausible journal entries (hallucinated
dates like `2017-10-26`) or to roleplay progress markers (`*[Begins
retrieval]*`) instead of emitting real data.

## Decision

1. **Ground-Truth Sovereignty Axiom.** Markdown documents on disk are the
   sovereign single source of truth; models are ephemeral cognitive processors
   reading the file data bus.
2. **Verbatim Quotation Protocol.** Historical notes are quoted with the user's
   exact words in Markdown blockquotes (`>`).
3. **Zero-Fabrication Directives.** If a note is not on disk or in the pre-turn
   payload, the model states honest ignorance immediately — no invented text, no
   simulated actions.

## Consequences

**Positive**

- Local 9B models retrieve and quote real notes with no simulated markers
  (verified against a real daily note).
- The axiom becomes the reference for later anti-simulation work (ADR-030,
  ADR-036).

**Negative / costs**

- Requires strong, repeated prompt directives across souls, skills, and
  workspace rules to hold small models in line.

## Alternatives rejected

> Not captured in the original decision record.
