---
title: "ADR-023 — Centralized Vault Ignore Filters"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-023 — Centralized Vault Ignore Filters

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Obsidian vaults carry heavy binary assets and config trees (`.obsidian/`,
`Attachments/`, `Drawings/`, `.git/`, `.trash/`) that cause search latency, file
read errors, and token waste when walked recursively.

## Decision

- Add `vault.ignore_folders` to `config.yaml` (`.obsidian`, `.git`,
  `Attachments`, `Drawings`, `Movies`, `.trash`, `dot-files`).
- `VaultManager.search()` prunes ignored trees during `os.walk` before any file
  read.
- Keep `sympose/vault.py` under the 200 LOC ceiling.

## Consequences

**Positive**

- Faster, cleaner searches; no read errors on binary trees.
- The ignore list is one config key, editable per vault.

**Negative / costs**

- A note genuinely stored under an ignored folder name is invisible until the
  list is adjusted.

## Alternatives rejected

> Not captured in the original decision record.
