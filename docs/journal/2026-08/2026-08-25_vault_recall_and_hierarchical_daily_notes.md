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

## 🏗️ Architectural Decisions Recorded (ADR Index)

### ADR-021: Hierarchical Daily Notes & Vault-Agnostic Format Resolvers
* **Context**: The default flat `Daily Notes/YYYY-MM-DD.md` path format fails to support standard Obsidian *Periodic Notes* conventions where daily notes are organized into decade-spanning year/month folder hierarchies (`Daily/2019/10-October/2019-10-16.md`). Furthermore, hardcoded folder paths violate the core user requirement that Sympose must remain completely vault-agnostic.
* **Decision**:
  * Added `vault.daily_notes_format` and `vault.daily_notes_folder` to `config.yaml` and `DEFAULT_CONFIG` in `sympose/config.py`:
    ```yaml
    vault:
      daily_notes_folder: Daily
      daily_notes_format: "Daily/%Y/%m-%B/%Y-%m-%d.md"
    ```
  * Refactored `VaultManager.write_daily_note` in `sympose/vault.py` to dynamically resolve formats via standard `strftime` formatting and environment overrides (`DAILY_NOTES_FORMAT`).
  * Enshrined the **Vault Agnosticism Mandate** into `profiles/user_profile.md` and `profiles/_shared_memory.md`.

---

### ADR-022: Local-First Hierarchical Retrieval & Noise Pruning (`vault_recall`)
* **Context**: Brute-force vault searching with cloud/frontier LLMs causes massive token cost, context pollution, and privacy concerns for personal reflections. However, naive local LLM search over raw files suffers from context limits and high latency.
* **Decision**:
  * Established the **3-Tier Triage & Deep Dive Retrieval Funnel**:
    1. *Tier 0 (Deterministic Filter)*: Mechanical path matching and regex (`0.005s`, 0 tokens).
    2. *Tier 1 (Local LLM Triage - $0.00)*: Ephemeral sub-agent worker running `ollama/qwen2.5:7b` or `ollama/gemma2:9b` parses YAML frontmatter, `## Key Decisions`, and `## Action Items` to filter candidate files and build structured timelines.
    3. *Tier 2 (Frontier Deep Reasoning)*: Optional paid model (Claude Sonnet 4.5 / Gemini 3.7) performs deep code refactoring or architectural synthesis using only the pre-cleaned high-signal files.
  * Created `skills/vault_recall/SKILL.md` with explicit recommended local models and deliverable schemas.

---

### ADR-023: Centralized Vault Ignore Filters
* **Context**: Obsidian vaults often contain heavy binary assets, Canvas diagrams, drawing files, and configuration data (`.obsidian/`, `Attachments/`, `Drawings/`, `.git/`) that cause search latency, file read errors, and token waste when traversed recursively.
* **Decision**:
  * Added `vault.ignore_folders` to `config.yaml`:
    ```yaml
    vault:
      ignore_folders:
        - .obsidian
        - .git
        - Attachments
        - Drawings
        - Movies
        - .trash
        - dot-files
    ```
  * Injected dynamic directory pruning in `VaultManager.search()` (`sympose/vault.py`) to bypass ignored trees during `os.walk` before file reads occur.
  * Maintained strict compliance with the **<200 LOC per file** mandate (`sympose/vault.py` at 198 LOC).

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
