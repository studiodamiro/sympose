---
title: "ADR-056 — Retirement of Automated Vault Session Dumping in Favor of Native History Sovereignty"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-056 — Retirement of Automated Vault Session Dumping in Favor of Native History Sovereignty

- **Status:** Accepted — **supersedes** the automated Obsidian session-log dump
  established in
  [ADR-005](./2026-08-24_adr-005-config-yaml-session-summarization-memory.md);
  builds on
  [ADR-054](./2026-08-29_adr-054-jsonl-conversation-persistence-context-hydration.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Sympose previously dumped session-summary Markdown notes into `Sessions/` (or
`General/Sessions/`) inside the user's Obsidian vault on exit — behaviour
established in
[ADR-005](./2026-08-24_adr-005-config-yaml-session-summarization-memory.md). With
native `.jsonl` session persistence and `/history` now active
([ADR-054](./2026-08-29_adr-054-jsonl-conversation-persistence-context-hydration.md)),
those dumps duplicated storage and polluted the user's curated second brain with
machine-generated noise.

## Decision

1. **Retire automated vault session dumps.** `session.exit_behavior.default_target`
   collapses to `memory` (extract durable facts to `_memory.md`) or `none`
   (instant 0 ms exit). No automated Markdown files are written to the vault on
   exit.
2. **Intentional Knowledge Contract.** The Obsidian vault is reserved for
   intentional human notes and deliberate agent generation (`[WRITE_NOTE]`,
   `[DAILY_NOTE]`, explicit `/save obsidian`).
3. **Binary exit dialog.** `TerminalUI.prompt_exit_choice()` →
   `[1] Extract durable facts to _memory.md [Default]` / `[2] Skip`.

## Consequences

**Positive**

- Pristine Obsidian vault — 0% session spam in search, graph view, backlinks.
- Clear 3-tier separation: `.jsonl` for dialogue replay, `_memory.md` for
  cognitive prompt facts, `Vault/` for sovereign knowledge.

**Negative / costs**

- Users who relied on browsable session notes inside Obsidian now use `/history`
  (`.jsonl`) or an explicit `/save obsidian` instead.

## Alternatives rejected

- **Keeping the automated `Sessions/` Markdown dump alongside `.jsonl`.**
  Rejected: duplicate storage and machine-generated clutter in a hand-curated
  vault.
