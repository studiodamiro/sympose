---
title: "ADR-021 — Hierarchical Daily Notes & Vault-Agnostic Format Resolvers"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-021 — Hierarchical Daily Notes & Vault-Agnostic Format Resolvers

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

The flat `Daily Notes/YYYY-MM-DD.md` path does not support Obsidian *Periodic
Notes* conventions, where dailies live in year/month hierarchies
(`Daily/2019/10-October/2019-10-16.md`). Hardcoded paths also violate the
vault-agnosticism requirement.

## Decision

- Add `vault.daily_notes_folder` and `vault.daily_notes_format` to `config.yaml`
  / `DEFAULT_CONFIG` (default `Daily/%Y/%m-%B/%Y-%m-%d.md`).
- `VaultManager.write_daily_note` resolves the format via `strftime` and honours
  the `DAILY_NOTES_FORMAT` env override.
- Enshrine the **Vault Agnosticism Mandate** in `profiles/user_profile.md` and
  `profiles/_shared_memory.md`.

## Consequences

**Positive**

- Daily notes land wherever the user's Periodic Notes setup expects them.
- No flat-directory bloat across multi-year archives.

**Negative / costs**

- A misconfigured `strftime` string produces an unexpected path silently.

## Alternatives rejected

- **Keeping the flat `Daily Notes/YYYY-MM-DD.md` layout.** Rejected: breaks
  Obsidian Periodic Notes hierarchies and bloats one directory over years.
- **Hardcoding the hierarchical path.** Rejected: violates vault agnosticism —
  users organise dailies differently.
