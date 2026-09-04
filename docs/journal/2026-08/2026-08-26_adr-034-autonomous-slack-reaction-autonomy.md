---
title: "ADR-034 — Autonomous Slack Emotion & Reaction Autonomy"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-034 — Autonomous Slack Emotion & Reaction Autonomy

- **Status:** Accepted
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace and Samantha (Engineering Partners)

## Context

Hardcoded emoji reactions (fixed checkmarks, static agent→emoji maps) make
agents rigid and rob them of expressiveness.

## Decision

- **ADR-034.1 — `[REACT: <emoji_name>]` action tag.** `REACT` regex in
  `sympose/actions.py`; syntax stripped from user-facing text, emoji intents
  passed to the Slack dispatcher.
- **ADR-034.2 — Dynamic reaction resolution in `sympose/slack.py`.** React `👀`
  on read; on completion remove it and apply the agent's chosen emoji(s), or
  fall back to `✅` if none.
- **ADR-034.3 — Soul directives for reaction autonomy.** Souls grant full
  autonomy over emotional expression and over choosing *not* to react.

## Consequences

**Positive**

- Reactions feel authentic — multiple emojis for multifaceted moments, silence
  for routine ones.
- No hardcoded emoji maps.

**Negative / costs**

- Reaction choice is model-driven and non-deterministic; occasional off-tone
  picks are possible.

## Alternatives rejected

- **Hardcoded static emoji reactions / agent→emoji mappings.** Rejected:
  artificial rigidity, no expressiveness.
