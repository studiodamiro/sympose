---
title: "Sympose — Project Journal & ADR Index"
created: 2026-08-24
type: journal
parent: index
tags:
  - sympose/journal
  - engineering/standard
---

# Sympose — Project Journal & ADR Index

Master index for the engineering journal (`docs/journal/YYYY-MM/`). Chronological
milestones and Architectural Decision Records, newest first.

> **Project:** Sympose — Zero-Bloat Multi-Model AI Agent Hub & Sovereign Vault Explorer
> **Lead Architect:** damiro · **Engineering Partner:** Grace (Rear Admiral Grace Hopper persona)

Every formal decision lives in its own
`docs/journal/YYYY-MM/YYYY-MM-DD_adr-NNN-topic-slug.md` file. This table and the
one in [`docs/wiki/index.md`](./wiki/index.md) are kept in sync per the
[documentation standard](../.agents/rules/documentation_standards.md) (B.4).

## Architectural Decision Records

| ADR | Title | Status | Date | Source |
| --- | ----- | ------ | ---- | ------ |
| ADR-075 | Persona Soul Content in CREATE_PERSONA | Accepted | 2026-09-05 | [2026-09-05_adr-075-persona-soul-content-in-create-persona.md](./journal/2026-09/2026-09-05_adr-075-persona-soul-content-in-create-persona.md) |
| ADR-074 | Default Persona Vault Scope & Onboarding Persona-Genesis Nudge | Accepted | 2026-09-05 | [2026-09-05_adr-074-default-persona-vault-scope-and-onboarding-genesis-nudge.md](./journal/2026-09/2026-09-05_adr-074-default-persona-vault-scope-and-onboarding-genesis-nudge.md) |
| ADR-073 | Worker Native-Shell Command Allowlisting & Symlink-Safe Path Checks | Accepted | 2026-09-04 | [2026-09-04_adr-073-worker-native-shell-allowlisting.md](./journal/2026-09/2026-09-04_adr-073-worker-native-shell-allowlisting.md) |
| ADR-072 | Engine Concurrency Model & Bounded Background Hygiene Pool | Accepted | 2026-09-04 | [2026-09-04_adr-072-engine-concurrency-bounded-background-hygiene.md](./journal/2026-09/2026-09-04_adr-072-engine-concurrency-bounded-background-hygiene.md) |
| ADR-071 | Primary-Agent Action Dispatch — Bracket-Tag DSL vs Native Function Calling | Accepted | 2026-09-04 | [2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md](./journal/2026-09/2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md) |
| ADR-070 | Hot-Path Vault Retrieval Budget, Trigger Discipline & Indexed Search Tier | Accepted | 2026-09-04 | [2026-09-04_adr-070-hot-path-retrieval-budget-trigger-discipline.md](./journal/2026-09/2026-09-04_adr-070-hot-path-retrieval-budget-trigger-discipline.md) |
| ADR-065 | MCP Client Threading & Logging Standard | Accepted | 2026-08-30 | [2026-08-30_adr-065-mcp-client-threading-logging-standard.md](./journal/2026-08/2026-08-30_adr-065-mcp-client-threading-logging-standard.md) |
| ADR-064 | Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan | Accepted | 2026-08-30 | [2026-08-30_adr-064-dashboard-api-auth-plan.md](./journal/2026-08/2026-08-30_adr-064-dashboard-api-auth-plan.md) |
| ADR-069 | Live Stream Markdown Parsing for Real-Time Badges & Sub-Agent Reports | Accepted | 2026-08-29 | [2026-08-29_adr-069-live-stream-markdown-parsing.md](./journal/2026-08/2026-08-29_adr-069-live-stream-markdown-parsing.md) |
| ADR-068 | Sub-Agent Worker Report Panel Styling & Redundant Synthesis Gating | Accepted | 2026-08-29 | [2026-08-29_adr-068-subagent-worker-report-panel-styling.md](./journal/2026-08/2026-08-29_adr-068-subagent-worker-report-panel-styling.md) |
| ADR-067 | Intelligent Ghost Session Pruning & Substantive Conversation Gating | Accepted | 2026-08-29 | [2026-08-29_adr-067-ghost-session-pruning.md](./journal/2026-08/2026-08-29_adr-067-ghost-session-pruning.md) |
| ADR-066 | Terminal Markdown Presentation Standard (vault_recall) & Beautified Sub-Agent Orchestration | Accepted | 2026-08-29 | [2026-08-29_adr-066-terminal-markdown-presentation-standard.md](./journal/2026-08/2026-08-29_adr-066-terminal-markdown-presentation-standard.md) |
| ADR-063 | System-Wide LLM Timeout Hardening | Accepted | 2026-08-29 | [2026-08-29_adr-063-system-wide-llm-timeout-hardening.md](./journal/2026-08/2026-08-29_adr-063-system-wide-llm-timeout-hardening.md) |
| ADR-062 | render_mode: raw Panel Suppression in the Action Executor | Accepted | 2026-08-29 | [2026-08-29_adr-062-render-mode-raw-panel-suppression.md](./journal/2026-08/2026-08-29_adr-062-render-mode-raw-panel-suppression.md) |
| ADR-061 | Sub-Agent [READ_NOTE] Explicit-Intent Gating | Accepted | 2026-08-29 | [2026-08-29_adr-061-subagent-read-note-explicit-intent-gating.md](./journal/2026-08/2026-08-29_adr-061-subagent-read-note-explicit-intent-gating.md) |
| ADR-060 | Three-Way Terminal Render Mode Knob (performance.render_mode) | Accepted | 2026-08-29 | [2026-08-29_adr-060-terminal-render-mode-knob.md](./journal/2026-08/2026-08-29_adr-060-terminal-render-mode-knob.md) |
| ADR-059 | Repository-Wide Clean Range Prompts & Graceful Asynchronous Signal Interruption (SIGINT) | Accepted | 2026-08-29 | [2026-08-29_adr-059-clean-range-prompts-signal-interruption.md](./journal/2026-08/2026-08-29_adr-059-clean-range-prompts-signal-interruption.md) |
| ADR-058 | MultiSectionPanel In-Terminal Note Viewer with Inline T-Junction Box Dividers | Accepted | 2026-08-29 | [2026-08-29_adr-058-multisectionpanel-in-terminal-note-viewer.md](./journal/2026-08/2026-08-29_adr-058-multisectionpanel-in-terminal-note-viewer.md) |
| ADR-057 | Orderly Structured Vault Retrieval & Single-Line Context Excerpts | Accepted | 2026-08-29 | [2026-08-29_adr-057-structured-vault-retrieval-context-excerpts.md](./journal/2026-08/2026-08-29_adr-057-structured-vault-retrieval-context-excerpts.md) |
| ADR-056 | Retirement of Automated Vault Session Dumping in Favor of Native History Sovereignty | Accepted | 2026-08-29 | [2026-08-29_adr-056-retire-automated-vault-session-dumping.md](./journal/2026-08/2026-08-29_adr-056-retire-automated-vault-session-dumping.md) |
| ADR-055 | Milestone-Based Asynchronous Titling & Generic Prompt Filtering | Accepted | 2026-08-29 | [2026-08-29_adr-055-milestone-based-async-titling.md](./journal/2026-08/2026-08-29_adr-055-milestone-based-async-titling.md) |
| ADR-054 | Zero-Bloat Conversation Persistence (.jsonl), Decoupled UI History & Sliding Context Window Hydration | Accepted | 2026-08-29 | [2026-08-29_adr-054-jsonl-conversation-persistence-context-hydration.md](./journal/2026-08/2026-08-29_adr-054-jsonl-conversation-persistence-context-hydration.md) |
| ADR-053 | Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers | Accepted | 2026-08-29 | [2026-08-29_adr-053-cross-platform-native-desktop-launchers.md](./journal/2026-08/2026-08-29_adr-053-cross-platform-native-desktop-launchers.md) |
| ADR-052 | In-Memory Metadata Caching & Sub-5ms Scalability Standard | Accepted | 2026-08-29 | [2026-08-29_adr-052-in-memory-metadata-caching-scalability.md](./journal/2026-08/2026-08-29_adr-052-in-memory-metadata-caching-scalability.md) |
| ADR-051 | Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine | Accepted | 2026-08-29 | [2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md](./journal/2026-08/2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md) |
| ADR-050 | Interactive Skill Command Suite (/skill & /skills) with Tab Auto-Completion | Accepted | 2026-08-29 | [2026-08-29_adr-050-interactive-skill-command-suite.md](./journal/2026-08/2026-08-29_adr-050-interactive-skill-command-suite.md) |
| ADR-049 | Robust Code-Fence Action Tag Parsing & Dynamic Cache Resolution | Accepted | 2026-08-29 | [2026-08-29_adr-049-code-fence-action-tag-parsing.md](./journal/2026-08/2026-08-29_adr-049-code-fence-action-tag-parsing.md) |
| ADR-048 | Dynamic 3-Tier Model Hierarchy & Runtime Fallback Architecture | Accepted | 2026-08-29 | [2026-08-29_adr-048-dynamic-3-tier-model-hierarchy.md](./journal/2026-08/2026-08-29_adr-048-dynamic-3-tier-model-hierarchy.md) |
| ADR-047 | Standardized Sympose CLI Design System (SYMPOSE_THEME) & Typography Standard | Accepted | 2026-08-29 | [2026-08-29_adr-047-cli-design-system-typography.md](./journal/2026-08/2026-08-29_adr-047-cli-design-system-typography.md) |
| ADR-046 | Samantha-Only Clean Slate & Dynamic Autonomic Persona Genesis | Accepted | 2026-08-29 | [2026-08-29_adr-046-samantha-only-clean-slate-persona-genesis.md](./journal/2026-08/2026-08-29_adr-046-samantha-only-clean-slate-persona-genesis.md) |
| ADR-045 | Modern Standalone Python Packaging (pyproject.toml) & Sovereign User Workspace | Accepted | 2026-08-29 | [2026-08-29_adr-045-standalone-packaging-sovereign-workspace.md](./journal/2026-08/2026-08-29_adr-045-standalone-packaging-sovereign-workspace.md) |
| ADR-044 | In-Memory Inverted Index & Deterministic Backlink Lookup Engine | Accepted | 2026-08-27 | [2026-08-27_adr-044-in-memory-inverted-index-backlink-engine.md](./journal/2026-08/2026-08-27_adr-044-in-memory-inverted-index-backlink-engine.md) |
| ADR-043 | Three-Layer Architectural Separation (Soul vs Skill vs System Physics) | Accepted | 2026-08-27 | [2026-08-27_adr-043-three-layer-separation-soul-skill-physics.md](./journal/2026-08/2026-08-27_adr-043-three-layer-separation-soul-skill-physics.md) |
| ADR-042 | Autonomous Live Internet Search (web_search) & Zero-Key ddgs Standard | Accepted | 2026-08-27 | [2026-08-27_adr-042-autonomous-live-internet-search.md](./journal/2026-08/2026-08-27_adr-042-autonomous-live-internet-search.md) |
| ADR-041 | Multi-Turn Slack Thread Active Context Isolation & Single-Source Action Execution | Accepted | 2026-08-27 | [2026-08-27_adr-041-slack-thread-active-context-isolation.md](./journal/2026-08/2026-08-27_adr-041-slack-thread-active-context-isolation.md) |
| ADR-040 | Native Obsidian Templates/ Engine & Dynamic Frontmatter Tag Syncing | Accepted | 2026-08-27 | [2026-08-27_adr-040-native-obsidian-templates-frontmatter-sync.md](./journal/2026-08/2026-08-27_adr-040-native-obsidian-templates-frontmatter-sync.md) |
| ADR-039 | Modular vault_write Skill, Obsidian Wikilink Taxonomy & Nested Hierarchies | Accepted | 2026-08-27 | [2026-08-27_adr-039-vault-write-skill-wikilink-taxonomy.md](./journal/2026-08/2026-08-27_adr-039-vault-write-skill-wikilink-taxonomy.md) |
| ADR-038 | Post-Remediation Hardening & Defensive Engineering Standards | Accepted | 2026-08-26 | [2026-08-26_adr-038-defensive-engineering-hardening-standards.md](./journal/2026-08/2026-08-26_adr-038-defensive-engineering-hardening-standards.md) |
| ADR-037 | Pure Declarative Markdown-Driven Prompting & Zero-Code Injections | Accepted | 2026-08-26 | [2026-08-26_adr-037-pure-declarative-markdown-prompting.md](./journal/2026-08/2026-08-26_adr-037-pure-declarative-markdown-prompting.md) |
| ADR-036 | Multi-Agent Collaboration Protocol, Discussion Moderation & Safety Circuit Breaker | Accepted | 2026-08-26 | [2026-08-26_adr-036-multi-agent-collaboration-circuit-breaker.md](./journal/2026-08/2026-08-26_adr-036-multi-agent-collaboration-circuit-breaker.md) |
| ADR-035 | Evidence-Based Grounding & Epistemic Humility Standard | Accepted | 2026-08-26 | [2026-08-26_adr-035-evidence-based-grounding-epistemic-humility.md](./journal/2026-08/2026-08-26_adr-035-evidence-based-grounding-epistemic-humility.md) |
| ADR-034 | Autonomous Slack Emotion & Reaction Autonomy | Accepted | 2026-08-26 | [2026-08-26_adr-034-autonomous-slack-reaction-autonomy.md](./journal/2026-08/2026-08-26_adr-034-autonomous-slack-reaction-autonomy.md) |
| ADR-033 | Zero-Key Native Web Search & the ddgs Standard | Accepted | 2026-08-26 | [2026-08-26_adr-033-zero-key-native-web-search-ddgs.md](./journal/2026-08/2026-08-26_adr-033-zero-key-native-web-search-ddgs.md) |
| ADR-032 | First-Class mcp/ Directory Hierarchy & Modular Hub Refactor | Accepted | 2026-08-26 | [2026-08-26_adr-032-first-class-mcp-directory-modular-hub.md](./journal/2026-08/2026-08-26_adr-032-first-class-mcp-directory-modular-hub.md) |
| ADR-031 | Slack Thread Deletion, Command Ergonomics & Memory Sovereignty | Accepted | 2026-08-26 | [2026-08-26_adr-031-slack-thread-deletion-command-ergonomics.md](./journal/2026-08/2026-08-26_adr-031-slack-thread-deletion-command-ergonomics.md) |
| ADR-030 | High-Density Folder Digests & Universal Ban on Time-Delay Simulation | Accepted | 2026-08-26 | [2026-08-26_adr-030-high-density-folder-digests-zero-delay.md](./journal/2026-08/2026-08-26_adr-030-high-density-folder-digests-zero-delay.md) |
| ADR-029 | Assume Interruption Meta-Directive & Write-Through State Checkpointing | Accepted | 2026-08-25 | [2026-08-25_adr-029-assume-interruption-write-through-state.md](./journal/2026-08/2026-08-25_adr-029-assume-interruption-write-through-state.md) |
| ADR-028 | Slack Socket Mode Integration & Thread Context Isolation | Accepted | 2026-08-25 | [2026-08-25_adr-028-slack-socket-mode-thread-context-isolation.md](./journal/2026-08/2026-08-25_adr-028-slack-socket-mode-thread-context-isolation.md) |
| ADR-027 | Config-Driven Spatial Compass & Complete Vault Agnosticism | Accepted | 2026-08-25 | [2026-08-25_adr-027-config-driven-spatial-compass.md](./journal/2026-08/2026-08-25_adr-027-config-driven-spatial-compass.md) |
| ADR-026 | Sub-Agent Worker Spatial Environment & Inherited Sandbox Security | Accepted | 2026-08-25 | [2026-08-25_adr-026-subagent-worker-spatial-environment-sandbox.md](./journal/2026-08/2026-08-25_adr-026-subagent-worker-spatial-environment-sandbox.md) |
| ADR-025 | Persistent Multi-Turn Vault Context & Conversational Intent Stripping | Accepted | 2026-08-25 | [2026-08-25_adr-025-persistent-multi-turn-vault-context.md](./journal/2026-08/2026-08-25_adr-025-persistent-multi-turn-vault-context.md) |
| ADR-024 | The Ground-Truth Sovereignty Axiom & Anti-Simulation Directives | Accepted | 2026-08-25 | [2026-08-25_adr-024-ground-truth-sovereignty-axiom.md](./journal/2026-08/2026-08-25_adr-024-ground-truth-sovereignty-axiom.md) |
| ADR-023 | Centralized Vault Ignore Filters | Accepted | 2026-08-25 | [2026-08-25_adr-023-centralized-vault-ignore-filters.md](./journal/2026-08/2026-08-25_adr-023-centralized-vault-ignore-filters.md) |
| ADR-022 | Local-First Hierarchical Retrieval & Noise Pruning (vault_recall) | Accepted | 2026-08-25 | [2026-08-25_adr-022-local-first-hierarchical-retrieval.md](./journal/2026-08/2026-08-25_adr-022-local-first-hierarchical-retrieval.md) |
| ADR-021 | Hierarchical Daily Notes & Vault-Agnostic Format Resolvers | Accepted | 2026-08-25 | [2026-08-25_adr-021-hierarchical-daily-notes-format-resolvers.md](./journal/2026-08/2026-08-25_adr-021-hierarchical-daily-notes-format-resolvers.md) |
| ADR-020 | The Zero-Maintenance Mandate & The Assistant Paradox | Accepted | 2026-08-25 | [2026-08-25_adr-020-zero-maintenance-mandate.md](./journal/2026-08/2026-08-25_adr-020-zero-maintenance-mandate.md) |
| ADR-019 | Automated Memory Compaction & Distillation Protocol | Accepted | 2026-08-25 | [2026-08-25_adr-019-automated-memory-compaction-distillation.md](./journal/2026-08/2026-08-25_adr-019-automated-memory-compaction-distillation.md) |
| ADR-018 | Multi-Model Concierge Integration (sympose_mastery) | Accepted | 2026-08-25 | [2026-08-25_adr-018-multi-model-concierge-integration.md](./journal/2026-08/2026-08-25_adr-018-multi-model-concierge-integration.md) |
| ADR-017 | Dynamic OpenRouter Model Discovery & Live Catalog Search | Accepted | 2026-08-25 | [2026-08-25_adr-017-openrouter-model-discovery-live-catalog.md](./journal/2026-08/2026-08-25_adr-017-openrouter-model-discovery-live-catalog.md) |
| ADR-016 | Skill-Driven Sub-Agent Worker Model Auto-Resolution | Accepted | 2026-08-25 | [2026-08-25_adr-016-skill-driven-worker-model-auto-resolution.md](./journal/2026-08/2026-08-25_adr-016-skill-driven-worker-model-auto-resolution.md) |
| ADR-015 | Multi-Provider Routing & Explicit OpenRouter Key Injection | Accepted | 2026-08-25 | [2026-08-25_adr-015-multi-provider-routing-openrouter-key-injection.md](./journal/2026-08/2026-08-25_adr-015-multi-provider-routing-openrouter-key-injection.md) |
| ADR-014 | Deterministic Native Tools & In-Turn Proactive Synthesis | Accepted | 2026-08-24 | [2026-08-24_adr-014-deterministic-native-tools-in-turn-synthesis.md](./journal/2026-08/2026-08-24_adr-014-deterministic-native-tools-in-turn-synthesis.md) |
| ADR-013 | Model Context Protocol & Ephemeral Sub-Agent Worker Sandbox | Accepted | 2026-08-24 | [2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md](./journal/2026-08/2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md) |
| ADR-012 | Modular Procedural Skills System (SKILL.md) | Accepted | 2026-08-24 | [2026-08-24_adr-012-modular-procedural-skills-system.md](./journal/2026-08/2026-08-24_adr-012-modular-procedural-skills-system.md) |
| ADR-011 | Multi-Folder Vault Whitelisting & Full-Vault Access Architecture | Accepted | 2026-08-24 | [2026-08-24_adr-011-multi-folder-vault-whitelisting.md](./journal/2026-08/2026-08-24_adr-011-multi-folder-vault-whitelisting.md) |
| ADR-010 | Selective Memory Sharing & Universal User Profile Architecture | Accepted | 2026-08-24 | [2026-08-24_adr-010-selective-memory-sharing-universal-user-profile.md](./journal/2026-08/2026-08-24_adr-010-selective-memory-sharing-universal-user-profile.md) |
| ADR-009 | Autonomous Agent Vault Read/Write Access & Action Protocol | Accepted | 2026-08-24 | [2026-08-24_adr-009-autonomous-agent-vault-access-action-protocol.md](./journal/2026-08/2026-08-24_adr-009-autonomous-agent-vault-access-action-protocol.md) |
| ADR-008 | Heuristic-Gated Shadow Memory Extractor | Accepted | 2026-08-24 | [2026-08-24_adr-008-heuristic-gated-shadow-memory-extractor.md](./journal/2026-08/2026-08-24_adr-008-heuristic-gated-shadow-memory-extractor.md) |
| ADR-007 | Strict Memory Grounding, Anti-Hallucination & Honest Ignorance | Accepted | 2026-08-24 | [2026-08-24_adr-007-memory-grounding-anti-hallucination.md](./journal/2026-08/2026-08-24_adr-007-memory-grounding-anti-hallucination.md) |
| ADR-006 | Autonomous Soul & Memory Bootstrapping | Accepted | 2026-08-24 | [2026-08-24_adr-006-autonomous-soul-memory-bootstrapping.md](./journal/2026-08/2026-08-24_adr-006-autonomous-soul-memory-bootstrapping.md) |
| ADR-005 | Centralized config.yaml, Session Summarization & Memory Consolidation | Accepted | 2026-08-24 | [2026-08-24_adr-005-config-yaml-session-summarization-memory.md](./journal/2026-08/2026-08-24_adr-005-config-yaml-session-summarization-memory.md) |
| ADR-004 | Industry-Standard Modular Package Architecture | Accepted | 2026-08-24 | [2026-08-24_adr-004-modular-package-architecture.md](./journal/2026-08/2026-08-24_adr-004-modular-package-architecture.md) |
| ADR-003 | Pluggable Multi-Tier Vault Search Architecture | Accepted | 2026-08-24 | [2026-08-24_adr-003-pluggable-multi-tier-vault-search.md](./journal/2026-08/2026-08-24_adr-003-pluggable-multi-tier-vault-search.md) |
| ADR-002 | Master Vault Domain Sandboxing & Access Control | Accepted | 2026-08-24 | [2026-08-24_adr-002-master-vault-domain-sandboxing.md](./journal/2026-08/2026-08-24_adr-002-master-vault-domain-sandboxing.md) |
| ADR-001 | Core Runtime & Execution Resilience | Accepted | 2026-08-24 | [2026-08-24_adr-001-core-runtime-execution-resilience.md](./journal/2026-08/2026-08-24_adr-001-core-runtime-execution-resilience.md) |

> **ADR-060 – ADR-063 numbering.** Two sets of decisions drafted on 2026-08-29
> both claimed the numbers 060–063. The *Terminal Render Mode Knob* set keeps
> 060–063 (its introducing commit named those topics); the *Structured Vault
> Search* session's four extra decisions were renumbered to **ADR-066 – ADR-069**
> during the 2026-09 documentation-standard conformance pass. No decision content
> changed.

## Milestones

| Date | Entry |
| ---- | ----- |
| 2026-09-05 | [Typewriter Reveal for `buffered` Render Mode](./journal/2026-09/2026-09-05_typewriter-reveal-buffered-mode.md) |
| 2026-09-05 | [Animated Thinking Status](./journal/2026-09/2026-09-05_animated-thinking-status.md) |
| 2026-09-05 | [Persona Soul Content Implementation (ADR-075)](./journal/2026-09/2026-09-05_persona-soul-content-implementation.md) |
| 2026-09-05 | [ADR-075 — Persona Soul Content in CREATE_PERSONA](./journal/2026-09/2026-09-05_adr-075-persona-soul-content-in-create-persona.md) |
| 2026-09-05 | [ADR-074 — Default Persona Vault Scope & Onboarding Persona-Genesis Nudge](./journal/2026-09/2026-09-05_adr-074-default-persona-vault-scope-and-onboarding-genesis-nudge.md) |
| 2026-09-05 | [Repository Shareability Pass, Part 2 (SECURITY.md, repo topics, private vulnerability reporting)](./journal/2026-09/2026-09-05_repo-shareability-pass-part2.md) |
| 2026-09-05 | [Repository Shareability Pass (LICENSE, CI, pyproject urls)](./journal/2026-09/2026-09-05_repo-shareability-pass.md) |
| 2026-09-05 | [`sqlite_fts` Indexed Vault Search, Tier 5 (ADR-070.5 / F3 — closes the review)](./journal/2026-09/2026-09-05_backend-hardening-tier5-sqlite-fts.md) |
| 2026-09-04 | [Backend Hardening Implementation, Tier 4 (ADR-071, ADR-073, ADR-064 all accepted)](./journal/2026-09/2026-09-04_backend-hardening-tier4-implementation.md) |
| 2026-09-04 | [Backend Hardening Implementation — Tiers 1–3 (ADR-070, ADR-072 accepted; ADR-071, ADR-064 amended)](./journal/2026-09/2026-09-04_backend-hardening-implementation.md) |
| 2026-09-04 | [Backend Architecture & Objective-Effectiveness Review (ADR-070 – ADR-073)](./journal/2026-09/2026-09-04_backend-architecture-effectiveness-review.md) |
| 2026-08-30 | [Ui Scaffold Documentation And Clean Slate](./journal/2026-08/2026-08-30_ui_scaffold_documentation_and_clean_slate.md) |
| 2026-08-30 | [MCP Client Threading & Logging Standard](./journal/2026-08/2026-08-30_mcp_client_threading_and_logging_standard.md) |
| 2026-08-30 | [Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan](./journal/2026-08/2026-08-30_dashboard_api_security_design_gap_and_auth_plan.md) |
| 2026-08-29 | [Web Dashboard Ui Ux And 3D Knowledge Nebula](./journal/2026-08/2026-08-29_web_dashboard_ui_ux_and_3d_knowledge_nebula.md) |
| 2026-08-29 | [Terminal Render Mode Knob, Sub-Agent `[READ_NOTE]` Discipline & System-Wide Timeout Hardening (ADR-060 – ADR-063)](./journal/2026-08/2026-08-29_terminal_render_mode_subagent_discipline_and_timeout_hardening.md) |
| 2026-08-29 | [Orderly Structured Vault Search (`/vault`), Inline T-Junction Note Viewer, Signal Interruption (`SIGINT`) & Systematic Prompt Ergonomics (ADR-057 – ADR-059)](./journal/2026-08/2026-08-29_structured_vault_search_note_viewer_and_prompt_ergonomics.md) |
| 2026-08-29 | [Standalone Python Packaging, Sovereign Onboarding Wizard & Standardized CLI Design System (ADR-045 – ADR-048)](./journal/2026-08/2026-08-29_sovereign_packaging_and_cli_design_system.md) |
| 2026-08-29 | [Action Parser Hardening & Interactive `/skill` Command Suite](./journal/2026-08/2026-08-29_skill_command_suite_and_action_parser_hardening.md) |
| 2026-08-29 | [Conversation History Persistence (`/history`), Milestone Smart Titling & Zero-Pollution Memory Sovereignty (ADR-054 – ADR-056)](./journal/2026-08/2026-08-29_conversation_history_and_session_resumption.md) |
| 2026-08-27 | [Vault Write Obsidian Templates And Live Web Search](./journal/2026-08/2026-08-27_vault_write_obsidian_templates_and_live_web_search.md) |
| 2026-08-27 | [Backlink Lookup Engine And Inverted Index](./journal/2026-08/2026-08-27_backlink_lookup_engine_and_inverted_index.md) |
| 2026-08-26 | [Zero-Key Native Web Search & DDGS Standard](./journal/2026-08/2026-08-26_zero_key_native_web_search_and_ddgs_standard.md) |
| 2026-08-26 | [Slack Thread Deletion, Command Ergonomics & Memory Sovereignty](./journal/2026-08/2026-08-26_slack_thread_deletion_and_command_ergonomics.md) |
| 2026-08-26 | [Pure Declarative Markdown-Driven Prompting & Zero-Code Injections](./journal/2026-08/2026-08-26_pure_declarative_markdown_prompting.md) |
| 2026-08-26 | [Post-Remediation Hardening & Defensive Engineering Standards](./journal/2026-08/2026-08-26_post_remediation_hardening_and_defensive_engineering_standards.md) |
| 2026-08-26 | [Multi-Agent Collaboration Protocol, Discussion Moderation & Safety Circuit Breaker](./journal/2026-08/2026-08-26_multi_agent_collaboration_and_circuit_breaker.md) |
| 2026-08-26 | [First-Class MCP Directory & Modular Hub Refactor](./journal/2026-08/2026-08-26_mcp_directory_segregation_and_modular_hub.md) |
| 2026-08-26 | [High-Density Folder Digests & Zero Time-Delay Simulation Standard](./journal/2026-08/2026-08-26_high_density_folder_digests_and_zero_delay_simulation.md) |
| 2026-08-26 | [Evidence-Based Grounding & Epistemic Humility Standard](./journal/2026-08/2026-08-26_evidence_based_grounding_and_epistemic_humility.md) |
| 2026-08-26 | [Autonomous Slack Emotion & Reaction Autonomy](./journal/2026-08/2026-08-26_autonomous_slack_reaction_engine.md) |
| 2026-08-25 | [Hierarchical Daily Notes, Vault Agnosticism & Local-First Recall](./journal/2026-08/2026-08-25_vault_recall_and_hierarchical_daily_notes.md) |
| 2026-08-25 | [Architecture Decision Record: Slack Socket Mode Integration & Thread-Bound Multi-Agent Routing](./journal/2026-08/2026-08-25_slack_socket_mode_integration.md) |
| 2026-08-25 | [Multi-Model Routing, OpenRouter Integration & Dynamic Model Discovery](./journal/2026-08/2026-08-25_openrouter_and_model_catalog.md) |
| 2026-08-25 | [Architecture Decision Records: Ground-Truth Sovereignty & Config-Driven Spatial Compass](./journal/2026-08/2026-08-25_ground_truth_sovereignty_and_spatial_compass.md) |
| 2026-08-25 | [Developer Workflow Architecture & Daemon Persistence Standard](./journal/2026-08/2026-08-25_developer_workflows_and_daemon_persistence.md) |
| 2026-08-25 | [Automated Memory Compactor & Working Memory Hygiene](./journal/2026-08/2026-08-25_automated_memory_compactor.md) |
| 2026-08-25 | [Architecture Decision Record: "Assume Interruption" & Proactive Write-Through State Memory](./journal/2026-08/2026-08-25_assume_interruption_and_write_through_memory.md) |
| 2026-08-24 | [Modular Skills & MCP Ephemeral Sub-Agent Worker Architecture](./journal/2026-08/2026-08-24_skills_and_mcp_workers.md) |
| 2026-08-24 | [Selective Memory Sharing & Universal User Profile](./journal/2026-08/2026-08-24_selective_memory_sharing.md) |
| 2026-08-24 | [Multi-Folder Vault Access & Flexible Domain Whitelists](./journal/2026-08/2026-08-24_multi_folder_vault.md) |
| 2026-08-24 | [Foundation Review & Modular Architecture Refactor](./journal/2026-08/2026-08-24_foundation_review.md) |
| 2026-08-24 | [Autonomous Agent Vault Read/Write Access & Action Protocols](./journal/2026-08/2026-08-24_agent_vault_access.md) |

## Technical Standards & Guides

- **[Autonomous Agent Memory Architecture Standard](./wiki/memory/architecture-standard.md):** triad memory management, anti-hallucination grounding, shadow extraction, and Obsidian integration.
- **[Latency & Performance Tuning Guide](./wiki/guides/latency-tuning.md):** the catalog of knobs, timeouts, context windows, and model configuration governing the sub-second SLA.
- **[Slack Socket Mode Setup Guide](./wiki/guides/slack-setup.md):** 1-click app manifest, Socket Mode, and multi-agent Slack deployment.
- **[Web Dashboard & Standalone Vault Explorer](./wiki/architecture/dashboard-and-vault-explorer.md):** architectural blueprint for the web dashboard, knowledge graph, chat stream, and vault explorer.
- **[Web Dashboard UI Design Reference](./wiki/reference/ui-design-reference.md):** the flat "Sovereign Craft" design brief — theme presets, semantic tokens, layout shell, per-screen artboards — derived from ADR-047 and ADR-051–053.
- **[Wiki Documentation Hub](./wiki/index.md):** skills, MCP workers, profile system, and command references.
