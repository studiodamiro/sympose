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
| [013](013-record-ttft-every-turn.md) | Record time-to-first-token on every turn: stream the model call internally, store `ttft_ms` + `model` per turn | Accepted |
| [014](014-dedicated-grounding-retriever.md) | A dedicated grounding retriever: passages and keyword scoring, precision over recall, not the search bar's matcher | Accepted |
| [015](015-context-budget.md) | Context budget: an overflowing prompt is cut silently, so the engine sizes it (measured on Ollama and `gemma2:9b` only) | Accepted |
| [016](016-show-grounded-notes-in-the-cli.md) | Show which notes grounded a reply in the CLI reply header, fitted to width, behind a `show_grounding` knob and `/grounding` | Accepted |
| [017](017-follow-up-aware-grounding.md) | Follow-up-aware grounding: retrieve first, rewrite a search-less message from recent turns on a miss, behind a mode knob | Accepted |
| [018](018-context-meter.md) | A context meter under the chat box: the share of the prompt budget in use, from the engine's own count, behind a `show_context_meter` knob | Accepted |
| [019](019-sympose-reference-library.md) | A Sympose reference library: read-only notes about Sympose itself, shipped in the package, searched by the same retriever in a strict mode, Samantha only | Proposed |
| [020](020-prompt-in-one-place.md) | The chat prompt in one place: the notes travel with the question, and the model is told how Sympose works | Proposed |
| [021](021-weak-evidence-asks-the-rewrite.md) | Weak evidence is not enough to ground a reply: address names and typed contractions are filler, and a one-word match is checked by the rewrite step | Proposed |
| [022](022-wire-the-reference-library.md) | Wiring the Sympose reference library into a persona's turns: a per-persona flag, its own labelled block, and what each persona is told | Proposed |
| [023](023-recaps-of-earlier-conversations.md) | Recaps: a short, model-written summary of each earlier conversation, kept in the persona's own folder and read at the start of the next one | Proposed |
| [024](024-general-questions-need-no-note.md) | A general question needs no note: notes attach only on a real share of the message, and she is told she may answer from her own knowledge | Proposed |
| [025](025-record-what-reached-each-turn.md) | Record which notes and recaps reached each turn: paths and session ids on the turn record, never their text, never read back into a prompt | Proposed |
