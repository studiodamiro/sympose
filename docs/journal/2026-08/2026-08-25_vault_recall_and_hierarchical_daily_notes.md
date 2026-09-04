---
entry: 2026-08-25
created: 2026-08-25 16:05
type: daily-log
project: sympose
tags:
  - sympose/vault
  - sympose/retrieval
  - architecture/vault-recall
  - obsidian/periodic-notes
---

# 📚 Engineering Journal: Hierarchical Daily Notes, Vault Agnosticism & Local-First Recall

> **Date:** August 25, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  

---

## 🎯 Focus & Objectives
1. Implement the Obsidian standard hierarchical `Daily/YYYY/MM-Month/YYYY-MM-DD.md` resolver for daily reflections and notes, avoiding flat directory bloat over multi-year archives.
2. Implement **The Vault Agnosticism Mandate**: ensure Sympose adapts cleanly to any user-chosen folder taxonomy, date formats, or directory hierarchies without forcing rigid structural constraints.
3. Build the **`vault_recall` (`skills/vault_recall/SKILL.md`)** procedural skill playbook for tiered local-first historical retrieval using local models (`ollama/qwen2.5:7b`, `ollama/gemma2:9b`) and sub-agent workers (`/worker vault_recall`).
4. Implement centralized, dynamic noise and non-text directory filtering in `config.yaml` (`vault.ignore_folders`) and `sympose/vault.py` (`.obsidian`, `Attachments`, `Drawings`, `Movies`, `.git`, `.trash`) to prevent token waste and latency during vault searches.
5. Update agent manifests (`grace.yaml`, `samantha.yaml`, `aurelius.yaml`) and the `sympose_mastery` agent creation playbook to mount `vault_recall` and align `vault_folders` with the user's active vault taxonomy.

---

## 🏗️ Architectural Decisions Recorded

- **[ADR-021 — Hierarchical Daily Notes & Vault-Agnostic Format Resolvers](./2026-08-25_adr-021-hierarchical-daily-notes-format-resolvers.md):**
  configurable `vault.daily_notes_format` (`strftime`) matching Obsidian
  Periodic Notes; the Vault Agnosticism Mandate enshrined — rejecting both the
  flat layout and a hardcoded hierarchical path.
- **[ADR-022 — Local-First Hierarchical Retrieval & Noise Pruning (`vault_recall`)](./2026-08-25_adr-022-local-first-hierarchical-retrieval.md):**
  the 3-tier funnel — Tier 0 deterministic filter → Tier 1 local-LLM triage
  ($0) → Tier 2 optional frontier deep reasoning on pre-cleaned files.
- **[ADR-023 — Centralized Vault Ignore Filters](./2026-08-25_adr-023-centralized-vault-ignore-filters.md):**
  `vault.ignore_folders` prunes heavy / binary trees during `os.walk` before
  any file read.

---

## 🧪 Verification & Empirical Results

### Automated Test Suite:
```text
✅ vault_recall skill correctly indexed: Obsidian Vault Historical Synthesis & Recall ['ollama/qwen2.5:7b', 'ollama/gemma2:9b', 'gemini/gemini-3.5-flash-lite']
✅ Grace profile verified: ['Projects', 'Architecture', 'Reference', 'Daily', 'Code'] ['git_workflow', 'code_review', 'system_architecture', 'vault_recall']
✅ Daily note target format: Daily/2026/08-August/2026-08-25.md
✅ Configured ignore_folders: ['.obsidian', '.git', 'Attachments', 'Drawings', 'Movies', '.trash', 'dot-files']
✅ sympose/vault.py line count: 198 LOC (Mandate: <200 LOC)
```
