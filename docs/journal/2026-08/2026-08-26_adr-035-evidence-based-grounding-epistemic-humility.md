---
title: "ADR-035 — Evidence-Based Grounding & Epistemic Humility Standard"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-035 — Evidence-Based Grounding & Epistemic Humility Standard

- **Status:** Accepted — extends
  [ADR-007](./2026-08-24_adr-007-memory-grounding-anti-hallucination.md) /
  [ADR-024](./2026-08-25_adr-024-ground-truth-sovereignty-axiom.md)
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace and Samantha (Engineering Partners)

## Context

"Eager Assumption Bias": on ambiguous pronouns ("is this appropriate?", "what do
you think of that layout?"), models pull an arbitrary recent memory file and
generate unsolicited plans instead of asking for clarification.

## Decision

- **ADR-035.1 — "No evidence = no assumptions".** On ambiguous subjects ("this",
  "that", "the thread") with no explicit antecedent, agents must pause and ask a
  clarifying question before executing or planning.
- **ADR-035.2 — Channel & thread boundary awareness.** Agents have visibility
  only into the active thread; questions about another channel require the user
  to paste the context.
- **ADR-035.3 — Universal soul & rule injection.** Injected into all souls and
  `.agents/rules/identity.md`.

## Consequences

**Positive**

- Fewer confidently-wrong tangents; the agent asks instead of guessing.

**Negative / costs**

- More clarifying questions on genuinely ambiguous input — a deliberate trade
  against fabrication.

## Alternatives rejected

> Not captured in the original decision record.
