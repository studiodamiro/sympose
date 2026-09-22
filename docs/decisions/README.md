# Decision records

Lightweight records for anything durable — a new dependency, or a decision that outlives the task it was made in (architecture, security posture, what's deliberately deferred). Format and rationale: `docs/CODE_QUALITY_STANDARDS.md` §9.

The original records 001–006 (backend dependencies, the legacy port strategy, and the architecture they described) were removed on 2026-09-22 along with the `sympose/`/`ui/` code they documented — that implementation was rebuilt from an empty slate rather than kept, so the decisions no longer applied. Numbering restarted from 001 below.

| # | Decision | Status |
|---|---|---|
| [001](001-never-commit-persona-memory.md) | Never commit persona memory, regardless of handle | Accepted |
| [002](002-search-and-grounding-share-one-matcher.md) | Grounding reuses search's matcher instead of a separate retrieval system | Accepted |
| [003](003-multi-vault-configured-list-plus-settings-file.md) | Multi-vault: a comma-separated configured list, one active vault, a new settings-file store | Accepted |
| [004](004-add-vault-from-the-switcher.md) | Add a vault from the workspace switcher, persisted alongside the env-configured list | Accepted |
| [005](005-cli-mock-built-on-textual.md) | CLI mock built on Textual, not `prompt_toolkit` | Accepted |
