---
title: "ADR-058 — MultiSectionPanel In-Terminal Note Viewer with Inline T-Junction Box Dividers"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-058 — `MultiSectionPanel` In-Terminal Note Viewer with Inline T-Junction Box Dividers

- **Status:** Accepted — `render_mode: raw` suppression added by
  [ADR-062](./2026-08-29_adr-062-render-mode-raw-panel-suppression.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Users had to leave the terminal for a GUI app to read a matched note. A standard
Rich `Panel(Group(header, Rule(), fm, Rule(), body))` puts horizontal rules
inside the interior padding, producing detached lines that do not meet the outer
border.

## Decision

1. **Custom `MultiSectionPanel` renderable.** Native Rich renderable over
   `Segment` streaming and `options.max_width`, drawing a single-frame box with
   inline section titles in the borders: top `╭─ 📄 NOTE: … ─╮`, section dividers
   `├─ 🏷️ FRONTMATTER ─┤` and `├───┤` that physically meet both walls, three
   inner sections (metadata stats, colorized frontmatter, syntax-highlighted
   body).
2. **Interactive quick-nav loop (`interactive_vault_browser`).** Jump between
   notes by number `1-N`, open in Obsidian (`o`), back to list (`b`), quit
   (`q`) — no re-running the search.

## Consequences

**Positive**

- Full note reading stays in the terminal, with pixel-accurate box borders.
- Browsing a result set is a loop, not repeated commands.

**Negative / costs**

- A hand-rolled Rich renderable is more code to maintain than a stock `Panel`.

## Alternatives rejected

- **Stock `Panel(Group(header, Rule(), …))`.** Rejected: `Rule()` renders
  detached interior lines that never connect to the panel border, failing the
  requested T-junction look.
