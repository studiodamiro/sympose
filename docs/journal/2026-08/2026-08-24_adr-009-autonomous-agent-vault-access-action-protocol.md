---
title: "ADR-009 — Autonomous Agent Vault Read/Write Access & Action Protocol"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-009 — Autonomous Agent Vault Read/Write Access & Action Protocol

- **Status:** Accepted — the action-tag parser is later hardened by
  [ADR-041](./2026-08-27_adr-041-slack-thread-active-context-isolation.md) and
  [ADR-049](./2026-08-29_adr-049-code-fence-action-tag-parsing.md)
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Base LLMs generate rich Markdown artifacts (schemas, specs, reflections)
straight to stdout, forcing the user to copy-paste or issue `/note` manually.
Agents had no autonomous way to write or retrieve vault knowledge mid-turn.
Adding OpenAI-style tool-call or ReAct roundtrips would add 1.5s–4.0s of network
latency per turn, breaking the sub-second SLA.

## Decision

- **Autonomic streaming action tags**, emitted inline during generation and
  executed atomically after the stream closes:
  `[WRITE_NOTE: <file> | <content>]`, `[APPEND_NOTE: <file> | <content>]`,
  `[DAILY_NOTE: <reflection>]`, `[REMEMBER: <fact>]`. Each produces a clean
  confirmation badge.
- **Dedicated `ActionProcessor` (`sympose/actions.py`)** parses, defensively
  executes, and badges tags — an SRP module under the 200 LOC ceiling.
- **Pre-turn grounded retrieval**: note-read and vault-search queries resolve in
  < 3 ms from the local filesystem and are injected into the turn's prompt, with
  no LLM pre-computation.
- **Defensive sandboxing**: `is_safe_path` rejects traversal outside the
  persona's assigned domain.

## Consequences

**Positive**

- Agents read and write Obsidian notes with no human friction and no latency
  penalty.
- Zero new external dependencies.
- Domain sandboxing keeps private notes unreachable by engineering / general
  personas.

**Negative / costs**

- Tags are parsed from free text, so parsing robustness (code fences, nested
  brackets, Slack history bleed) becomes an ongoing hardening surface.

## Alternatives rejected

- **Heavyweight agentic function-calling (OpenAI tool calls / ReAct loops).**
  Rejected: 1.5s–4.0s of network roundtrip latency per turn violates the
  sub-second TTFT SLA.
