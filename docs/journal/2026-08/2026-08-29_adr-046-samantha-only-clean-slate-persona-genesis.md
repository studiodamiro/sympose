---
title: "ADR-046 — Samantha-Only Clean Slate & Dynamic Autonomic Persona Genesis"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-046 — Samantha-Only Clean Slate & Dynamic Autonomic Persona Genesis (`[CREATE_PERSONA]`)

- **Status:** Accepted — narrows the starter-seed policy of
  [ADR-006](./2026-08-24_adr-006-autonomous-soul-memory-bootstrapping.md); the
  fenced-tag parsing bug is fixed by
  [ADR-049](./2026-08-29_adr-049-code-fence-action-tag-parsing.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Early prototypes seeded multiple hardcoded personas (Grace, Anaïs) into starter
assets and skills, causing LLM confusion and role hallucinations on fresh
installs.

## Decision

1. **Samantha-only starter seed.** First run seeds only Samantha
   (`samantha.yaml`, `_soul.md`, `_memory.md`, `user_profile.md`,
   `_shared_memory.md`, `config.yaml`, `workspace_rules.md`).
2. **Generic heuristic playbooks.** Purge hardcoded agent names from `skills/`
   and `prompts/`; use `@specialist` / `@peer` patterns.
3. **`[CREATE_PERSONA: <handle> | <manifest>]` tag.** Samantha emits it from a
   natural-language request; `ActionProcessor` writes
   `profiles/<handle>.yaml` and bootstraps `_soul.md` / `_memory.md` in < 3 ms,
   mounting `@<handle>` into `/switch`.
4. **Baseline fallback guarantee.** Omitted `model:` / `skills:` are filled by
   `bootstrap_missing_artifacts` with `DEFAULT_MODEL` and the baseline trifecta
   (`vault_recall`, `vault_write`, `web_search`).

## Consequences

**Positive**

- Fresh installs have exactly one clear orchestrator; no role confusion.
- New specialists are created conversationally in milliseconds.

**Negative / costs**

- Fenced `[CREATE_PERSONA]` tags were initially swallowed by code-block masking
  (ADR-049).

## Alternatives rejected

- **Shipping multiple hardcoded personas in the starter seed.** Rejected:
  demonstrated LLM confusion and role hallucination on fresh installs.
