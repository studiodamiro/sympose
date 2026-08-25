# Sympose Multi-Model Agent Hub

- **User**: damiro
- **Architecture**: Modular Python package (`sympose/`) with strict <200 LOC per file.
- **Tech Stack**: Python 3.12, LiteLLM, Rich, PyYAML, Obsidian Markdown Vault.
- **Performance SLA**: Sub-second TTFT (<1.0s) streaming.
- **Storage Architecture**: Pure Markdown for human inspectability and Obsidian integration as primary storage; SQLite reserved strictly for future vector/FTS5 semantic search indexing if empirical scale demands it.
- **System Model Tiers**: `gemini/gemini-3.5-flash-lite`, `openrouter/google/gemini-3.7-flash`, `openrouter/anthropic/claude-sonnet-4.5`, `openrouter/deepseek/deepseek-v4-pro`, and open-weights Qwen. Management commands include `/model`, `/model find`, and `/switch`.
- **Active Agent Profiles on Disk (`profiles/`)**: `@samantha`, `@grace`, and `@aurelius`. (`@curie` remains a conceptual Principal Research Specialist whose files were never written to disk, omitting her from the `/switch` menu).
- **Vault Agnosticism & Config-Driven Spatial Compass**: All environmental path resolutions (Obsidian Vault root, folder hierarchies, search targets) are centrally driven by configuration (`.env` and `config.yaml`). Sympose code, tools, and sub-agent workers dynamically navigate wherever the user points their config (`MASTER_VAULT_PATH`), remaining 100% agnostic of directory naming, depth, or location on disk.
- **Project Assets**: Hot & cold knee A+ sizing chart is ready for review.
- **Obsidian Vault Contents**: Includes projects directory containing `Revwr` (a production-ready blueprint for a React Native (Expo) + Supabase + WatermelonDB app with full documentation, database schemas, and commercial strategies) and `Damiro .dev` (lightweight personal content, site mapping, and musings on SSG and `.mdx` content management), among other folders.
