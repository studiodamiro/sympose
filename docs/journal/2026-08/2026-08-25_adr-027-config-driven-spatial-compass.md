---
title: "ADR-027 — Config-Driven Spatial Compass & Complete Vault Agnosticism"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-027 — Config-Driven Spatial Compass & Complete Vault Agnosticism

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Hardcoding folder paths (`Movies/`, `Projects/`, `Daily/`) into skills or tools
assumes every user organises identically. Agents also conflated
`profiles/_shared_memory.md` with `MASTER_VAULT_PATH` and guessed wrong env-var
names.

## Decision

1. **Code / spatial-config separation.** No hardcoded directory paths in
   `sympose/`. All paths live in `.env` (`MASTER_VAULT_PATH`) and `config.yaml`
   (`vault.ignore_folders`).
2. **Spatial-coordinate injection.** `sympose/profiles.py` gives each agent its
   exact workspace root, master vault path, and shared-memory file location.
3. **Multi-dimensional discovery.** `skills/vault_recall/SKILL.md` uses dynamic
   inspection (`find`, `ls`, frontmatter keys, date formats) instead of folder
   assumptions — supporting Flat, PARA, Johnny Decimal, Zettelkasten.
4. **Universal portability.** Clone to any machine, set `MASTER_VAULT_PATH`,
   done.

## Consequences

**Positive**

- Sympose navigates any personal vault with one env var.
- Agents stop guessing where their files physically live.

**Negative / costs**

- Dynamic discovery is slower than a hardcoded path lookup — an accepted trade
  for portability.

## Alternatives rejected

> Not captured in the original decision record.
