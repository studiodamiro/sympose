---
title: "ADR-044 — In-Memory Inverted Index & Deterministic Backlink Lookup Engine"
created: 2026-08-27
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-044 — In-Memory Inverted Index & Deterministic Backlink Lookup Engine

- **Status:** Accepted
- **Date:** 2026-08-27
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Bi-directional linking in a PKM depends on backlinks ("which documents reference
Note X?"). Relying on an Obsidian MCP server or desktop plugin requires running
Obsidian in the background — 400–900 ms latency and 1,000+ schema tokens per
turn — violating the < 0.8s TTFT SLA and the zero-daemon mandate.

## Decision

Implement a native in-memory inverted index in `sympose/vault.py` using only
stdlib (`collections.defaultdict`, `re`, `os.walk`):

- `VaultManager.get_backlinks()` / `get_backlinks_digest()` /
  `get_forward_links()`; robust `extract_wikilinks` (aliases, `#heading`
  anchors).
- Strict per-profile sandbox (`vault_folders`) and `vault.ignore_folders`.
- Tier-0 natural-language intent interception in `resolve_turn_context()`
  ("what links to [[Topic]]?").
- Slash commands `/vault backlinks <note>` and `/backlinks <note>`.

## Consequences

**Positive**

- Sub-4 ms index build and query; no subprocess, no HTTP roundtrip.
- Works headless — terminal, Slack Socket Mode.
- Provides the data structure the web dashboard's knowledge graph later reuses.

**Negative / costs**

- The index lives in RAM and is rebuilt per process; very large vaults pay a
  one-time build cost (measured ~3 ms at test scale).

## Alternatives rejected

- **An Obsidian MCP server / desktop plugin for backlinks.** Rejected: requires
  Obsidian running in the background, adds 400–900 ms latency and 1,000+ schema
  tokens, and breaks the zero-daemon / zero-infrastructure philosophy.
