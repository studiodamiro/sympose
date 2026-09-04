---
entry: 2026-08-24
created: 2026-08-24 21:10
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/vault
  - sympose/security
  - adr
---

# Sympose Engineering Log: Multi-Folder Vault Access & Flexible Domain Whitelists

> **Date:** Monday, August 24, 2026  
> **Topic:** ADR-011 Multi-Folder Vault Whitelisting & Full-Vault Access Architecture  
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)  
> **Status:** Implemented, Tested & Verified (All Modules < 200 LOC)  

---

## 1. Executive Summary

Existing real-world Obsidian vaults typically follow multi-folder organizational taxonomies (e.g. PARA method with `01_Projects`, `02_Areas`, `03_Resources`, `04_Archives`, `Daily Notes`). Previously, Sympose assigned each agent a single rigid folder (`vault_folder: "General"`), preventing engineering agents from cross-referencing architecture specs, project files, and reference notes in other directories.

To seamlessly integrate with existing Obsidian vaults without requiring users to move or rename files, we designed and implemented **ADR-011: Multi-Folder Vault Access & Flexible Domain Whitelists**:
1. **Multi-Folder Whitelist (`vault_folders: [...]`)**: Agents can specify a list of permitted folders in their YAML manifests.
2. **Full-Vault Root Access (`vault_folders: ["*"]` or `vault_folder: ""`):** Trusted agents can search and read across the entire root vault.
3. **Cross-Directory Search & Path-Aware Reading**: Search spans all whitelisted folders, and relative paths (e.g. `Architecture/cache.md` or `Reference/api.md`) are resolved automatically.
4. **Strict Security Sandboxing**: Unlisted directories (e.g. `Personal/` or `Finances/`) remain strictly blocked with `is_safe_path` path traversal protection.

---

## 2. Architectural Decision Record

- **[ADR-011 — Multi-Folder Vault Whitelisting & Full-Vault Access Architecture](./2026-08-24_adr-011-multi-folder-vault-whitelisting.md):**
  `vault_folders: [...]` resolves to canonical paths under `MASTER_VAULT_PATH`,
  wildcards grant full-root access, legacy single `vault_folder` still works, and
  non-whitelisted folders stay denied. Amends
  [ADR-002](./2026-08-24_adr-002-master-vault-domain-sandboxing.md).

---

## 3. Whitelist Topology

```mermaid
graph TD
    Vault[Obsidian Master Vault ~/obsidian]
    
    Vault --> Projects[Projects/]
    Vault --> Arch[Architecture/]
    Vault --> Ref[Reference/]
    Vault --> Daily[Daily Notes/]
    Vault --> Journal[Journal/]
    Vault --> Personal[Personal/]
    Vault --> Finances[Finances/]

    Grace([@grace]) -->|vault_folders| Projects
    Grace -->|vault_folders| Arch
    Grace -->|vault_folders| Ref
    Grace -->|vault_folders| Daily
    Grace -.->|BLOCKED / Air-Gapped| Personal
    Grace -.->|BLOCKED / Air-Gapped| Finances

    Auri([@aurelius]) -->|vault_folders| Journal
    Auri -->|vault_folders| Personal
    Auri -->|vault_folders| Daily
    Auri -.->|BLOCKED| Projects
    Auri -.->|BLOCKED| Finances
```

---

## 4. Verification & Benchmarks

* **Automated Test Suite ([`scratch/test_multi_folder_vault.py`](../../../scratch/test_multi_folder_vault.py))**:
  * Multi-folder whitelist resolution (`Projects`, `Architecture`, `Reference`): **PASSED**
  * Cross-folder reading: **PASSED**
  * Security rejection on unlisted folders (`Personal/`, `Finances/`): **PASSED**
  * Multi-folder search: **PASSED**
  * Writing to specific and default folders: **PASSED**
  * Full-vault wildcard access (`vault_folders: ["*"]`): **PASSED**
* **LOC Compliance**:
  * All 10 modules in `sympose/` strictly under 200 lines (1,415 total LOC).
