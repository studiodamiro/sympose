---
title: "ADR-060 — Three-Way Terminal Render Mode Knob (performance.render_mode)"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-060 — Three-Way Terminal Render Mode Knob (`performance.render_mode`)

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Sympose had no render-mode concept: terminal output was either Rich-formatted or
raw stdout, with no user control over the trade-off between streaming
transparency and full Markdown rendering. A latent `UnboundLocalError` on
`first_chunk` also lived in the streaming loop.

## Decision

Three modes under `config.yaml → performance.render_mode`:

| Mode | Behaviour | Use case |
|---|---|---|
| `hybrid` | Live streaming with Rich badge rendering intercepted mid-stream | Default |
| `buffered` | Spin during generation, then render the full response with Rich Markdown | Visual polish |
| `raw` | Pure stdout token streaming, no Rich panels | Debugging, piping, transparency |

Wired into `sympose/cli.py` (per-turn branch, `UnboundLocalError` fixed),
`sympose/ui.py` (`select_render_mode()` cyan `box.ROUNDED` menu),
`sympose/commands.py` (`/render [hybrid|buffered|raw]`, persisted to
`config.yaml`), and `sympose/completer.py`.

## Consequences

**Positive**

- One knob controls all terminal output behaviour, switchable mid-session via
  `/render` with no restart.
- Fixes the pre-existing `first_chunk` `UnboundLocalError`.

**Negative / costs**

- Three code paths in the streaming loop to keep in step.

## Alternatives rejected

> Not captured in the original decision record.
