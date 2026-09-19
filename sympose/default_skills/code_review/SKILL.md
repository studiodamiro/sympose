---
name: "code_review"
title: "Zero-Bloat Code Review & Static Heuristics"
description: "Code review focused on simplicity, error boundaries, concurrency, and cognitive load."
tags:
  - engineering
  - quality
  - review
---

# Zero-Bloat Code Review

Apply scrutiny across four pillars:

**1. Simplicity / bloat** — Solvable with stdlib instead of a new dependency?
Cut speculative generality (YAGNI): no factory wrappers or adapter layers with a
single implementation. Keep complexity low — flat over nested, early returns over
`if/else` ladders.

**2. Robustness** — No bare `except Exception: pass` (catch specific cases, log
them). File handles, cursors, and connections use context managers. Validate
types and bounds at entry points.

**3. Concurrency / state** — Look for shared mutable state, unprotected globals,
un-synchronised increments. Retryable operations (webhooks, payments) must be
idempotent.

**4. Output** — Report in tiers:
1. **Blockers** — bugs, security, races, data loss.
2. **Warnings** — perf bottlenecks, unhandled edges, missing tests.
3. **Suggestions** — naming, minor refactors, style.
