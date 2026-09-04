---
title: "ADR-062 — render_mode: raw Panel Suppression in the Action Executor"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-062 — `render_mode: raw` Panel Suppression in the Action Executor

- **Status:** Accepted — depends on
  [ADR-060](./2026-08-29_adr-060-terminal-render-mode-knob.md); suppresses the
  panel from
  [ADR-058](./2026-08-29_adr-058-multisectionpanel-in-terminal-note-viewer.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`render_mode: raw` should give pure terminal transparency, but `[READ_NOTE]`
actions in `sympose/actions.py` unconditionally called
`TerminalUI.render_vault_note_panel()` regardless of render mode.

## Decision

Before rendering any Rich panel for a `[READ_NOTE]` / `[VIEW_NOTE]` action,
`actions.py` reads `config_manager.get("performance.render_mode")`. If `raw`,
`console=None` is passed and the panel is suppressed; in `hybrid` / `buffered`
the full `MultiSectionPanel` renders as before.

## Consequences

**Positive**

- `render_mode: raw` is now honoured end-to-end, including action output.

**Negative / costs**

- Every new Rich-rendering action path must add the same render-mode check.

## Alternatives rejected

> Not captured in the original decision record.
