---
title: "ADR-030 — High-Density Folder Digests & Universal Ban on Time-Delay Simulation"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-030 — High-Density Folder Digests & Universal Ban on Time-Delay Simulation

- **Status:** Accepted — extends
  [ADR-007](./2026-08-24_adr-007-memory-grounding-anti-hallucination.md) /
  [ADR-024](./2026-08-25_adr-024-ground-truth-sovereignty-axiom.md)
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Asked broad questions over a folder of 45 notes (`People/`), `@aurelius`
(`gemma2:9b`) (1) faked asynchronous "sifting" ("give me a few minutes... I'll
come back") then produced generic filler, and (2) fragmented context — 45 full
notes overflow the window, but 4–5 full notes leave 40 people invisible and the
model hallucinates `[Name of Person]` placeholders.

## Decision

1. **High-density folder digests (small-to-big).** `VaultManager.get_folder_digest()`
   emits a compact 1-line metadata manifest per file (`name:`, `aka:`, `tags:`,
   `birthday:`, `created:`, `up:`) — 45 notes compress from ~25,000 tokens to
   ~450, so any model synthesizes the whole directory in one turn.
2. **Universal ban on time-delay simulation (Pillar 6).** Codified in
   `docs/wiki/memory/architecture-standard.md` and the universal prompt builder:
   findings are delivered immediately in the current turn; phrases like "give me
   a few minutes" / "I'll look into this and come back" are forbidden.
3. **Direct entity & title resolution.** Any person / entity named in a prompt
   auto-resolves against note filenames across allowed directories.

## Consequences

**Positive**

- Whole-folder synthesis on a local 9B model with no overflow or placeholders.
- Named entities resolve to their note automatically.

**Negative / costs**

- A digest is metadata only; a question needing note *bodies* still requires a
  follow-up read.

## Alternatives rejected

- **Injecting full note bodies for folder-wide questions.** Rejected: 45 notes
  overflow the context window.
- **Injecting only the first few full notes.** Rejected: the rest of the folder
  becomes invisible and the model invents placeholders.
