---
title: "ADR-068 — Sub-Agent Worker Report Panel Styling & Redundant Synthesis Gating"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-068 — Sub-Agent Worker Report Panel Styling & Redundant Synthesis Gating

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Renumbered from ADR-062 during the 2026-09 documentation-standard conformance
pass to resolve a numbering collision; no decision content changed.

Worker tool output rendered as nested blockquotes (`> > ⚙️ Worker calling
tool:`), breaking Rich wrapping and colour hierarchy. Worker actions were
attributed to the parent agent. And after a worker rendered a note, the parent
ran an unnecessary second LLM round to re-synthesize the full note — 30+ seconds
and token waste.

## Decision

1. **Styled panel (`TerminalUI.render_worker_report_panel`).** A dedicated
   yellow-bordered Rich panel
   (`╭─ 🛠️ SUB-AGENT WORKER REPORT • #skills ─╮`) with tool calls
   (`⚙️ Tool: read_file(...)`) and syntax-highlighted deliverables.
2. **Worker actor attribution.** Sub-agent actions are attributed to
   `"Sub-Agent Worker"` (`> 📄 Sub-Agent Worker rendered note to Terminal:`).
3. **Redundant synthesis gating (`sympose/engine.py`).** If a worker already
   rendered the note (`has_rendered_note`), the parent skips the second LLM
   completion.

## Consequences

**Positive**

- Worker output is legible and correctly attributed; instant turnaround with no
  duplicate synthesis round.

**Negative / costs**

- Skipping the second round means the parent adds no extra commentary when a
  worker has already rendered the deliverable.

## Alternatives rejected

> Not captured in the original decision record.
