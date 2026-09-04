---
title: "ADR-069 — Live Stream Markdown Parsing for Real-Time Badges & Sub-Agent Reports"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-069 — Live Stream Markdown Parsing for Real-Time Badges & Sub-Agent Reports

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Renumbered from ADR-063 during the 2026-09 documentation-standard conformance
pass to resolve a numbering collision; no decision content changed.

`/history` replay rendered Markdown turns through `TerminalUI.render_markdown()`
with proper `▌` bars and ANSI styling, but live chat streaming wrote raw badge
and report strings straight to `sys.stdout.write()`, so live sub-agent reports
showed raw `>`, `**`, `###` instead of formatted Rich Markdown.

## Decision

1. **Live stream badge interception (`sympose/cli.py`).** In the token-stream
   consumer, chunks carrying badge / report payloads
   (`chunk.startswith("\n\n>")` or `"\n> " in chunk`) are parsed and rendered via
   `TerminalUI.render_markdown(self.console, chunk.strip())`.
2. **Unified visual fidelity.** Live sub-agent reports render identically to the
   `/history` replayer — purple `▌` bars, italic task metadata, clean tool
   chips.

## Consequences

**Positive**

- Live and replayed output look the same; no raw Markdown characters mid-stream.

**Negative / costs**

- The interception relies on badge/report chunks starting with a recognisable
  prefix; a payload shaped differently would stream raw.

## Alternatives rejected

> Not captured in the original decision record.
