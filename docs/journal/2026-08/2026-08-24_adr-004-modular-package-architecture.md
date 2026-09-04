---
title: "ADR-004 — Industry-Standard Modular Package Architecture"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-004 — Industry-Standard Modular Package Architecture

- **Status:** Accepted
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

The monolithic `app.py` was approaching 600+ lines and becoming unwieldy before
the Phase 2 Slack and dashboard modules could be added. The project needed a
clean module boundary set and an enforceable size ceiling.

## Decision

Segregate responsibilities into focused Python modules under `sympose/`, each
strictly under 200 lines of code, and reduce `app.py` to a lean entry point
(~35–40 lines) that only parses `--config` / `--persona` and dispatches:

- `sympose/config.py` — `ConfigManager`, environment loading, path-security
  validation (`is_safe_path`).
- `sympose/profiles.py` — `ProfileManager`: YAML manifest scanning and composite
  prompt building.
- `sympose/vault.py` — `VaultManager`: sandboxed note read/write, session logs,
  daily notes.
- `sympose/engine.py` — `PersonaEngine`: LiteLLM routing, sliding context,
  action-tag interception, sub-agent delegation.
- `sympose/memory.py` — `SessionArchivist`: session summarization and memory
  distillation.
- `sympose/commands.py` — `CommandInterceptor`: slash commands and natural
  language memory capture.
- `sympose/ui.py` — `TerminalUI`: Rich banners, persona table, exit modals.
- `sympose/cli.py` — `TerminalInterface`: real-time streaming and the REPL loop.

The **hard < 200 LOC ceiling** becomes a binding architectural constraint.

## Consequences

**Positive**

- Every file is scannable and independently testable.
- Phase 2 modules (`sympose/slack.py`, later `sympose/server.py`) drop in without
  touching a monolith.
- The size ceiling forces continuous SRP discipline.

**Negative / costs**

- The ceiling creates recurring pressure to split modules
  (`sympose/commands.py`, `sympose/mcp.py`) as features land — an accepted,
  ongoing tax rather than a one-time cost.

## Alternatives rejected

- **Keeping the single-file `app.py`.** Rejected (reconstructed from the journal
  narrative): at 600+ lines it was already hard to navigate and would only
  worsen once Slack, MCP, and dashboard code were added.
