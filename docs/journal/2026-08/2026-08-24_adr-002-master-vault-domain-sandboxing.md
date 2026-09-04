---
title: "ADR-002 — Master Vault Domain Sandboxing & Access Control"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-002 — Master Vault Domain Sandboxing & Access Control

- **Status:** Accepted — the string-prefix boundary check is later hardened by
  [ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md)
  (Standard 2); multi-folder whitelists added by
  [ADR-011](./2026-08-24_adr-011-multi-folder-vault-whitelisting.md)
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

The user keeps a single master Obsidian vault organized into top-level domain
folders (`/General`, `/Engineering`, `/Personal`). Different personas operate at
different trust tiers — a cloud model must never be able to read a private
`/Personal` note.

## Decision

Implement strict runtime folder sandboxing per persona, with path-boundary
checks (`is_safe_path()`). Each persona manifest declares the domain folder(s) it
may touch; any resolved path outside that boundary is denied before any read or
write executes.

## Consequences

**Positive**

- A hard security boundary keeps private notes out of cloud-model prompts.
- Domain assignment is declarative, per persona, in the YAML manifest.

**Negative / costs**

- The initial check is a plain string prefix comparison, which allows
  sibling-directory escapes (`/vault` matching `/vault_secrets/`) — corrected in
  [ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md).
- A single rigid folder per persona proved too restrictive for real vaults —
  relaxed by [ADR-011](./2026-08-24_adr-011-multi-folder-vault-whitelisting.md).

## Alternatives rejected

> Not captured in the original decision record.
