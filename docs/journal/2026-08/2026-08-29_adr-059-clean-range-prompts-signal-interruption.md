---
title: "ADR-059 — Repository-Wide Clean Range Prompts & Graceful Asynchronous Signal Interruption (SIGINT)"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-059 — Repository-Wide Clean Range Prompts & Graceful Asynchronous Signal Interruption (`SIGINT` / `Ctrl+C`)

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Rich's `Prompt.ask` prints every member of `choices` in the prompt string — for
session selection that dumped all 30-character session IDs. And `Ctrl+C` during
thinking or streaming raised an unhandled `KeyboardInterrupt` that killed the
whole process.

## Decision

1. **Clean range prompts.** `show_choices=False, show_default=False` on all
   `Prompt.ask` calls in `sympose/ui.py` and `sympose/bootstrap.py`; human
   ranges instead — `Select session to resume [1-5, Enter for [1], 'q' to
   cancel]:`, `Select note [1-11, 'o <#>' to open, 'q' to exit]:`.
2. **Three-tier graceful signal trapping (`sympose/cli.py`).** Generation tier —
   trap in `chat_stream()`, print `^C [Interrupted @handle]`, return to prompt;
   command tier — `^C [Command cancelled]`; prompt tier — stay in the REPL with
   a hint.

## Consequences

**Positive**

- Prompts are readable regardless of choice-set size.
- `Ctrl+C` interrupts the current turn instead of crashing the session.

**Negative / costs**

- Range hints are hand-written per prompt — they must be kept in sync with the
  actual accepted inputs.

## Alternatives rejected

- **Rich's default `Prompt.ask` choice rendering.** Rejected: dumps every choice
  string (including full session IDs) into the prompt line.
