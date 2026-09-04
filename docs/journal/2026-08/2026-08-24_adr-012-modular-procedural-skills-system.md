---
title: "ADR-012 — Modular Procedural Skills System (SKILL.md)"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-012 — Modular Procedural Skills System (`SKILL.md`)

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Agents needed reusable domain heuristics (Git hygiene, code review, strategic
decision-making) without bloating their core identity souls (`_soul.md`).

## Decision

Adopt the open `skills/<skill_name>/SKILL.md` format: YAML frontmatter plus a
Markdown playbook body.

- `sympose/skills.py` (`SkillManager`) discovers, parses, and formats skills into
  system-prompt blocks.
- Profiles opt in with `skills: [git_workflow, code_review]` in
  `profiles/*.yaml`.
- Ship starter skills: `git_workflow`, `code_review`, `system_architecture`,
  `strategic_analysis`.

## Consequences

**Positive**

- Procedural know-how is composable and shared across agents without touching
  souls.
- Skill files are plain Markdown, versionable and user-editable.

**Negative / costs**

- Each mounted skill adds prompt tokens; skill sprawl must be watched per agent.

## Alternatives rejected

> Not captured in the original decision record.
