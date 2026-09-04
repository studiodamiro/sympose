---
title: "ADR-006 — Autonomous Soul & Memory Bootstrapping"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-006 — Autonomous Soul & Memory Bootstrapping (Zero-Friction Agent Creation)

- **Status:** Accepted — starter-seed policy narrowed to Samantha-only by
  [ADR-046](./2026-08-29_adr-046-samantha-only-clean-slate-persona-genesis.md);
  the bootstrapping mechanism itself is unchanged
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Creating a new agent required hand-writing three synchronized files
(`.yaml`, `_soul.md`, `_memory.md`). Hardcoded thinking phrases in `cli.py` also
prevented user-defined agents from having custom status spinners.

## Decision

- Move `thinking_phrases` into the YAML manifest (UI-only, no prompt-token cost).
- Add `bootstrap_missing_artifacts`: dropping a minimal 4-line YAML
  (`name`, `handle`, `title`, `model`) auto-generates
  `profiles/{handle}_soul.md`, `profiles/{handle}_memory.md`, and default
  thinking phrases on launch.
- Generated files stay plain Markdown on disk, editable at any time.

## Consequences

**Positive**

- A working agent is one short YAML file away.
- No loss of customizability — every generated file remains user-editable.

**Negative / costs**

- Auto-generation from a terse manifest can produce a bland default soul until
  the user edits it.

## Alternatives rejected

- **Continuing to require three hand-authored files per agent.** Rejected
  (reconstructed from the journal narrative): the synchronization burden was
  friction the hub is meant to remove.
