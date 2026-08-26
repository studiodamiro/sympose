---
entry: 2026-08-24
created: 2026-08-24 14:38
type: index
project: sympose
tags:
  - index
  - sympose/master-journal
---

# Sympose Master Journal Index

> **Project:** Sympose Multi-Model Agent Hub  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  

This master document serves as the top-level index and Table of Contents.  
**Daily logs are kept in dedicated individual files inside [`docs/journal/`](journal) under `YYYY-MM-DD_topic_slug.md`.**

---

## Daily Engineering Entries

| Date | Topic / Focus | Status | Daily Log File |
| :--- | :--- | :--- | :--- |
| **2026-08-24** | Foundation Review, Phase 1A/1B Delivery & ADR-001 through ADR-008 | Complete | [`2026-08-24_foundation_review.md`](journal/2026-08-24_foundation_review.md) |
| **2026-08-24** | Autonomous Agent Vault Read/Write Access & Action Protocols (ADR-009) | Complete | [`2026-08-24_agent_vault_access.md`](journal/2026-08-24_agent_vault_access.md) |
| **2026-08-24** | Selective Memory Sharing & Universal User Profile Architecture (ADR-010) | Complete | [`2026-08-24_selective_memory_sharing.md`](journal/2026-08-24_selective_memory_sharing.md) |
| **2026-08-24** | Multi-Folder Vault Access & Flexible Domain Whitelists (ADR-011) | Complete | [`2026-08-24_multi_folder_vault.md`](journal/2026-08-24_multi_folder_vault.md) |
| **2026-08-24** | Modular Skills (`SKILL.md`) & MCP Ephemeral Sub-Agent Workers (ADR-012, ADR-013, ADR-014) | Complete | [`2026-08-24_skills_and_mcp_workers.md`](journal/2026-08-24_skills_and_mcp_workers.md) |
| **2026-08-25** | Dynamic OpenRouter Discovery, Model Catalog & Auto-Resolution (ADR-017, ADR-018, ADR-019) | Complete | [`2026-08-25_openrouter_and_model_catalog.md`](journal/2026-08-25_openrouter_and_model_catalog.md) |
| **2026-08-25** | Autonomous Memory Compactor & Zero-Maintenance Mandate (ADR-020) | Complete | [`2026-08-25_automated_memory_compactor.md`](journal/2026-08-25_automated_memory_compactor.md) |
| **2026-08-25** | Hierarchical Daily Notes, Vault Agnosticism & Local-First Recall (ADR-021, ADR-022, ADR-023) | Complete | [`2026-08-25_vault_recall_and_hierarchical_daily_notes.md`](journal/2026-08-25_vault_recall_and_hierarchical_daily_notes.md) |
| **2026-08-25** | Ground-Truth Sovereignty Axiom & Config-Driven Spatial Compass (ADR-024, ADR-025, ADR-026, ADR-027) | Complete | [`2026-08-25_ground_truth_sovereignty_and_spatial_compass.md`](journal/2026-08-25_ground_truth_sovereignty_and_spatial_compass.md) |
| **2026-08-25** | Slack Socket Mode Integration & Thread-Bound Routing (ADR-028) | Complete | [`2026-08-25_slack_socket_mode_integration.md`](journal/2026-08-25_slack_socket_mode_integration.md) |
| **2026-08-25** | Developer Workflows, IDE Ergonomics & Daemon Persistence Standard | Complete | [`2026-08-25_developer_workflows_and_daemon_persistence.md`](journal/2026-08-25_developer_workflows_and_daemon_persistence.md) |
| **2026-08-25** | "Assume Interruption" & Proactive Write-Through State Memory (ADR-029) | Complete | [`2026-08-25_assume_interruption_and_write_through_memory.md`](journal/2026-08-25_assume_interruption_and_write_through_memory.md) |
| **2026-08-26** | High-Density Folder Digests & Zero Time-Delay Simulation Standard (ADR-030) | Complete | [`2026-08-26_high_density_folder_digests_and_zero_delay_simulation.md`](journal/2026-08-26_high_density_folder_digests_and_zero_delay_simulation.md) |
| **2026-08-26** | Slack Thread Deletion, Command Ergonomics & Memory Sovereignty (ADR-031) | Complete | [`2026-08-26_slack_thread_deletion_and_command_ergonomics.md`](journal/2026-08-26_slack_thread_deletion_and_command_ergonomics.md) |
| **2026-08-26** | First-Class MCP Directory & Modular Hub Refactor (ADR-032) | Complete | [`2026-08-26_mcp_directory_segregation_and_modular_hub.md`](journal/2026-08-26_mcp_directory_segregation_and_modular_hub.md) |
| **2026-08-26** | Zero-Key Native Web Search & DDGS Standard (ADR-033) | Complete | [`2026-08-26_zero_key_native_web_search_and_ddgs_standard.md`](journal/2026-08-26_zero_key_native_web_search_and_ddgs_standard.md) |
| **2026-08-26** | Autonomous Slack Emotion & Reaction Autonomy (ADR-034) | Complete | [`2026-08-26_autonomous_slack_reaction_engine.md`](journal/2026-08-26_autonomous_slack_reaction_engine.md) |
| **2026-08-26** | Evidence-Based Grounding & Epistemic Humility Standard (ADR-035) | Complete | [`2026-08-26_evidence_based_grounding_and_epistemic_humility.md`](journal/2026-08-26_evidence_based_grounding_and_epistemic_humility.md) |

---

## Architectural Decision Records (ADR Index)

* **[ADR-001 (2026-08-24): Core Runtime Resilience](journal/2026-08-24_foundation_review.md#adr-001-core-runtime--execution-resilience):**
  * *ADR-001.1:* Smart Sliding Window (15–20 Turns) vs. 6-Turn Truncation
  * *ADR-001.2:* Defensive File Access for Obsidian Vault
  * *ADR-001.3:* Local Ollama Offline Resilience
  * *ADR-001.4:* Phased 4-Step Build Sequence
  * *ADR-001.5:* Zero-Latency Explicit API Key Resolution
* **[ADR-002 (2026-08-24): Master Vault Domain Sandboxing](journal/2026-08-24_foundation_review.md#adr-002-master-vault-domain-sandboxing--access-control):**
  * Strict folder-level sandboxing (`/General`, `/Engineering`, `/Personal`) per agent profile.
  * Hard security boundary (`is_safe_path()`) preventing cloud models from inspecting private notes.
* **[ADR-003 (2026-08-24): Pluggable Multi-Tier Vault Search Architecture](journal/2026-08-24_foundation_review.md#adr-003-pluggable-multi-tier-vault-search-architecture):**
  * Configurable search mode: `direct` (Pure Python), `sqlite_fts` (Ranked BM25), `semantic` (Local Vector Embeddings).
* **[ADR-004 (2026-08-24): Industry-Standard Modular Package Architecture](journal/2026-08-24_foundation_review.md#adr-004-industry-standard-modular-package-architecture):**
  * Segregated monolithic runtime into a clean `sympose/` package (`config`, `profiles`, `vault`, `engine`, `cli`), reducing `app.py` to a lean 35-line entry point.
* **[ADR-005 (2026-08-24): Centralized `config.yaml`, Session Summarization & Memory Consolidation](journal/2026-08-24_foundation_review.md#adr-005-centralized-configyaml-session-summarization--memory-consolidation):**
  * Root `config.yaml` for performance and exit flow tuning.
  * Automated session distillation on `/exit` and on-demand `/save`.
  * Dynamic in-session `/config` and `/config set` parameter inspection and live override.
  * Clean terminal reset and memory consolidation into `_memory.md` and Obsidian.
* **[ADR-006 (2026-08-24): Autonomous Soul & Memory Bootstrapping](journal/2026-08-24_foundation_review.md#adr-006-autonomous-soul--memory-bootstrapping-zero-friction-agent-creation):**
  * Moved `thinking_phrases` to YAML manifests (zero prompt token overhead).
  * Auto-generation of `_soul.md`, `_memory.md`, and spinner phrases from a minimal 4-line YAML manifest on initial launch.
* **[ADR-007 (2026-08-24): Strict Memory Grounding & GCE Metadata Probe Bypass](journal/2026-08-24_foundation_review.md#adr-007-strict-memory-grounding-anti-hallucination--honest-ignorance-standard):**
  * Zero-tolerance anti-hallucination protocol for working memory truthfulness.
  * `NO_GCE_CHECK=True` & `GOOGLE_CLOUD_DISABLE_METADATA=true` to eliminate the 10s–300s socket hang on macOS.
* **[ADR-008 (2026-08-24): Heuristic Gated Shadow Memory Extractor](journal/2026-08-24_foundation_review.md#adr-008-heuristic-gated-shadow-memory-extractor):**
  * Asynchronous, non-blocking background daemon thread for silent user intent and plan extraction.
  * Dual-filter regex gate skipping 80%+ of chit-chat turns for near-zero token overhead.
  * Automatic deduplication preventing redundant memory line writes.
* **[ADR-009 (2026-08-24): Autonomous Agent Vault Read/Write Access & Action Protocols](journal/2026-08-24_agent_vault_access.md#adr-009-autonomous-agent-vault-readwrite-access--action-protocol):**
  * Zero-latency autonomic action tags (`[WRITE_NOTE]`, `[APPEND_NOTE]`, `[DAILY_NOTE]`, `[REMEMBER]`).
  * Dedicated `ActionProcessor` module (`sympose/actions.py`) for parsing and badging file operations.
  * Instantaneous (<3ms) pre-turn grounded retrieval for note reading and vault searches.
* **[ADR-010 (2026-08-24): Selective Memory Sharing & Universal User Profile Architecture](journal/2026-08-24_selective_memory_sharing.md#adr-010-selective-memory-sharing--universal-user-profile-architecture):**
  * Universal User Card (`profiles/user_profile.md`) loaded by all personas for zero-friction identity awareness.
  * Configurable `share_memory: true | false` per profile manifest.
  * Shared team memory pool (`profiles/_shared_memory.md`) for collaborative agents (Samantha & Grace) while keeping offline agents (Aurelius) 100% private and air-gapped.
* **[ADR-011 (2026-08-24): Multi-Folder Vault Access & Flexible Domain Whitelists](journal/2026-08-24_multi_folder_vault.md#adr-011-multi-folder-vault-whitelisting--full-vault-access-architecture):**
  * Multi-Folder Whitelist (`vault_folders: [...]`) allowing agents to access multiple directories in existing Obsidian vaults.
  * Full-vault root access (`vault_folders: ["*"]` or `vault_folder: ""`) for unrestricted domain coverage.
  * Cross-directory note reading, searching, and sandboxed security enforcement.
* **[ADR-012 (2026-08-24): Modular Procedural Skills System (`SKILL.md`)](journal/2026-08-24_skills_and_mcp_workers.md#adr-012-modular-procedural-skills-system-skillmd):**
  * Standard open format `skills/<name>/SKILL.md` (frontmatter metadata + markdown instructions).
  * Auto-mounting in agent manifests (`skills: [...]`) and dynamic prompt compilation via `sympose/skills.py`.
  * Mandatory deliverable schemas for non-code and strategic analysis skills.
* **[ADR-013 (2026-08-24): Model Context Protocol (MCP) & Ephemeral Sub-Agent Workers](journal/2026-08-24_skills_and_mcp_workers.md#adr-013-model-context-protocol-mcp--ephemeral-sub-agent-worker-sandbox):**
  * Standard-library JSON-RPC 2.0 stdio client bridge (`sympose/mcp.py`) for community MCP tool servers.
  * Isolated sub-agent sandbox (`sympose/workers.py`) preventing chat context pollution and saving 5,000+ tokens per turn.
  * Autonomic delegation tag `[SPAWN_WORKER: ... | ...]` and configurable `performance.max_worker_tool_turns: 8`.
* **[ADR-014 (2026-08-24): Deterministic Native Execution Tools & In-Turn Proactive Synthesis](journal/2026-08-24_skills_and_mcp_workers.md#adr-014-deterministic-native-tools--in-turn-proactive-synthesis):**
  * Real macOS execution (`subprocess.run`, file I/O) in `sympose/native_tools.py`, eliminating worker simulation/hallucination.
  * In-turn proactive synthesis loop in `sympose/engine.py` delivering instant executive summaries right after tool execution in a single conversational turn.
* **[ADR-015 (2026-08-24): Autonomic Runtime Configuration & Master 7-Point Agent Prerequisite Standard](journal/2026-08-24_skills_and_mcp_workers.md#adr-015-autonomic-runtime-configuration--master-7-point-agent-prerequisite-standard):**
  * Autonomic tag `[CONFIG_SET: <key> | <value>]` in `sympose/actions.py` to persist `config.yaml` updates live from conversational natural language.
  * `skills/sympose_mastery/SKILL.md` turning the default orchestrator (Samantha) into a full runtime concierge and sysadmin.
  * Master 7-Point Agent Prerequisite Standard governing complete, zero-defect agent creation.
* **[ADR-016 (2026-08-24): Complete Agent Lifecycle: Autonomic Genesis & Defensive Retirement Archiving](journal/2026-08-24_skills_and_mcp_workers.md#adr-016-complete-agent-lifecycle-autonomic-genesis--defensive-retirement-archiving):**
  * Autonomic tag `[CREATE_PERSONA: <handle> | <yaml>]` for instant declarative agent onboarding.
  * Autonomic tag `[DELETE_PERSONA: <handle>]` and slash command `/delete @<handle>` / `/retire @<handle>` implementing defensive soft-delete archiving to `profiles/_archived/<handle>/` while preserving Obsidian notes.
  * Dynamic `reload_profiles()` on `/switch` and `list_personas()`.
* **[ADR-017 (2026-08-25): Multi-Provider Routing & Explicit OpenRouter Key Injection](journal/2026-08-25_openrouter_and_model_catalog.md#adr-015-multi-provider-routing--explicit-openrouter-key-injection):**
  * Explicit OpenRouter API key routing and provider prefixes across engine, workers, and memory modules.
* **[ADR-018 (2026-08-25): Skill-Driven Sub-Agent Worker Model Auto-Resolution](journal/2026-08-25_openrouter_and_model_catalog.md#adr-016-skill-driven-sub-agent-worker-model-auto-resolution):**
  * 4-tier worker resolution hierarchy prioritizing `task.model` $\rightarrow$ `skill.recommended_models[0]` $\rightarrow$ `DEFAULT_MODEL` $\rightarrow$ system fallback.
* **[ADR-019 (2026-08-25): Dynamic OpenRouter Model Discovery & Live Catalog Search](journal/2026-08-25_openrouter_and_model_catalog.md#adr-017-dynamic-openrouter-model-discovery--live-catalog-search-symposemodelspy):**
  * `ModelCatalog` with 24-hour disk caching, `/model find <keyword>` search, `/model refresh`, and Readline Tab autocompletion.
* **[ADR-020 (2026-08-25): The Zero-Maintenance Mandate & Automated Memory Compaction](journal/2026-08-25_automated_memory_compactor.md#adr-020-the-zero-maintenance-mandate--the-assistant-paradox):**
  * Autonomous `MemoryCompactor` with configurable line threshold (default: 25 lines) for background deduplication and conflict resolution across persona and shared memory files.
* **[ADR-021 (2026-08-25): Hierarchical Daily Notes & Vault-Agnostic Format Resolvers](journal/2026-08-25_vault_recall_and_hierarchical_daily_notes.md#adr-021-hierarchical-daily-notes--vault-agnostic-format-resolvers):**
  * Configurable `vault.daily_notes_format` (`Daily/%Y/%m-%B/%Y-%m-%d.md`) matching Obsidian Periodic Notes standards.
  * Enshrined the Vault Agnosticism Mandate across user profiles and shared memories.
* **[ADR-022 (2026-08-25): Local-First Hierarchical Retrieval & Noise Pruning (`vault_recall`)](journal/2026-08-25_vault_recall_and_hierarchical_daily_notes.md#adr-022-local-first-hierarchical-retrieval--noise-pruning-vault_recall):**
  * 3-tier retrieval funnel (Tier 0 deterministic filter $\to$ Tier 1 local LLM triage on Qwen 2.5/Gemma 2 $\to$ Tier 2 frontier deep reasoning).
  * Reusable `vault_recall` skill playbook with high-density anchor extraction (`## Key Decisions`, `## Action Items`, `### Reflection`).
* **[ADR-023 (2026-08-25): Centralized Vault Ignore Filters](journal/2026-08-25_vault_recall_and_hierarchical_daily_notes.md#adr-023-centralized-vault-ignore-filters):**
  * Centralized `vault.ignore_folders` in `config.yaml` with dynamic `os.walk` directory pruning across `.obsidian`, `Attachments`, `Drawings`, `.git`, `.trash`.
* **[ADR-024 (2026-08-25): The Ground-Truth Sovereignty Axiom & Anti-Simulation Directives](journal/2026-08-25_ground_truth_sovereignty_and_spatial_compass.md#adr-024-the-ground-truth-sovereignty-axiom--anti-simulation-directives):**
  * Codified that Markdown documents on disk are the sovereign single source of truth; models are transient cognitive processors reading the file data bus.
  * Mandatory verbatim quotation (`> blockquote`) and complete prohibition of action roleplaying or fabricated dates.
* **[ADR-025 (2026-08-25): Persistent Multi-Turn Vault Context & Conversational Intent Stripping](journal/2026-08-25_ground_truth_sovereignty_and_spatial_compass.md#adr-025-persistent-multi-turn-vault-context-selfactive_vault_ctx--conversational-intent-stripping):**
  * Stateful `self.active_vault_ctx` on `PersonaEngine` retaining retrieved notes across follow-up conversational turns.
  * Conversational preamble and boilerplate stripping isolating entity keywords (`movies`, `quotes`, `projects`) and dates (`2017`, `2018`).
* **[ADR-026 (2026-08-25): Sub-Agent Worker Spatial Environment & Inherited Sandbox Security](journal/2026-08-25_ground_truth_sovereignty_and_spatial_compass.md#adr-026-sub-agent-worker-spatial-environment--inherited-sandbox-security):**
  * Inherited sandbox enforcement passing parent agent's `allowed_dirs` to sub-agents, preventing privilege escalation into private folders (like `Daily/`).
  * Direct injection of `MASTER_VAULT_PATH` into worker environment prompts and `NativeTools.read_file()`.
  * Multi-tool command blocking in `NativeTools.run_command()` preventing unauthorized shell queries against restricted vault subdirectories.
  * Fuzzy skill name resolution (`VaultHistoricalRecall` $\to$ `vault_recall`) and alignment with installed local model weights.
* **[ADR-027 (2026-08-25): Config-Driven Spatial Compass & Complete Vault Agnosticism](journal/2026-08-25_ground_truth_sovereignty_and_spatial_compass.md#adr-027-config-driven-spatial-compass--complete-vault-agnosticism):**
  * Zero hardcoded folder paths in codebase or skills. Centralized path configuration in `.env` and `config.yaml`.
  * Multi-dimensional dynamic discovery supporting Flat, PARA, Johnny Decimal, and Zettelkasten structures.
* **[ADR-028 (2026-08-25): Slack Socket Mode Integration & Thread Context Isolation](journal/2026-08-25_slack_socket_mode_integration.md#adr-028-slack-socket-mode-integration--thread-context-isolation):**
  * Zero inbound ports using `slack-bolt` and `SocketModeHandler`.
  * Thread-bound multi-agent session isolation preventing conversational crosstalk across channels.
  * Intelligent `@handle` mention parsing, automatic persona routing, and instant reaction SLA feedback.

---

## Technical Standards & Guides
* **[Autonomous Agent Memory Architecture Standard](MEMORY_ARCHITECTURE_STANDARD.md):** The definitive standard for triad memory management, anti-hallucination grounding, shadow extraction, and Obsidian integration.
* **[Latency & Performance Tuning Guide](LATENCY_TUNING_GUIDE.md):** Complete catalog of knobs, timeouts, context windows, and model configurations governing sub-second SLA.
* **[Wiki Documentation Hub](wiki/index.md):** Comprehensive guide to skills, MCP workers, profile systems, and command references.
