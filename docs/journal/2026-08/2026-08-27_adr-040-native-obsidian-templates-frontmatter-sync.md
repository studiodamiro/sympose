---
title: "ADR-040 — Native Obsidian Templates/ Engine & Dynamic Frontmatter Tag Syncing"
created: 2026-08-27
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-040 — Native Obsidian `Templates/` Engine & Dynamic Frontmatter Tag Syncing

- **Status:** Accepted
- **Date:** 2026-08-27
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Agent-written notes and daily logs were missing the custom YAML frontmatter
defined in the user's real Obsidian vault templates (`Templates/`). Appending
reflections also left frontmatter `tags:` out of sync with new topics.

## Decision

- `VaultManager.get_template_for_path()` inspects `/Templates/` and maps
  destination paths to templates (`Daily template.md`, `Thoughts template.md`,
  `People template.md`, ...), interpolating `{{date}}`, `{{time}}`, `{{title}}`,
  `{{date:YYYY}}`.
- `VaultManager._sync_frontmatter_tags()` merges reflection topic tags into the
  top-level YAML `tags:` array on daily-note appends without corrupting other
  keys.

## Consequences

**Positive**

- New notes match the user's authentic template schema.
- Frontmatter `tags:` stays current as reflections are appended.

**Negative / costs**

- Template resolution depends on filename conventions in `Templates/`; an
  unrecognised name falls back to a generic note.

## Alternatives rejected

> Not captured in the original decision record.
