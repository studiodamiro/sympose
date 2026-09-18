---
title: "Configuration Reference"
created: 2026-09-08
type: wiki-reference
parent: index
tags:
  - sympose/reference
  - config
---

# ⚙️ Configuration Reference

> **Generated from `sympose/config_schema.py` — do not edit by hand.**
> Regenerate with `python -m sympose.config_reference > docs/wiki/reference/configuration.md`.

Every runtime knob Sympose reads. Global keys live in `config.yaml`, settable at runtime with `/config set <key> <value>`; persona keys live in `profiles/<handle>.yaml`, settable with `/persona set @<handle> <key> <value>`. **Live = yes** takes effect immediately; **restart** needs a fresh process.

## Performance & Streaming

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `performance.request_timeout` | float | `30.0` | ≥ 1 | yes | Cloud-model HTTP timeout, seconds. |
| `performance.local_request_timeout` | float | `120.0` | ≥ 1 | yes | Local (ollama/…) model timeout, seconds. |
| `performance.local_keep_alive` | str | *(unset)* | — | yes | Ollama residency hint: -1 forever, 0 unload, '30m'. Unset = defer to OLLAMA_KEEP_ALIVE. |
| `performance.local_model_keep_alive` | dict | `{}` | — | yes | Per-model Ollama residency override, keyed by exact model id (e.g. "ollama/llama3.1:8b": "30m"). Wins over a persona's own keep_alive and local_keep_alive above — the right place to set this once two or more personas share the same local model, since keep_alive is a property of the loaded model, not the persona calling it. Edit config.yaml directly; not settable via `/config set`. |
| `performance.max_context_turns` | int | `15` | ≥ 1 | yes | Conversation turns kept in the model context window. |
| `performance.resume_context_turns` | int | `6` | ≥ 0 | yes | Turns rehydrated when resuming a saved session. |
| `performance.max_sub_agent_tool_turns` | int | `8` | ≥ 1 | yes | Tool-call budget for a sub-agent before a forced synthesis. |
| `performance.max_consecutive_bot_turns` | int | `3` | ≥ 1 | yes | Bot-to-bot reply streak cap in a Slack thread. |
| `performance.slack_thread_context_limit` | int | `12` | ≥ 0 | yes | Preceding Slack thread messages pulled into a turn's context. |
| `performance.slack_max_concurrent` | int | `3` | ≥ 1 | yes | Max concurrently-handled Slack messages. |
| `performance.hygiene_workers` | int | `2` | ≥ 1 | **restart** | Background hygiene thread-pool size (extraction, titling, compaction). |
| `performance.drop_unsupported_params` | bool | `True` | — | yes | Silently drop model params a backend rejects (litellm.drop_params). |
| `performance.stream` | bool | `True` | — | yes | Stream model output token-by-token. |
| `performance.render_mode` | str | `hybrid` | `raw` \| `hybrid` \| `buffered` | yes | Terminal render mode. |
| `performance.local_simple_max_tokens` | int | `200` | ≥ 1 | yes | Response length cap for a SIMPLE-tier reply routed to a persona's local_model (ADR-122). Bounds worst-case wait independent of hardware/warm state — the local model's tokens/sec doesn't change, so a short cap is what actually keeps a trivial reply fast. |

## Session & Memory

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `session.exit_behavior.auto_save` | bool | `False` | — | yes | Auto-save the session on exit. |
| `session.exit_behavior.default_target` | str | `memory` | `memory` \| `vault` \| `both` | yes | Where an auto-saved session goes. |
| `session.exit_behavior.clear_terminal` | bool | `True` | — | yes | Clear the terminal on exit. |
| `session.exit_behavior.obsidian_subfolder` | str | `Sessions` | — | yes | Vault subfolder for archived sessions. |
| `session.exit_behavior.summarization_model` | str | *(unset)* | — | yes | Model for session summaries; empty = the active chat model. |
| `session.exit_behavior.title_timeout` | float | `4.0` | ≥ 0 | yes | Timeout for the background session-auto-title generator, seconds. |
| `memory.auto_compact` | bool | `True` | — | yes | Auto-compact working memory past the threshold. |
| `memory.compaction_threshold` | int | `25` | ≥ 1 | yes | Working-memory line count that triggers compaction. |
| `memory.extraction_timeout` | float | `8.0` | ≥ 0 | yes | Timeout for the background memory extractor, seconds. |
| `memory.user_profile_file` | str | `profiles/user_profile.md` | — | **restart** | Path to the core user profile. |
| `memory.shared_memory_file` | str | `profiles/_shared_memory.md` | — | **restart** | Path to the shared team memory pool. |

## Runtime

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `runtime.default_persona` | str | `samantha` | — | yes | Persona loaded at startup. |
| `runtime.profiles_dir` | str | `profiles` | — | **restart** | Directory holding persona YAMLs. |

## Vault

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `vault.search_mode` | str | `direct` | `direct` \| `sqlite_fts` \| `semantic` | yes | Vault search backend. |
| `vault.grounding_default` | str | `auto` | `auto` \| `strict` \| `trust` | yes | Vault-grounding enforcement when a persona sets no vault_grounding. auto = strict for local models, trust for cloud. |
| `vault.daily_notes_folder` | str | `Daily` | — | yes | Vault folder for daily notes. |
| `vault.daily_notes_format` | str | `Daily/%Y/%m-%B/%Y-%m-%d.md` | — | yes | strftime path for a daily note. |
| `vault.ignore_folders` | list | `['.obsidian', '.git', 'Attachments', 'Drawings', '.trash']` | — | yes | Folders excluded from vault search and indexing. |
| `vault.search_triggers` | list | `[]` | — | yes | Extra keywords that flag a message as a vault query (added to the built-ins). |
| `vault.manifest.enabled` | bool | `True` | — | yes | Maintain a materialized structural map of the vault (nodes, links, folders) under the workspace for the persona and the dashboard graph (ADR-078). Built lazily on first use; set false to disable entirely. |
| `vault.manifest.check_debounce_seconds` | float | `2.0` | ≥ 0 | yes | Minimum seconds between vault-manifest freshness scans; 0 disables the debounce. |
| `vault.manifest.max_nodes` | int | `0` | ≥ 0 | yes | Cap on vault-manifest nodes (0 = unlimited); guards pathological vaults. |
| `vault.multi_writer_safety` | bool | `False` | — | yes | Enable the optimistic-concurrency guard (ADR-129): callers that pass expected_mtime to write_note/append_note/overwrite_note get a NOTE_CONFLICT instead of silently clobbering a file that changed since they last read it. Off by default so a single writer pays zero cost. Sync-mechanism-agnostic — no assumption about Obsidian Sync specifically; this guards against ANY two concurrent writers, on one machine or many. |

## Sub-Agent Sandbox

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `sub_agent.shell_allowlist` | list | `[]` | — | **restart** | argv[0] allowlist for the sub-agent `run_command` tool (read-only commands only). |
| `sub_agent.shell_command_timeout` | float | `20.0` | ≥ 1 | yes | Hard wall-clock cap on a single `run_command` execution, seconds. |
| `sub_agent.request_timeout` | float | `120.0` | ≥ 1 | yes | A sub-agent's own LLM call timeout, seconds - one call per tool-use turn, up to max_sub_agent_tool_turns of them. Deliberately separate from performance.request_timeout: that one bounds a live, streamed chat reply's TTFT, but a sub-agent's report is delivered as a single block once the whole tool-calling loop finishes, so there's no TTFT reason to use the short cloud timeout even when its model is a cloud one. |
| `sub_agent.unsupported_synthesis_min_words` | int | `15` | ≥ 1 | yes | Minimum word count before a sub-agent's synthesis is checked for verbatim overlap with what it actually retrieved (_content_unsupported) - below this, a reply is too short to reliably judge. Live-tuned once already (25 -> 15) after a real fabrication slipped under the original bar; expect to retune this in either direction as more live failures surface. |

## Model Capability Tiers

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `models.capability_tier_order` | list | `['basic', 'standard', 'high']` | — | yes | Ordered least-to-most-capable tier names for capability-based routing (ADR-127) — position in this list is what's compared, not the label text. A separate axis from local-vs-cloud (ADR-122): a sufficiently capable local model can clear a 'high' requirement, and a cloud model can be assigned 'basic'. |
| `models.capability_tiers` | dict | `{}` | — | yes | Explicit model-id -> tier-name assignment (value must be one of models.capability_tier_order). A model with no entry here defaults to the lowest declared tier — conservative by default, same bias as ADR-122's is_simple_message. Edit config.yaml directly (dict, not settable via `/config set`), e.g.: {"ollama/qwen2.5-32b-instruct": "high", "gemini/gemini-3.6-flash": "standard"}. |

## LLM Wiki (Tier 3, opt-in)

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `wiki.root` | str | *(unset)* | — | yes | Vault-relative root folder for the AI-owned LLM-wiki subtree (ADR-132). Empty (default) disables the wiki layer entirely — no wiki_ingest/wiki_lint skill has anywhere to act until this is set. |
| `wiki.raw_sources_subdir` | str | `Sources` | — | yes | Subfolder under wiki.root holding immutable original sources — read by wiki skills, never edited. |
| `wiki.schema_file` | str | `WIKI.md` | — | yes | Filename at wiki.root: the navigation schema explaining how the wiki is structured, seeded once and safe to hand-edit afterward. |
| `wiki.log_file` | str | `log.md` | — | yes | Filename at wiki.root: chronological, append-only ingest/lint audit trail. |

## Persona (set in profiles/<handle>.yaml)

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `vault_grounding` | str | `auto` | `auto` \| `strict` \| `trust` | yes | Per-persona grounding: auto|strict|trust. |
| `keep_alive` | str | *(unset)* | — | yes | Per-persona Ollama keep_alive override. |
| `share_memory` | bool | `False` | — | yes | Write to the shared team memory pool instead of private memory. |
| `temperature` | float | *(unset)* | 0–2 | yes | Sampling temperature. |
| `model` | str | *(unset)* | — | yes | litellm model id (e.g. gemini/gemini-3.6-flash, ollama/llama3.1:8b). |
| `local_model` | str | *(unset)* | — | yes | Ollama model id for SIMPLE-tier messages (ADR-122) — definitions, quick math, a plain greeting. Empty = routing disabled, every message goes to `model` as today. Meaningless (leave unset) for a persona whose `model` is already local — there's no cheaper tier to route to, and no cloud fallback should ever fire for them. |
| `capability_min_tier` | str | *(unset)* | — | yes | Opt-in (ADR-135): route by declared capability tier (models.capability_tier_order/capability_tiers, ADR-127) instead of ADR-122's SIMPLE-message heuristic — every message this persona sends (not just short/trivial ones) routes to local_model whenever its declared tier clears this floor, falling back to `model` otherwise. Empty (default) = today's SIMPLE-message-only behavior, unchanged. Meaningless without local_model also set. |
| `api_base` | str | *(unset)* | — | yes | Custom API base URL for the persona's model. |
| `lint_auto_fix` | bool | `False` | — | yes | ADR-134: when this persona runs the wiki_lint skill, allow it to edit flagged pages directly under wiki.root instead of only logging findings to log.md. Off by default — user-trusted opt-in, your call whether to trust this persona to self-correct its own wiki pages. Has no effect on a persona without the wiki_lint skill, or when wiki.root is unset. |

