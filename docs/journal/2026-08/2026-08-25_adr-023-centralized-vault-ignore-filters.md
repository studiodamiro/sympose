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
  `Attachments`, `Drawings`, `.trash`).
- `VaultManager.search()` prunes ignored trees during `os.walk` before any file
  read.
- Keep `sympose/vault.py` under the 200 LOC ceiling.

> **Correction (2026-09-16):** the original decision list also included
> `Movies` and `dot-files`. Neither fits this ADR's own stated rationale —
> both are ordinary markdown content folders (or, for `dot-files`, not even
> a folder that exists inside a vault at all), not the binary/config noise
> this filter exists for. Their presence silently blocked a persona with
> full vault access (`vault_folders: ["*"]`) from ever reaching a
> `Movies/` folder through the structural retrieval path, while an
> unrelated code path (sub-agent shell commands) ignored this list
> entirely and reached it anyway - two paths quietly disagreeing about
> what was in scope. Removed from the shipped default in
> `config_schema.py` so this list stays what it was meant to be: a
> generic, user-agnostic set of Obsidian/system housekeeping folders, not
> a place for one vault's own content-folder names to end up baked into
> every install's default.

## Consequences

**Positive**

- Faster, cleaner searches; no read errors on binary trees.
- The ignore list is one config key, editable per vault.

**Negative / costs**

- A note genuinely stored under an ignored folder name is invisible until the
  list is adjusted.

## Alternatives rejected

> Not captured in the original decision record.
