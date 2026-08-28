---
name: "strategic_analysis"
title: "Strategic Decision & Tradeoff Analysis"
description: "Rigorous mental models for evaluating architectural, product, or organizational tradeoffs without speculation."
tags:
  - strategy
  - decision-making
  - analysis
---

# 🎯 Strategic Analysis Protocol

When evaluating an ambiguous strategic decision, proposal, or architecture direction:

## 1. Evaluation Heuristics
- **Reversibility Test (Bezos Door Heuristic)**: Is this a One-Way Door (irreversible, high blast radius) or a Two-Way Door (cheap to reverse)?
- **Second-Order Effects**: What downstream behavior or incentives does this change introduce?
- **Opportunity Cost**: What are we implicitly choosing *not* to build by committing to this path?

## 2. Mandatory Output Contract (Deliverable Structure)
Every strategic evaluation MUST include these four explicit sections:
1. **The Core Tradeoff**: The fundamental tension summarized in 1 sentence.
2. **Option Comparison Matrix**: Minimum 2 distinct paths comparing latency, complexity, cost, and maintenance.
3. **Decisive Recommendation**: An unvarnished, opinionated recommendation with rationale.
4. **Kill Criteria / Reversal Triggers**: Measurable metrics or conditions under which we should abort or pivot.
