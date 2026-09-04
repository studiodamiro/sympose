---
title: "ADR-037 — Pure Declarative Markdown-Driven Prompting & Zero-Code Injections"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-037 — Pure Declarative Markdown-Driven Prompting & Zero-Code Injections

- **Status:** Accepted
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace and Samantha (Engineering Partners)

## Context

`sympose/*.py` carried 120+ lines of hardcoded English prompt strings —
spatial coordinates and grounding rules in `profiles.py`, extraction /
summarization prompts in `memory.py`, worker directives in `workers.py`. Tuning
agent instructions meant editing Python.

## Decision

- **ADR-037.1 — 100% hands-off Python.** Python files are transport runners and
  file assemblers only; zero hardcoded prompt text.
- **ADR-037.2 — Universal `workspace_rules.md`.** All global spatial rules,
  anti-hallucination protocols, and autonomic tags (`[REMEMBER]`, `[WRITE_NOTE]`,
  `[DAILY_NOTE]`, `[SPAWN_WORKER]`, `[CONFIG_SET]`, `[CREATE_PERSONA]`,
  `[DELETE_PERSONA]`) live in the root `workspace_rules.md`; `ProfileManager`
  substitutes runtime variables (`{{workspace_root}}`, `{{master_vault_path}}`,
  `{{user}}`, `{{handle}}`, ...).
- **ADR-037.3 — Modular `prompts/` directory.** `prompts/memory_extraction.md`,
  `prompts/session_summary.md`, `prompts/worker_system.md`.

## Consequences

**Positive**

- Agent behaviour is tuned by editing Markdown, not source.
- `sympose/profiles.py` and `memory.py` line counts drop sharply.

**Negative / costs**

- A missing or misnamed template file is now a runtime failure surface
  (anchored-path lookup added by
  [ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md)
  Standard 3).

## Alternatives rejected

> Not captured in the original decision record.
