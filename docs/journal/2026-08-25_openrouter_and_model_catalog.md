---
entry: 2026-08-25
created: 2026-08-25 14:42
type: daily-log
project: sympose
tags:
  - sympose/models
  - sympose/openrouter
  - sympose/commands
  - architecture/model-catalog
---

# 🧠 Engineering Journal: Multi-Model Routing, OpenRouter Integration & Dynamic Model Discovery

> **Date:** August 25, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)

---

## 🎯 Focus & Objectives

1. Implement zero-bloat, transparent multi-provider LLM routing with first-class **OpenRouter** support.
2. Enable seamless in-session model inspection, live overrides, and resets via the `/model` CLI command.
3. Build a lightweight, non-blocking **Model Catalog Manager (`sympose/models.py`)** with 24-hour disk caching for real-time model discovery (`/model find <keyword>` and `/model refresh`).
4. Implement automatic **Skill-Driven Worker Model Auto-Resolution** so ephemeral workers run optimal domain models specified in `SKILL.md` frontmatter.
5. Equip the orchestrator (@samantha) via `sympose_mastery` with autonomous multi-model concierge heuristics.

---

## 🏗️ Architectural Decisions Recorded (ADR Index)

### ADR-015: Multi-Provider Routing & Explicit OpenRouter Key Injection

- **Context**: Sympose uses `litellm` for backend completions. While LiteLLM reads standard environment variables, our explicit key handshake in `engine.py`, `workers.py`, and `memory.py` lacked explicit branching for `openrouter/` models, which caused ambiguity for new users with OpenRouter credits.
- **Decision**:
  - Explicitly inject `OPENROUTER_API_KEY` across all completion invocation points (`engine.py`, `workers.py`, `memory.py`) whenever an `openrouter/*` model is targeted.
  - Standardize model naming prefixes (`openrouter/<provider>/<model>`, `gemini/<model>`, `anthropic/<model>`, `openai/<model>`, `ollama/<model>`).
  - Updated `.env.example` and `quickstart.md` to establish OpenRouter as a first-class supported provider.

---

### ADR-016: Skill-Driven Sub-Agent Worker Model Auto-Resolution

- **Context**: Specialized skills (e.g. `code_review`, `system_architecture`) perform best when paired with high-precision models (like Claude Sonnet or DeepSeek Pro), while simple lookup skills can run on lightweight models.
- **Decision**: Adopt a 4-tier worker model resolution hierarchy in `sympose/workers.py`:
  1. **Explicit Task Override**: `WorkerTask(..., model="...")` passed programmatically.
  2. **Skill Frontmatter Recommendation**: First entry from `recommended_models:` in the loaded skill's `SKILL.md`.
  3. **Global Environment Variable**: `DEFAULT_MODEL` configured in `.env`.
  4. **System Fallback**: `gemini/gemini-3.5-flash-lite`.

---

### ADR-017: Dynamic OpenRouter Model Discovery & Live Catalog Search (`sympose/models.py`)

- **Context**: OpenRouter adds dozens of cutting-edge models weekly. Static lists become stale quickly, but network-blocking on every keystroke hurts CLI latency.
- **Decision**:
  - Created `sympose/models.py` (`ModelCatalog`) with a 24-hour local disk cache (`~/.sympose_models_cache.json`).
  - Implemented `/model find <keyword>` (or `/model search <keyword>`) to query the cached catalog instantaneously with context lengths and pricing information.
  - Implemented `/model refresh` to force-sync the latest catalog directly from OpenRouter's API on demand.
  - Augmented `sympose/completer.py` with intelligent Readline Tab auto-completion for `/model`, `/model find <term>`, and dynamic `openrouter/*` slug completion.

---

### ADR-018: Multi-Model Concierge Integration (`sympose_mastery`)

- **Context**: Users asking natural language questions about model choices or provider setup should be guided conversationally by the orchestrator (@samantha).
- **Decision**: Updated `skills/sympose_mastery/SKILL.md` with Section 7 ("Multi-Model & OpenRouter Concierge") to guide users on task-specific model selection (coding vs reasoning vs distillation) and interactive `/model` command usage.

---

## 🧪 Verification & Metrics

- **Unit Test Suites**:
  - `scratch/test_model_routing.py`: 3/3 tests passing (`0.000s`) verifying skill recommended model extraction and key injection.
  - `scratch/test_model_command.py`: 5/5 tests passing (`8.24s` including live API refresh) verifying `/model`, `/model find`, `/model refresh`, `/model reset`, and Readline Tab completions.
- **Modularity Standard Compliance**:
  - `sympose/models.py`: 102 LOC
  - `sympose/completer.py`: 189 LOC
  - `sympose/workers.py`: 188 LOC
  - `sympose/commands.py`: 333 LOC (structured sub-command generators)
