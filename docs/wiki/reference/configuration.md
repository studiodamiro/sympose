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
| `performance.max_context_turns` | int | `15` | ≥ 1 | yes | Conversation turns kept in the model context window. |
| `performance.resume_context_turns` | int | `6` | ≥ 0 | yes | Turns rehydrated when resuming a saved session. |
| `performance.max_worker_tool_turns` | int | `8` | ≥ 1 | yes | Tool-call budget for a sub-agent worker before a forced synthesis. |
| `performance.max_consecutive_bot_turns` | int | `3` | ≥ 1 | yes | Bot-to-bot reply streak cap in a Slack thread. |
| `performance.slack_thread_context_limit` | int | `12` | ≥ 0 | yes | Preceding Slack thread messages pulled into a turn's context. |
| `performance.slack_max_concurrent` | int | `3` | ≥ 1 | yes | Max concurrently-handled Slack messages. |
| `performance.hygiene_workers` | int | `2` | ≥ 1 | **restart** | Background hygiene thread-pool size (extraction, titling, compaction). |
| `performance.drop_unsupported_params` | bool | `True` | — | yes | Silently drop model params a backend rejects (litellm.drop_params). |
| `performance.stream` | bool | `True` | — | yes | Stream model output token-by-token. |
| `performance.render_mode` | str | `hybrid` | `raw` \| `hybrid` \| `buffered` | yes | Terminal render mode. |

## Session & Memory

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `session.exit_behavior.auto_save` | bool | `False` | — | yes | Auto-save the session on exit. |
| `session.exit_behavior.default_target` | str | `memory` | `memory` \| `vault` \| `both` | yes | Where an auto-saved session goes. |
| `session.exit_behavior.clear_terminal` | bool | `True` | — | yes | Clear the terminal on exit. |
| `session.exit_behavior.obsidian_subfolder` | str | `Sessions` | — | yes | Vault subfolder for archived sessions. |
| `session.exit_behavior.summarization_model` | str | *(unset)* | — | yes | Model for session summaries; empty = the active chat model. |
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
| `vault.ignore_folders` | list | `['.obsidian', '.git', 'Attachments', 'Drawings', 'Movies', '.trash', 'dot-files']` | — | yes | Folders excluded from vault search and indexing. |
| `vault.search_triggers` | list | `[]` | — | yes | Extra keywords that flag a message as a vault query (added to the built-ins). |
| `vault.manifest.enabled` | bool | `False` | — | yes | Maintain a materialized structural map of the vault (nodes, links, folders) under the workspace for the agent and the dashboard graph (ADR-078). |
| `vault.manifest.check_debounce_seconds` | float | `2.0` | ≥ 0 | yes | Minimum seconds between vault-manifest freshness scans; 0 disables the debounce. |
| `vault.manifest.max_nodes` | int | `0` | ≥ 0 | yes | Cap on vault-manifest nodes (0 = unlimited); guards pathological vaults. |

## Worker Sandbox

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `worker.shell_allowlist` | list | `[]` | — | **restart** | argv[0] allowlist for the worker `run_command` tool (read-only commands only). |

## Persona (set in profiles/<handle>.yaml)

| Key | Type | Default | Allowed | Live | Description |
| --- | --- | --- | --- | --- | --- |
| `vault_grounding` | str | `auto` | `auto` \| `strict` \| `trust` | yes | Per-persona grounding: auto|strict|trust. |
| `keep_alive` | str | *(unset)* | — | yes | Per-persona Ollama keep_alive override. |
| `share_memory` | bool | `False` | — | yes | Write to the shared team memory pool instead of private memory. |
| `temperature` | float | *(unset)* | 0–2 | yes | Sampling temperature. |
| `model` | str | *(unset)* | — | yes | litellm model id (e.g. gemini/gemini-3.6-flash, ollama/llama3.1:8b). |
| `api_base` | str | *(unset)* | — | yes | Custom API base URL for the persona's model. |

