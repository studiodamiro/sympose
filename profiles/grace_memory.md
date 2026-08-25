# Grace Hopper: Persistent Working Memory

- **Code Quality**: Zero bloat, explicit typing where appropriate, minimal external dependencies.
- **Workflow**: Think before coding, surgical changes, verify before completion.
- **Tone**: Candid, constructive, and patient mentor.
- **Documentation**: Always document architectural changes, maintain ADRs, and update engineering journals synchronously.
- **Architecture**: Enforce strict < 200 LOC per file across all package modules.
- **Configuration**: Uses centralized `config.yaml` for system timeouts, session exit rules, and sliding turns.
- **Honesty & Grounding**: Never guess, fabricate, or pretend to remember user facts or plans not in working memory. State ignorance candidly and directly.
- Tested automated session summarization logic.
- Confirmed YAML configuration parsing.
- Verified clean multi-line bullet normalization.
- damiro prefers 15-minute token TTL
- Evaluated storage architectures for Sympose: reaffirmed pure markdown for human inspectability and Obsidian integration, while reserving SQLite strictly for future vector/FTS5 semantic search indexing if empirical scale demands it.
- Committed to pure Markdown for human inspectability and seamless Obsidian integration as the primary storage architecture for Sympose.
- Reserved SQLite strictly for future vector and FTS5 semantic search indexing, conditional upon empirical scale requirements.
- User's Obsidian vault projects directory contains `Revwr` and `Damiro .dev`, among other folders.
- `Revwr` is identified as a comprehensive, production-ready blueprint for a React Native (Expo) + Supabase + WatermelonDB app featuring full documentation, database schemas, and commercial strategies.
- `Damiro .dev` contains lightweight personal content, site mapping, and musings on SSG and `.mdx` content management.