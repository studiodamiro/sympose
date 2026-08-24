# Shared Team Working Memory (Collaborative Agents)

- **Active Project**: Sympose Multi-Model Agent Hub
- **Architecture**: Modular Python package (`sympose/`) with strict <200 LOC per file.
- **Tech Stack**: Python 3.12, LiteLLM, Rich, PyYAML, Obsidian Markdown Vault.
- **Performance SLA**: Sub-second TTFT (<1.0s) streaming.

- Evaluated storage architectures for Sympose: reaffirmed pure markdown for human inspectability and Obsidian integration, while reserving SQLite strictly for future vector/FTS5 semantic search indexing if empirical scale demands it.
- Committed to pure Markdown for human inspectability and seamless Obsidian integration as the primary storage architecture for Sympose.
- Reserved SQLite strictly for future vector and FTS5 semantic search indexing, conditional upon empirical scale requirements.
- Hot & cold knee A+ sizing chart is ready for review.
- Created @curie (Marie Curie) as the Principal Research Specialist agent in Sympose.