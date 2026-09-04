---
title: "ADR-047 — Standardized Sympose CLI Design System (SYMPOSE_THEME) & Typography Standard"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-047 — Standardized Sympose CLI Design System (`SYMPOSE_THEME`) & Typography Standard

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Slash-command output (`/help`, `/model`, `/config`) streamed raw Markdown
asterisks and backticks to stdout with misleading persona speaker headers
(`Grace Hopper: **Available Commands**`).

## Decision

1. **Thematic palette (`SYMPOSE_THEME`).** Semantic tokens — brand headers
   (`bold cyan`), category subheaders (`bold white`), handles / code chips
   (`bold yellow` / `bright_yellow on grey11`), status (`bold green` /
   `bold red`), vault paths (`magenta`), metadata (`dim cyan` / `dim white`).
2. **Surface standards.** Panels / modals use `box=ROUNDED`, `dim cyan` borders,
   `(1, 2)` padding; `/switch` uses right-aligned indexes and model chips.
3. **Structured command formatting.** `/help`, `/model`, `/config`, `/skills`
   render via `rich.markdown.Markdown` with section headings and no false
   speaker prefixes.

## Consequences

**Positive**

- Consistent, GitHub-CLI-class visual language across every system command.
- No misleading "persona said this" headers on system output.

**Negative / costs**

- New command surfaces must adopt the token set to stay consistent.

## Alternatives rejected

> Not captured in the original decision record.
