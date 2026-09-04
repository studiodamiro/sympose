---
title: "ADR-026 — Sub-Agent Worker Spatial Environment & Inherited Sandbox Security"
created: 2026-08-25
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-026 — Sub-Agent Worker Spatial Environment & Inherited Sandbox Security

- **Status:** Accepted
- **Date:** 2026-08-25
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Workers ran `run_command` in `sympose/` (the code repo), not the vault, so they
could not find notes. A missing recommended model crashed dispatch. And a worker
spawned by an agent whose whitelist excludes `Daily/` could still read private
daily notes and leak them to cloud models — a sandbox breakout.

## Decision

1. **Inherited worker sandboxing (zero-escalation mandate).** Workers resolve
   and inherit the parent's `allowed_dirs` via
   `VaultManager.get_allowed_dirs(parent_prof)`. `NativeTools.read_file()` and
   `run_command()` enforce those boundaries — an unauthorized worker's `cat` /
   `ls` / `grep` against a restricted folder is blocked with a Security Error.
2. **Spatial path injection.** The worker runtime injects
   `Obsidian Vault Directory: <path>` into the worker prompt.
3. **Vault-aware file reader.** `NativeTools.read_file()` resolves paths relative
   to `MASTER_VAULT_PATH` when not found locally.
4. **Fuzzy skill resolution & model alignment.** `sympose/skills.py` tolerates
   CamelCase / hyphen variants (`VaultHistoricalRecall` → `vault_recall`) and
   recommended models are aligned to installed weights.

## Consequences

**Positive**

- Workers can actually reach the vault, and cannot exceed their parent's
  permissions.
- Dispatch no longer crashes on an uninstalled recommended model.

**Negative / costs**

- Every native tool call carries a boundary check; skill-name fuzziness is a
  small parsing surface.

## Alternatives rejected

- **Unrestricted sub-agent workers.** Rejected: allows privilege escalation into
  folders the parent agent is explicitly denied.
