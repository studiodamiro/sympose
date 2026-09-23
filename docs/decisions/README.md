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
| [006](006-chat-engine-v0-shape.md) | Chat engine v0: turn handling, grounding, sessions, and what's deliberately out | Accepted |
| [007](007-litellm-for-model-calls.md) | litellm for model calls, `ollama_chat/` prefix, local-first default | Accepted |
| [008](008-message-queueing.md) | Message queueing: per-persona locks, not one global lock | Accepted |
| [009](009-persona-profile-fail-closed.md) | `profile.py`'s final shape: fail-closed resolution, settings-backed default persona | Accepted |
| [010](010-persona-scoped-graph-model-precedence-default-setter.md) | Persona-scoped nebula graph, model precedence, and a default-persona setter | Accepted |
| [011](011-one-directory-per-persona.md) | One directory per persona: `profiles/<handle>/{persona.yaml, soul.md, memory.md, expertise.md, sessions/}` | Accepted |
| [012](012-persona-soul-is-voice-only.md) | A persona's soul is voice only; engine rules stay in the engine | Accepted |
