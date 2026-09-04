---
title: "ADR-066 — Terminal Markdown Presentation Standard (vault_recall) & Beautified Sub-Agent Orchestration"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-066 — Terminal Markdown Presentation Standard (`vault_recall`) & Beautified Sub-Agent Orchestration (`subagent_spawn`)

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Renumbered from ADR-060 during the 2026-09 documentation-standard conformance
pass to resolve a numbering collision; no decision content changed. (The
`ADR-060 – ADR-063` numbers are kept by the *Terminal Render Mode Knob* set,
whose introducing commit named those topics.)

Agents lacked codified guidance on how to format recalled Markdown notes and
citations in the terminal, producing inconsistent quote styles. Sub-agent worker
badges and web-search summaries were raw single-line quotes with no visual
hierarchy.

## Decision

1. **Codified terminal Markdown standard in `skills/vault_recall/SKILL.md`
   (Section 4).** The 3-tier box anatomy: header metadata bar, frontmatter
   `#tags`, syntax-highlighted clean body with rotated T-junction dividers.
2. **Dedicated `skills/subagent_spawn/SKILL.md`.** The zero-pollution
   orchestration law, `[SPAWN_WORKER]` syntax, skill/MCP mounting rules, and
   parent-synthesis directives.
3. **Beautified worker & search reports (`sympose/actions.py`).** `SPAWN_WORKER`
   and `WEB_SEARCH` output emit styled blockquotes with Markdown headers
   (`### 🛠️ Sub-Agent Worker Report`), skill chips, and structured task
   metadata.

## Consequences

**Positive**

- Recalled notes and worker reports render with a consistent, legible structure.

**Negative / costs**

- The presentation standard is playbook text agents must follow, not enforced
  formatting.

## Alternatives rejected

> Not captured in the original decision record.
