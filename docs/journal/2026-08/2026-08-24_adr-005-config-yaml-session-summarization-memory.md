---
title: "ADR-005 — Centralized config.yaml, Session Summarization & Memory Consolidation"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-005 — Centralized `config.yaml`, Session Summarization & Memory Consolidation

- **Status:** Accepted — the automated Obsidian session-log dump defined here was
  retired by
  [ADR-056](./2026-08-29_adr-056-retire-automated-vault-session-dumping.md)
  (2026-08-29); the `config.yaml`, `ConfigManager`, and `summarize_session()`
  portions remain in force
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Runtime and latency parameters were scattered and partly hardcoded. The project
needed a single tunable config surface, plus automated session summarization on
exit and on demand, persistent memory consolidation into `_memory.md`, and
structured session logging.

## Decision

- Create a root `config.yaml` separating runtime / latency infrastructure from
  agent personas (`profiles/*.yaml`).
- Implement `ConfigManager` (`sympose/config.py`) with dot-notation access and
  dynamic LiteLLM synchronization.
- Implement `summarize_session()` in `SessionArchivist` using a dedicated fast
  model to distill persistent memory bullets and Markdown session logs.
- Add natural-language memory capture and the autonomic `[REMEMBER: <fact>]` tag.
- Add an interactive exit workflow (Memory / Obsidian / Both / Discard) with
  auto-save and terminal clearing.
- Add live commands: `/config`, `/config set <key> <val>`, `/save [target]`,
  `/clear`.

  > **Superseded 2026-08-29 by
  > [ADR-056](./2026-08-29_adr-056-retire-automated-vault-session-dumping.md):**
  > the automated Markdown session-log dump into the Obsidian vault
  > (`Sessions/`) is retired. Transcripts now live in sovereign `.jsonl` files;
  > the exit dialog collapses to "extract durable facts to `_memory.md`" or
  > "skip". `config.yaml` / `ConfigManager` / `summarize_session()` are
  > unchanged.

## Consequences

**Positive**

- One file governs all latency and exit-flow tuning; no source edits to retune.
- Durable facts survive session end without manual note-taking.

**Negative / costs**

- The Obsidian session-log dump polluted the user's curated vault with
  machine-generated notes — the reason it was retired by ADR-056.

## Alternatives rejected

> Not captured in the original decision record.
