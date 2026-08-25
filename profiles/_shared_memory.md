# Sympose Multi-Model Agent Hub

- **User**: damiro
- **Architecture**: Modular Python package (`sympose/`) with strict <200 LOC per file.
- **Tech Stack**: Python 3.12, LiteLLM, Rich, PyYAML, Obsidian Markdown Vault.
- **Performance SLA**: Sub-second TTFT (<1.0s) streaming.
- **Storage Architecture**: Pure Markdown for human inspectability and Obsidian integration as primary storage; SQLite reserved strictly for future vector/FTS5 semantic search indexing if empirical scale demands it.
- **System Model Tiers**: `gemini/gemini-3.5-flash-lite`, `openrouter/google/gemini-3.7-flash`, `openrouter/anthropic/claude-sonnet-4.5`, and `openrouter/deepseek/deepseek-v4-pro`.
- **Active Agent Profiles on Disk (`profiles/`)**: `@samantha`, `@grace`, and `@aurelius`. (Note: `@curie` was discussed as a Principal Research Specialist concept, but her files were never written to disk, omitting her from the `/switch` menu).
- **Project Assets**: Hot & cold knee A+ sizing chart is ready for review.
