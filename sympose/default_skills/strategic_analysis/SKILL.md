---
name: "strategic_analysis"
title: "Strategic Decision & Tradeoff Analysis"
description: "Mental models for evaluating architectural, product, or organisational tradeoffs without speculation."
tags:
  - strategy
  - decision-making
  - analysis
---

# Strategic Analysis Protocol

When evaluating an ambiguous decision, proposal, or architecture direction:

## Heuristics

- **Reversibility (Bezos door test)**: one-way door (irreversible, high blast
  radius) or two-way door (cheap to reverse)?
- **Second-order effects**: what downstream behaviour or incentives does this
  change create?
- **Opportunity cost**: what are we implicitly choosing *not* to build?

## Output contract

Every evaluation includes these four sections:

1. **The core tradeoff** — the fundamental tension in one sentence.
2. **Option comparison** — ≥2 distinct paths compared on latency, complexity,
   cost, maintenance.
3. **Recommendation** — unvarnished and opinionated, with rationale.
4. **Kill criteria** — measurable conditions under which to abort or pivot.
