---
title: "Sandboxed Obsidian Vault & File Security"
created: 2026-08-24
type: wiki-architecture
parent: architecture/overview
tags:
  - sympose/security
  - obsidian-vault
  - sandboxing
---

# 🛡️ Sandboxed Obsidian Vault & File Security

Sympose connects AI agents directly to your local **Obsidian Vault** for persistent note-taking, daily journaling, and session archival. To prevent cloud LLMs or rogue agent prompts from reading or corrupting private personal notes, Sympose enforces a strict **Domain Sandboxing Security Architecture**.

---

## 1. Domain-Level Folder Isolation

Every agent profile manifest defines an isolated `vault_folder` boundary:

| Agent | Model Tier | Domain Folder | Permitted Access |
| :--- | :--- | :--- | :--- |
| **@samantha** | Cloud (Gemini) | `General/` | Cross-functional strategy & synthesis notes only. |
| **@grace** | Cloud (Claude/Gemini) | `Engineering/` | Technical docs, architecture pattern files, and code reviews. |
| **@aurelius** | **Local Offline (Ollama)** | `Personal/` | 100% private daily brain-dumps, journal reflections, and personal growth. |

---

## 2. Defensive Path Validation (`is_safe_path`)

To prevent Path Traversal attacks (e.g. `../../etc/passwd` or accessing other private vault folders), every file read/write pass through [`VaultManager.is_safe_path()`](file:///Users/damiro/Development/sympose/sympose/vault.py#L30):

```python
@classmethod
def is_safe_path(cls, base_dir: str, target_path: str) -> bool:
    """Ensures target_path resolves strictly within base_dir (prevents ../ traversal)."""
    try:
        base = os.path.realpath(base_dir)
        target = os.path.realpath(target_path)
        return os.path.commonpath([base]) == os.path.commonpath([base, target])
    except Exception:
        return False
```

If an agent or command attempts to escape its assigned domain folder:
1. The file write/read is aborted immediately.
2. An error banner is logged.
3. No external files or sensitive personal directories are exposed to cloud models.

---

## 3. Pluggable Search Tiers

[`sympose/vault.py`](file:///Users/damiro/Development/sympose/sympose/vault.py#L82) provides a multi-tier search architecture configurable in `config.yaml`:

- **Tier 1: `direct` (Default / Pure Python)**: Zero dependencies, ultra-fast regex/substring scan over domain notes.
- **Tier 2: `sqlite_fts`**: Ranked BM25 full-text search indexed in SQLite.
- **Tier 3: `semantic`**: Vector search via local embedding models (e.g. `all-MiniLM-L6-v2`).
