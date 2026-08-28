---
entry: 2026-08-29
created: 2026-08-29 04:35
type: journal
project: sympose
tags:
  - packaging
  - onboarding
  - cli-design-system
  - typography
  - adr
---

# 2026-08-29: Standalone Python Packaging, Sovereign Onboarding Wizard & Standardized CLI Design System (ADR-045 – ADR-048)

> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Milestones:** Modern PEP 517/621 Packaging (`pyproject.toml`), Global User Workspace (`~/.sympose/`), Zero-Friction Onboarding (`sympose --setup`), Dynamic Persona Genesis (`[CREATE_PERSONA]`), and Unified Sympose CLI Design System (`SYMPOSE_THEME`).

---

## 1. Executive Summary & Problem Statement

To transform Sympose from a developer-only repository into a sovereign, production-grade CLI runtime that anyone can install across macOS, Linux, and Windows with a single command (`pipx install git+https://github.com/studiodamiro/sympose.git`), four major architectural initiatives were designed, tested, and shipped:

1. **Modern PEP 517/621 Packaging & Global User Directory (`~/.sympose/`)**:
   - Eliminate manual venv setup and python paths. Sympose now installs globally as `sympose` in PATH.
   - Implemented dynamic dual-mode workspace resolution: detects local project directory (`./profiles` or `./config.yaml`) if working in source, or defaults to the user's sovereign home directory (`~/.sympose/`).
2. **Interactive Zero-Friction Onboarding (`sympose --setup` & `/setup`)**:
   - Automated interactive first-run wizard prompting for LLM provider (Google Gemini, OpenRouter, Anthropic, Ollama) and Obsidian vault path linking.
   - Built-in live command `/setup` and `/onboard` available directly inside chat sessions.
3. **Clean-Slate Seeding & Dynamic Autonomic Persona Genesis (`[CREATE_PERSONA]`)**:
   - Fresh installs seed **Samantha only** out of the box (`samantha.yaml`, `samantha_soul.md`, `samantha_memory.md`, `user_profile.md`, `_shared_memory.md`, `config.yaml`, `workspace_rules.md`).
   - Enabled Samantha with absolute mastery over runtime orchestration (`sympose_mastery`), emitting `[CREATE_PERSONA: <handle> | <manifest>]` to write new agent files on disk dynamically in $<3\text{ms}$.
   - Auto-injected baseline skill fallbacks (`vault_recall`, `vault_write`, `web_search`) and model fallbacks for any newly generated persona.
4. **Standardized Sympose CLI Design System (`SYMPOSE_THEME`)**:
   - Established an industry-standard visual language and typography hierarchy (following GitHub CLI, Charm.sh, and Vercel CLI standards).
   - Replaced raw ASCII markdown streaming in slash commands (`/help`, `/model`, `/config`, `/skills`) with categorized, themed Rich Markdown surfaces and rounded containers (`box.ROUNDED`).

---

## 2. Architectural Decision Records (ADR-045 – ADR-048)

### ADR-045: Modern Standalone Python Packaging (`pyproject.toml`) & Sovereign User Workspace (`~/.sympose/`)

#### Context
Previously, Sympose required manual `git clone`, `python -m venv`, `source venv/bin/activate`, and `pip install -r requirements.txt`. Non-technical users could not easily install or run Sympose.

#### Decision
1. **PEP 517/621 Packaging**: Created `pyproject.toml` and `MANIFEST.in` defining package dependencies and the entry point `sympose = "app:main"`.
2. **Global Workspace Resolver (`sympose.bootstrap.resolve_workspace_dir`)**:
   - If `./profiles/` or `./config.yaml` exists in CWD $\implies$ use Local Dev Mode (`.` in current repo).
   - Otherwise $\implies$ use Global Sovereign Mode (`~/.sympose/`).
3. **Distribution Mandate**: Users can install and upgrade with single commands:
   ```bash
   pipx install git+https://github.com/studiodamiro/sympose.git
   pipx upgrade sympose
   ```

#### Consequences
- Zero-friction installation across macOS, Linux, and Windows.
- User data, memories, and custom personas are safely persisted in `~/.sympose/` across software updates.

---

### ADR-046: Samantha-Only Clean Slate & Dynamic Autonomic Persona Genesis (`[CREATE_PERSONA]`)

#### Context
Early prototypes included multiple hardcoded personas (Grace, Anaïs) in starter assets and procedural skills, leading to LLM confusion and role hallucinations on fresh installs.

#### Decision
1. **Samantha-Only Starter Seed**: On first run, `sympose.bootstrap.ensure_workspace` seeds only Samantha as the master orchestrator.
2. **Generic Heuristic Playbooks**: Purged hardcoded agent names from `skills/` and `prompts/`, replacing them with generic `@specialist` and `@peer` patterns.
3. **Dynamic Autonomic Persona Tag (`[CREATE_PERSONA]`)**:
   - When the user asks to create an agent in natural language, Samantha emits:
     ```text
     [CREATE_PERSONA: <handle> |
     name: "<Display Name>"
     handle: "<handle>"
     title: "<Role>"
     model: "<model_id>"
     vault_folders: ["<Folder1>", "<Folder2>"]
     share_memory: true
     skills: ["<skill1>", "<skill2>"]
     thinking_phrases: ["<Phrase1>...", "<Phrase2>..."]
     ]
     ```
   - `ActionProcessor` writes `profiles/<handle>.yaml` and bootstraps `profiles/<handle>_soul.md` and `_memory.md` on disk, dynamically mounting `@<handle>` into `/switch`.
4. **Baseline Fallback Guarantee**: If `model:` or `skills:` are omitted from the created YAML, `ProfileManager.bootstrap_missing_artifacts` automatically injects `DEFAULT_MODEL` and the baseline skill trifecta (`["vault_recall", "vault_write", "web_search"]`).

---

### ADR-047: Standardized Sympose CLI Design System (`SYMPOSE_THEME`) & Typography Standard

#### Context
Slash command outputs (`/help`, `/model`, `/config`) were previously outputting raw markdown asterisks and backticks directly to terminal stdout with misleading persona speaker headers (`Grace Hopper: **Available Commands**`).

#### Decision
1. **Thematic Palette (`SYMPOSE_THEME`)**:
   - `Brand / Primary Headers`: `bold cyan`
   - `Category Subheaders`: `bold white`
   - `Interactive Handles & Code Chips`: `bold yellow` / `bright_yellow on grey11`
   - `Status Indicators`: `bold green` (Active / Success) and `bold red` (Missing / Error)
   - `Vault Paths / Entities`: `magenta`
   - `Latency / Metadata`: `dim cyan` / `dim white`
2. **Surface Standards**:
   - Bounded panels and modals use `box=ROUNDED` with subtle `dim cyan` borders and `(1, 2)` padding.
   - Persona switcher (`/switch`) uses right-aligned indexes, color-coded model chips, and compact sandbox paths.
3. **Structured Command Formatting**:
   - System commands (`/help`, `/model`, `/config`, `/skills`) render via `rich.markdown.Markdown` with section headings and zero false speaker prefixes.

---

### ADR-048: Dynamic 3-Tier Model Hierarchy & Runtime Fallback Architecture

#### Context
Hardcoded model strings (e.g. `gemini/gemini-3.5-flash-lite`) caused 401 authentication exceptions when LiteLLM fell back to enterprise Google Vertex AI endpoints.

#### Decision
Established a strict **3-Tier Model Resolution Hierarchy**:
1. **Tier 1 (Global System Default):** Configured in `.env` as `DEFAULT_MODEL` (e.g. `openrouter/google/gemini-2.5-flash` or `gemini/gemini-3.6-flash`).
2. **Tier 2 (Per-Persona Specialization):** Configured in `profiles/<handle>.yaml` under `model:` (e.g. `openrouter/anthropic/claude-3.5-sonnet` for code).
3. **Tier 3 (Session Summarizer & Live Overrides):** Configured in `config.yaml` (`session.exit_behavior.summarization_model`), `/model <id>` live switches, or `/setup` wizard.

---

## 3. Verification & Test Coverage

All test suites were built and verified with 100% pass rates:
* `scratch/test_onboarding_bootstrap.py` — Fresh user workspace initialization in isolated directory.
* `scratch/test_persona_creation_action.py` — Autonomous `[CREATE_PERSONA]` tag execution and dynamic `/switch` mounting.
* `scratch/test_server_endpoints.py` — FastAPI REST and Vault Backlink endpoints.
* `scratch/test_cli_theme.py` — Visual layout, typography, and Rich Markdown rendering.
