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

## 2. Architectural Decision Records

- **[ADR-045 - Modern Standalone Python Packaging (`pyproject.toml`) & Sovereign User Workspace](./2026-08-29_adr-045-standalone-packaging-sovereign-workspace.md):**
  PEP 517/621 packaging, `sympose` entry point, dual-mode workspace resolver
  (local repo vs `~/.sympose/`), 1-command `pipx` install/upgrade - replacing
  manual clone + venv + pip.
- **[ADR-046 - Samantha-Only Clean Slate & Dynamic Autonomic Persona Genesis](./2026-08-29_adr-046-samantha-only-clean-slate-persona-genesis.md):**
  seed Samantha only; generic `@specialist` playbooks; `[CREATE_PERSONA]` writes
  a new agent in `< 3 ms` with baseline model/skill fallbacks. Narrows
  [ADR-006](./2026-08-24_adr-006-autonomous-soul-memory-bootstrapping.md);
  rejected shipping multiple hardcoded personas.
- **[ADR-047 - Standardized Sympose CLI Design System (`SYMPOSE_THEME`) & Typography Standard](./2026-08-29_adr-047-cli-design-system-typography.md):**
  semantic color tokens, `box.ROUNDED` surfaces, `rich.markdown.Markdown` for
  `/help` `/model` `/config` `/skills` with no false speaker prefixes.
- **[ADR-048 - Dynamic 3-Tier Model Hierarchy & Runtime Fallback Architecture](./2026-08-29_adr-048-dynamic-3-tier-model-hierarchy.md):**
  system `DEFAULT_MODEL` -> persona `model:` -> summarizer / `/model` override;
  no hardcoded model strings (which caused Vertex-fallback 401s).

---

## 3. Verification & Test Coverage

All test suites were built and verified with 100% pass rates:
* `scratch/test_onboarding_bootstrap.py` — Fresh user workspace initialization in isolated directory.
* `scratch/test_persona_creation_action.py` — Autonomous `[CREATE_PERSONA]` tag execution and dynamic `/switch` mounting.
* `scratch/test_server_endpoints.py` — FastAPI REST and Vault Backlink endpoints.
* `scratch/test_cli_theme.py` — Visual layout, typography, and Rich Markdown rendering.
