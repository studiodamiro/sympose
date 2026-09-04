---
title: "ADR-011 — Multi-Folder Vault Whitelisting & Full-Vault Access Architecture"
created: 2026-08-24
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-011 — Multi-Folder Vault Whitelisting & Full-Vault Access Architecture

- **Status:** Accepted — amends
  [ADR-002](./2026-08-24_adr-002-master-vault-domain-sandboxing.md) by replacing
  the single rigid `vault_folder` with a multi-folder whitelist
- **Date:** 2026-08-24
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Real Obsidian vaults use multi-folder taxonomies (PARA: `01_Projects`,
`02_Areas`, `03_Resources`, `04_Archives`, `Daily Notes`). Restricting a persona
to one folder (`vault_folder: "General"`) forced either file duplication or
amnesia about related architecture / reference notes.

## Decision

- `VaultManager.get_allowed_dirs()` resolves `vault_folders: [...]` into a list
  of canonical paths under `MASTER_VAULT_PATH`.
- Wildcards (`"*"`, `""`, `"all"`) grant full root-vault access for trusted
  agents.
- Legacy single `vault_folder: "Folder"` manifests still work.
- `read_note`, `search`, and `write_note` operate across every whitelisted
  directory; writes default to the primary folder when no path prefix is given.
- Any access to a non-whitelisted folder is denied.

## Consequences

**Positive**

- Zero friction integrating with an established vault — no file moves.
- Agents cross-reference multiple knowledge domains at once.
- Sensitive unlisted folders (`Personal/`, `Finances/`) stay isolated.

**Negative / costs**

- A broader whitelist widens each agent's blast radius if a manifest is
  misconfigured; the boundary check itself is hardened later by
  [ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md).

## Alternatives rejected

- **One rigid folder per persona (status quo from ADR-002).** Rejected: forces
  artificial file duplication or leaves agents blind to related notes.
