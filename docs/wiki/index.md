---
title: "Sympose Wiki: Zero-Bloat Multi-Model AI Persona Hub"
created: 2026-08-24
type: wiki-index
parent: index
tags:
  - sympose/wiki
  - engineering/standard
---

# 🏛️ Sympose Wiki
> **A zero-bloat, sub-second personal AI orchestration hub and dynamic memory system.**

Welcome to the technical documentation and engineering specifications for **Sympose**. Sympose is designed as an unbloated, developer-first alternative to heavyweight multi-agent frameworks, pairing ultra-fast cloud models (Google Gemini, Anthropic Claude) with local, private LLMs (Ollama) under a unified CLI, sandboxed Obsidian vault, and autonomous memory layer.

---

## 🗺️ System Architecture Overview

```mermaid
graph TD
    User([User Interactive REPL / Slack]) --> Engine[PersonaEngine]

    subgraph Core Execution Loop
        Engine --> PM[ProfileManager]
        Engine --> Archivist[SessionArchivist]
        Engine --> Cmds[CommandInterceptor]
        Engine --> VM[VaultManager]
    end

    subgraph Multi-Model Layer [<0.8s SLA]
        Engine --> Gemini[Google Gemini 3.5 Flash-Lite]
        Engine --> Claude[Anthropic Claude 3.5 Sonnet]
        Engine --> Ollama[Local Private Models / Ollama]
    end

    subgraph Autonomous Memory Triad
        PM --> Manifests[profiles/*.yaml Manifests]
        PM --> Souls[profiles/*_soul.md Directives]
        Archivist --> Shadow[Async Shadow Extractor]
        Shadow --> Memory[profiles/*_memory.md]
    end

    subgraph Sandboxed Vault Storage
        VM --> Notes[Obsidian Vault Domain Folders]
        VM --> Backlinks[In-Memory Inverted Index]
    end
```

---

## 📚 Wiki Sections & Deep Dives

### 📐 [Architecture](./architecture/overview.md)
* **[System Overview](./architecture/overview.md):** The Triad pattern separating UI manifest, cognitive directives, and persistent memory.
* **[Sub-Second Latency Engine](./architecture/sub-second-engine.md):** How Sympose achieves 0.75s TTFT on macOS by eliminating GCE metadata server hangs and managing warm connection pools.
* **[MCP & Sub-Agents](./architecture/mcp-and-sub-agents.md):** Isolated, ephemeral sub-agent sandboxes connecting to Model Context Protocol tool servers.
* **[Sandboxed Obsidian Vault](./architecture/sandboxed-vault.md):** Defensive path validation, isolated domain folders, and note search tiers.
* **[Web Dashboard & Standalone Vault Explorer](./architecture/dashboard-and-vault-explorer.md):** UI specification, interactive knowledge graph, multi-persona chat stream, and standalone vault explorer.
* **[LLM Wiki Layer](./architecture/llm-wiki-layer.md):** the opt-in Tier-3 raw-sources/wiki/schema convention and its ingest/query/lint operations.

### 🧠 [Autonomous Memory System](./memory/shadow-extractor.md)
* **[Memory Architecture Standard](./memory/architecture-standard.md):** The definitive triad memory standard — grounding pillars, shadow extraction, and Obsidian integration.
* **[Selective Memory Sharing & Privacy Rings](./memory/selective-sharing.md):** Air-gapping private offline personas (Aurelius) while allowing cloud personas (Samantha & Grace) to share team project memory.
* **[Heuristic Gated Shadow Extractor](./memory/shadow-extractor.md):** Frictionless, zero-keyword memory capture running in detached background daemon threads.
* **[Anti-Hallucination & Grounding](./memory/anti-hallucination.md):** Eliminating sycophancy with the 4 grounding pillars, honest ignorance protocols, and a post-hoc deterministic structural backstop for when a model doesn't comply anyway.
* **[Session Archival & Distillation](./memory/session-archival.md):** Working memory consolidation on exit and sovereign `.jsonl` conversation history.

### 🎭 [Persona & Skills Ecosystem](./personas/profile-system.md)
* **[Profile System & Dynamic Persona Genesis](./personas/profile-system.md):** Seeding Samantha on fresh slate and spinning up new domain specialists on-the-fly.
* **[Modular Skills System (`SKILL.md`)](./personas/skills-system.md):** Reusable procedural heuristics, domain playbooks, and tool bindings.
* **[@samantha](./personas/samantha.md):** Core Starter Master Orchestrator & Concierge.
* **[Specialist Archetypes](./personas/grace.md):** Example blueprints for surgical engineering (`@grace`) and offline local personas (`@aurelius`).

### 🚀 [Guides & Getting Started](./guides/quickstart.md)
* **[Installation, Upgrades & Onboarding](./guides/installation-and-onboarding.md):** 1-Line `pipx` install, upgrade protocols, and interactive setup wizard.
* **[Quickstart Guide](./guides/quickstart.md):** Installation, API keys, and starting the interactive CLI.
* **[Developer Workflows & Daemon Persistence](./guides/developer-workflows.md):** Pair-programming with Grace across Antigravity, VS Code, and background 24/7 Slack daemon.
* **[Slack Integration & Setup](./guides/slack-integration.md):** 1-Click App Manifest, Socket Mode, and multi-persona Slack deployment.
* **[Slack Socket Mode Setup Guide](./guides/slack-setup.md):** The full step-by-step app-manifest walkthrough.
* **[Configuration](./guides/configuration.md):** Schema-defined knobs, `config.yaml`, and in-session `/config` / `/persona` tuning.
* **[Latency & Performance Tuning Guide](./guides/latency-tuning.md):** The catalog of knobs, timeouts, context windows, and model configuration governing the sub-second SLA.
* **[Creating Custom Personas](./guides/creating-personas.md):** Defining new persona models, prompts, and vault permissions.

### 📖 [Reference](./reference/cli-commands.md)
* **[CLI Commands & Shortcuts](./reference/cli-commands.md):** Complete guide to `/save`, `/config`, `/switch`, `/note`, `/daily`, and `/ask`.
* **[Configuration Reference](./reference/configuration.md):** Every runtime knob — type, default, allowed values, live-vs-restart — generated from `config_schema.py`.
* **[Action Tags Reference](./reference/action-tags.md):** Every `[TAG: args]` a persona can emit — `WRITE_NOTE`, `SPAWN_SUB_AGENT`, `CREATE_PERSONA`, and the rest — plus the malformed-tag warning contract.
* **[Python API Reference](./reference/python-api.md):** Package internals, class hierarchies, and integration hooks.
* **[Web Dashboard UI Design Reference](./reference/ui-design-reference.md):** The flat "Sovereign Craft" design brief — theme presets, semantic tokens, layout shell, per-screen artboards.
* **[Vault Agent Capability Reference & Roadmap](./reference/vault-agent-capabilities.md):** What a `vault_read` sub-agent can already do deterministically, what data exists but isn't wired up yet (backlink counting), and what's genuinely unsolved (aggregate counting, full-corpus synthesis).

---

## 🗂️ Engineering Journal & ADR Index

Chronological milestones and Architectural Decision Records live under
`docs/journal/YYYY-MM/`. The master index is
[`docs/PROJECT_JOURNAL.md`](../PROJECT_JOURNAL.md); this table mirrors its ADR
list and is kept in sync per the
[documentation standard](../../.agents/rules/documentation_standards.md) (B.4).

| ADR | Title | Status | Date |
| --- | ----- | ------ | ---- |
| [ADR-138](../journal/2026-09/2026-09-19_adr-138-structural-wiki-lint-write-gate.md) | A Structural Write Gate for Lint-Only wiki_lint Personas | Implemented | 2026-09-19 |
| [ADR-137](../journal/2026-09/2026-09-19_adr-137-splitting-actions-into-focused-modules.md) | Splitting actions.py Into Focused, Under-200-LOC Modules | Implemented | 2026-09-19 |
| [ADR-136](../journal/2026-09/2026-09-19_adr-136-splitting-vault-write-into-focused-modules.md) | Splitting vault_write.py Into Focused, Under-200-LOC Modules | Implemented | 2026-09-19 |
| [ADR-135](../journal/2026-09/2026-09-19_adr-135-capability-tier-routing-for-the-main-turn.md) | Opt-In Capability-Tier Routing for the Main Persona Turn | Implemented | 2026-09-19 |
| [ADR-134](../journal/2026-09/2026-09-19_adr-134-wiki-lint-skill-user-controlled-auto-fix.md) | wiki_lint Skill, With User-Controlled Auto-Fix | Implemented | 2026-09-19 |
| [ADR-133](../journal/2026-09/2026-09-19_adr-133-wiki-ingest-skill.md) | wiki_ingest Skill | Implemented, verified against a real model | 2026-09-19 |
| [ADR-132](../journal/2026-09/2026-09-19_adr-132-llm-wiki-layer-scaffolding.md) | LLM Wiki Layer: Raw/Wiki/Schema Convention & Config Knobs | Implemented | 2026-09-19 |
| [ADR-130](../journal/2026-09/2026-09-19_adr-130-streaming-chat-endpoint-structured-actions.md) | Streaming Persona Chat Endpoint (SSE) & Structured Action Events | Implemented (backend; frontend is ADR-131) | 2026-09-19 |
| [ADR-129](../journal/2026-09/2026-09-19_adr-129-vault-write-optimistic-concurrency-guard.md) | Vault-Write Optimistic-Concurrency Guard | Implemented | 2026-09-19 |
| [ADR-128](../journal/2026-09/2026-09-19_adr-128-wiring-capability-tiers-into-skill-model-selection.md) | Wiring Capability Tiers Into Skill-Driven Model Selection | Implemented (scoped down, see doc) | 2026-09-19 |
| [ADR-127](../journal/2026-09/2026-09-19_adr-127-capability-tier-model-routing-axis.md) | Capability-Tier Model Routing Axis | Implemented (dormant primitive) | 2026-09-19 |
| [ADR-126](../journal/2026-09/2026-09-19_adr-126-splitting-config-schema-into-section-modules.md) | Splitting config_schema.py's SETTINGS Into Section Modules | Implemented | 2026-09-19 |
| [ADR-125](../journal/2026-09/2026-09-18_adr-125-splitting-vault-and-engine-under-200-loc.md) | Splitting vault.py and engine.py Into Focused, Under-200-LOC Modules | Implemented | 2026-09-18 |
| [ADR-124](../journal/2026-09/2026-09-18_adr-124-index-backed-grounding-checks-over-catch-phrases.md) | Index-Backed Grounding Checks, With Catch-Phrase Lists Reduced to a Coarse Gate | Accepted | 2026-09-18 |
| [ADR-123](../journal/2026-09/2026-09-18_adr-123-automatic-folder-kind-signals-from-digest-fields.md) | Automatic Folder-Kind Signals, Derived From Existing Digest Fields | Fully implemented (123.1-123.5 shipped) | 2026-09-18 |
| [ADR-122](../journal/2026-09/2026-09-14_adr-122-local-cloud-model-complexity-routing.md) | Local/Cloud Model Routing by Message Complexity | Mechanism shipped, dormant (no persona configured; no onboarding path) | 2026-09-14 |
| [ADR-121](../journal/2026-09/2026-09-14_adr-121-ruff-as-standing-dev-dependency.md) | ruff as a Standing Dev Dependency, With a Narrow, Audited Rule Set | Accepted | 2026-09-14 |
| [ADR-120](../journal/2026-09/2026-09-14_adr-120-click-drag-cumulative-displacement.md) | Click-vs-Drag Detection: Cumulative Displacement Instead of Per-Event Delta (amends ADR-096, ADR-114) | Accepted | 2026-09-14 |
| [ADR-119](../journal/2026-09/2026-09-14_adr-119-3d-nebula-one-way-random-axis-spin.md) | 3D Nebula Camera Spin: One-Way Twist on a Random Axis (amends ADR-118) | Accepted | 2026-09-14 |
| [ADR-118](../journal/2026-09/2026-09-14_adr-118-3d-nebula-click-then-fly-sequencing.md) | 3D Nebula Click-Then-Fly Sequencing (amends ADR-117) | Accepted (amended by ADR-119) | 2026-09-14 |
| [ADR-117](../journal/2026-09/2026-09-14_adr-117-3d-nebula-click-stutter-root-causes.md) | 3D Nebula Click Stutter: Three Independent Root Causes (amends ADR-112, ADR-116) | Accepted (amended by ADR-118) | 2026-09-14 |
| [ADR-116](../journal/2026-09/2026-09-14_adr-116-3d-highlight-easing-never-reached-the-screen.md) | 3D Highlight/Dim Easing Never Reached the Screen (amends ADR-112, ADR-115) | Accepted (amended by ADR-117) | 2026-09-14 |
| [ADR-115](../journal/2026-09/2026-09-14_adr-115-remove-duplicate-3d-background-click-dispatch.md) | Remove the Duplicate 3D Background-Click Dispatch (amends ADR-112, ADR-114) | Accepted (amended by ADR-116) | 2026-09-14 |
| [ADR-114](../journal/2026-09/2026-09-14_adr-114-nebula-force-graph-mount-crash-and-click-threshold-patches.md) | Nebula Force-Graph Mount-Crash Fix & Click-vs-Drag Threshold Recalibration (amends ADR-096, ADR-112) | Accepted (amended by ADR-115, ADR-120) | 2026-09-14 |
| [ADR-113](../journal/2026-09/2026-09-14_adr-113-agent-notes-use-real-vault-templates.md) | Notes Use the Vault's Real Templates, Agent and Dashboard Alike (amends ADR-039, ADR-076, ADR-083) | Accepted | 2026-09-14 |
| [ADR-112](../journal/2026-09/2026-09-14_adr-112-enable-3d-nebula-renderer-in-app-shell.md) | Enable the 3D Nebula Renderer in the App Shell (amends ADR-088) | Accepted (amended by ADR-114, ADR-115, ADR-116, ADR-117) | 2026-09-14 |
| [ADR-111](../journal/2026-09/2026-09-13_adr-111-drag-drop-target-for-folder-in-view.md) | Drop Target for the Folder Currently in View (amends ADR-110) | Accepted | 2026-09-13 |
| [ADR-110](../journal/2026-09/2026-09-13_adr-110-drag-and-drop-vault-note-moves.md) | Drag-and-Drop Note Moves: Vault Tree and Main Menu | Accepted | 2026-09-13 |
| [ADR-109](../journal/2026-09/2026-09-13_adr-109-pinned-notes-scoped-to-root-folder.md) | Pinned Notes Scoped to Root Folder, Not Vault-Wide | Accepted | 2026-09-13 |
| [ADR-108](../journal/2026-09/2026-09-13_adr-108-pinned-notes-vault-wide-recent-management.md) | Pinned Notes Promoted to a Vault-Wide Group; Recent Management + Toggle | Accepted | 2026-09-13 |
| [ADR-107](../journal/2026-09/2026-09-13_adr-107-recent-notes-group.md) | Recent Notes: A Vault-Wide Group Under Pinned | Accepted | 2026-09-13 |
| [ADR-106](../journal/2026-09/2026-09-13_adr-106-pinned-notes-per-folder-reorder.md) | Pinned Notes: Per-Folder Reorder in the Vault Tree | Accepted | 2026-09-13 |
| [ADR-105](../journal/2026-09/2026-09-13_adr-105-vault-search-field.md) | Vault Search Field: Instant Client Filter, Backend Content Tier, Folder-Scoped Results | Accepted | 2026-09-13 |
| [ADR-104](../journal/2026-09/2026-09-13_adr-104-directional-panel-slide-navigation.md) | Directional Slide for Content/Editor Panel Navigation | Accepted | 2026-09-13 |
| [ADR-103](../journal/2026-09/2026-09-13_adr-103-vault-tree-exit-animation.md) | Vault-Tree Row Exit Animation on Delete | Accepted | 2026-09-13 |
| [ADR-102](../journal/2026-09/2026-09-13_adr-102-thumb-motion-tier.md) | `thumb` Motion Tier: Editor/Vault Entrances Match the Scrollbar (amends ADR-101) | Accepted | 2026-09-13 |
| [ADR-101](../journal/2026-09/2026-09-13_adr-101-motion-tier-tokens.md) | Motion Tier Tokens (`snappy` / `mode`) | Accepted (amended by ADR-102) | 2026-09-13 |
| [ADR-100](../journal/2026-09/2026-09-13_adr-100-animated-hand-drawn-scrollbar-thumb.md) | Animated Hand-Drawn Scrollbar Thumb | Accepted | 2026-09-13 |
| [ADR-099](../journal/2026-09/2026-09-12_adr-099-vault-folder-delete-to-bin.md) | Vault Folder Delete: Empty Unlinks, Non-Empty Goes to the Bin | Accepted | 2026-09-12 |
| [ADR-098](../journal/2026-09/2026-09-12_adr-098-vault-tree-shows-empty-folders.md) | Vault Tree Shows Empty Folders on Disk (amends ADR-095) | Accepted | 2026-09-12 |
| [ADR-097](../journal/2026-09/2026-09-12_adr-097-content-panel-selection-drives-ambient-nebula-focus.md) | Content-Panel Note Selection Drives the Ambient Nebula Focus (amends ADR-088) | Accepted | 2026-09-12 |
| [ADR-096](../journal/2026-09/2026-09-12_adr-096-patch-force-graph-pointer-drag-detection.md) | Patch force-graph / three-render-objects Pointer-Drag Detection & Hover Freshness | Accepted (amended by ADR-114, ADR-120) | 2026-09-12 |
| [ADR-095](../journal/2026-09/2026-09-12_adr-095-content-panel-toolbar-folder-creation-and-visit-history.md) | Content Panel Toolbar: Folder Creation & Visit History | Accepted (amended by ADR-098) | 2026-09-12 |
| [ADR-094](../journal/2026-09/2026-09-11_adr-094-settings-panel-density-cleanup.md) | Settings Panel Density Cleanup | Accepted | 2026-09-11 |
| [ADR-093](../journal/2026-09/2026-09-11_adr-093-stage-action-group-swap-and-explore-slide-out.md) | Stage Action Group Order Swap & Explore Slide-Out | Accepted | 2026-09-11 |
| [ADR-092](../journal/2026-09/2026-09-11_adr-092-vault-editor-ux-batch-pin-notes-hide-extensions-footer-slot.md) | Vault & Editor UX Batch: Pin/Unpin Notes, Hidden File Extensions, ContentPanel Footer Slot | Accepted | 2026-09-11 |
| [ADR-091](../journal/2026-09/2026-09-11_adr-091-nebula-dock-inline-in-settings-and-dock-toggle.md) | Nebula Dock Knobs Surfaced Inline in Settings + Dock Visibility Toggle (amends ADR-088/ADR-090) | Accepted | 2026-09-11 |
| [ADR-090](../journal/2026-09/2026-09-11_adr-090-explore-auto-collapses-stage-panels.md) | Explore Auto-Collapses the Stage Panels (amends ADR-088) | Accepted | 2026-09-11 |
| [ADR-089](../journal/2026-09/2026-09-11_adr-089-drop-frosted-panel-blur.md) | Drop the Frosted-Panel Blur Knob (amends ADR-088) | Accepted | 2026-09-11 |
| [ADR-088](../journal/2026-09/2026-09-11_adr-088-ambient-knowledge-nebula-in-app-shell.md) | Ambient Knowledge Nebula in the App Shell (Phase A) | Accepted (amended by ADR-089, ADR-090, ADR-091, ADR-097, ADR-112) | 2026-09-11 |
| [ADR-087](../journal/2026-09/2026-09-11_adr-087-notification-and-confirmation-preferences.md) | Notification & Confirmation Preferences | Accepted | 2026-09-11 |
| [ADR-086](../journal/2026-09/2026-09-11_adr-086-vault-tree-context-menu-and-trash-in-main-menu.md) | Vault Tree Context Menu & Trash in the Main Menu | Accepted | 2026-09-11 |
| [ADR-085](../journal/2026-09/2026-09-10_adr-085-note-recovery-trash-view.md) | Note Recovery: the Vault Trash View | Accepted | 2026-09-10 |
| [ADR-084](../journal/2026-09/2026-09-10_adr-084-rename-delete-notes-from-editor.md) | Rename & Delete Notes from the Editor | Accepted | 2026-09-10 |
| [ADR-083](../journal/2026-09/2026-09-10_adr-083-editor-note-creation-and-frontmatter-fidelity.md) | Editor Note Creation & Frontmatter Round-Trip Fidelity | Accepted | 2026-09-10 |
| [ADR-082](../journal/2026-09/2026-09-10_adr-082-slack-heartbeat-status.md) | Slack Daemon Heartbeat & Dashboard Status Pill | Accepted | 2026-09-10 |
| [ADR-081](../journal/2026-09/2026-09-10_adr-081-vault-note-write-back.md) | Vault Note Write-Back from the Dashboard Editor | Accepted | 2026-09-10 |
| [ADR-080](../journal/2026-09/2026-09-10_adr-080-stylo-vault-markdown-editor.md) | Stylo as the Vault Markdown Editor | Accepted | 2026-09-10 |
| [ADR-079](../journal/2026-09/2026-09-09_adr-079-prebuilt-dashboard-bundle.md) | Prebuilt Dashboard Bundle Shipped in the Package | Accepted | 2026-09-09 |
| [ADR-078](../journal/2026-09/2026-09-09_adr-078-vault-manifest-materialized-map.md) | Materialized Vault Manifest (Structural Map) for the Agent & Dashboard Graph | Accepted | 2026-09-09 |
| [ADR-077](../journal/2026-09/2026-09-08_adr-077-declarative-configuration-schema.md) | Declarative Configuration Schema as Single Source of Truth | Accepted | 2026-09-08 |
| [ADR-076](../journal/2026-09/2026-09-07_adr-076-skill-playbook-single-source-and-compression.md) | Skill Playbook Single-Source & Compression | Accepted | 2026-09-07 |
| [ADR-075](../journal/2026-09/2026-09-05_adr-075-persona-soul-content-in-create-persona.md) | Persona Soul Content in CREATE_PERSONA | Accepted | 2026-09-05 |
| [ADR-074](../journal/2026-09/2026-09-05_adr-074-default-persona-vault-scope-and-onboarding-genesis-nudge.md) | Default Persona Vault Scope & Onboarding Persona-Genesis Nudge | Accepted | 2026-09-05 |
| [ADR-073](../journal/2026-09/2026-09-04_adr-073-worker-native-shell-allowlisting.md) | Worker Native-Shell Command Allowlisting & Symlink-Safe Path Checks | Accepted | 2026-09-04 |
| [ADR-072](../journal/2026-09/2026-09-04_adr-072-engine-concurrency-bounded-background-hygiene.md) | Engine Concurrency Model & Bounded Background Hygiene Pool | Accepted | 2026-09-04 |
| [ADR-071](../journal/2026-09/2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md) | Primary-Agent Action Dispatch — Bracket-Tag DSL vs Native Function Calling | Accepted (revisited 2026-09-14, unchanged) | 2026-09-04 |
| [ADR-070](../journal/2026-09/2026-09-04_adr-070-hot-path-retrieval-budget-trigger-discipline.md) | Hot-Path Vault Retrieval Budget, Trigger Discipline & Indexed Search Tier | Accepted | 2026-09-04 |
| [ADR-065](../journal/2026-08/2026-08-30_adr-065-mcp-client-threading-logging-standard.md) | MCP Client Threading & Logging Standard | Accepted | 2026-08-30 |
| [ADR-064](../journal/2026-08/2026-08-30_adr-064-dashboard-api-auth-plan.md) | Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan | Accepted | 2026-08-30 |
| [ADR-069](../journal/2026-08/2026-08-29_adr-069-live-stream-markdown-parsing.md) | Live Stream Markdown Parsing for Real-Time Badges & Sub-Agent Reports | Accepted | 2026-08-29 |
| [ADR-068](../journal/2026-08/2026-08-29_adr-068-subagent-worker-report-panel-styling.md) | Sub-Agent Worker Report Panel Styling & Redundant Synthesis Gating | Accepted | 2026-08-29 |
| [ADR-067](../journal/2026-08/2026-08-29_adr-067-ghost-session-pruning.md) | Intelligent Ghost Session Pruning & Substantive Conversation Gating | Accepted | 2026-08-29 |
| [ADR-066](../journal/2026-08/2026-08-29_adr-066-terminal-markdown-presentation-standard.md) | Terminal Markdown Presentation Standard (vault_recall) & Beautified Sub-Agent Orchestration | Accepted | 2026-08-29 |
| [ADR-063](../journal/2026-08/2026-08-29_adr-063-system-wide-llm-timeout-hardening.md) | System-Wide LLM Timeout Hardening | Accepted | 2026-08-29 |
| [ADR-062](../journal/2026-08/2026-08-29_adr-062-render-mode-raw-panel-suppression.md) | render_mode: raw Panel Suppression in the Action Executor | Accepted | 2026-08-29 |
| [ADR-061](../journal/2026-08/2026-08-29_adr-061-subagent-read-note-explicit-intent-gating.md) | Sub-Agent [READ_NOTE] Explicit-Intent Gating | Accepted | 2026-08-29 |
| [ADR-060](../journal/2026-08/2026-08-29_adr-060-terminal-render-mode-knob.md) | Three-Way Terminal Render Mode Knob (performance.render_mode) | Accepted | 2026-08-29 |
| [ADR-059](../journal/2026-08/2026-08-29_adr-059-clean-range-prompts-signal-interruption.md) | Repository-Wide Clean Range Prompts & Graceful Asynchronous Signal Interruption (SIGINT) | Accepted | 2026-08-29 |
| [ADR-058](../journal/2026-08/2026-08-29_adr-058-multisectionpanel-in-terminal-note-viewer.md) | MultiSectionPanel In-Terminal Note Viewer with Inline T-Junction Box Dividers | Accepted | 2026-08-29 |
| [ADR-057](../journal/2026-08/2026-08-29_adr-057-structured-vault-retrieval-context-excerpts.md) | Orderly Structured Vault Retrieval & Single-Line Context Excerpts | Accepted | 2026-08-29 |
| [ADR-056](../journal/2026-08/2026-08-29_adr-056-retire-automated-vault-session-dumping.md) | Retirement of Automated Vault Session Dumping in Favor of Native History Sovereignty | Accepted | 2026-08-29 |
| [ADR-055](../journal/2026-08/2026-08-29_adr-055-milestone-based-async-titling.md) | Milestone-Based Asynchronous Titling & Generic Prompt Filtering | Accepted | 2026-08-29 |
| [ADR-054](../journal/2026-08/2026-08-29_adr-054-jsonl-conversation-persistence-context-hydration.md) | Zero-Bloat Conversation Persistence (.jsonl), Decoupled UI History & Sliding Context Window Hydration | Accepted | 2026-08-29 |
| [ADR-053](../journal/2026-08/2026-08-29_adr-053-cross-platform-native-desktop-launchers.md) | Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers | Accepted | 2026-08-29 |
| [ADR-052](../journal/2026-08/2026-08-29_adr-052-in-memory-metadata-caching-scalability.md) | In-Memory Metadata Caching & Sub-5ms Scalability Standard | Accepted | 2026-08-29 |
| [ADR-051](../journal/2026-08/2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md) | Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine | Accepted | 2026-08-29 |
| [ADR-050](../journal/2026-08/2026-08-29_adr-050-interactive-skill-command-suite.md) | Interactive Skill Command Suite (/skill & /skills) with Tab Auto-Completion | Accepted | 2026-08-29 |
| [ADR-049](../journal/2026-08/2026-08-29_adr-049-code-fence-action-tag-parsing.md) | Robust Code-Fence Action Tag Parsing & Dynamic Cache Resolution | Accepted | 2026-08-29 |
| [ADR-048](../journal/2026-08/2026-08-29_adr-048-dynamic-3-tier-model-hierarchy.md) | Dynamic 3-Tier Model Hierarchy & Runtime Fallback Architecture | Accepted | 2026-08-29 |
| [ADR-047](../journal/2026-08/2026-08-29_adr-047-cli-design-system-typography.md) | Standardized Sympose CLI Design System (SYMPOSE_THEME) & Typography Standard | Accepted | 2026-08-29 |
| [ADR-046](../journal/2026-08/2026-08-29_adr-046-samantha-only-clean-slate-persona-genesis.md) | Samantha-Only Clean Slate & Dynamic Autonomic Persona Genesis | Accepted | 2026-08-29 |
| [ADR-045](../journal/2026-08/2026-08-29_adr-045-standalone-packaging-sovereign-workspace.md) | Modern Standalone Python Packaging (pyproject.toml) & Sovereign User Workspace | Accepted | 2026-08-29 |
| [ADR-044](../journal/2026-08/2026-08-27_adr-044-in-memory-inverted-index-backlink-engine.md) | In-Memory Inverted Index & Deterministic Backlink Lookup Engine | Accepted | 2026-08-27 |
| [ADR-043](../journal/2026-08/2026-08-27_adr-043-three-layer-separation-soul-skill-physics.md) | Three-Layer Architectural Separation (Soul vs Skill vs System Physics) | Accepted | 2026-08-27 |
| [ADR-042](../journal/2026-08/2026-08-27_adr-042-autonomous-live-internet-search.md) | Autonomous Live Internet Search (web_search) & Zero-Key ddgs Standard | Accepted | 2026-08-27 |
| [ADR-041](../journal/2026-08/2026-08-27_adr-041-slack-thread-active-context-isolation.md) | Multi-Turn Slack Thread Active Context Isolation & Single-Source Action Execution | Accepted | 2026-08-27 |
| [ADR-040](../journal/2026-08/2026-08-27_adr-040-native-obsidian-templates-frontmatter-sync.md) | Native Obsidian Templates/ Engine & Dynamic Frontmatter Tag Syncing | Accepted | 2026-08-27 |
| [ADR-039](../journal/2026-08/2026-08-27_adr-039-vault-write-skill-wikilink-taxonomy.md) | Modular vault_write Skill, Obsidian Wikilink Taxonomy & Nested Hierarchies | Accepted | 2026-08-27 |
| [ADR-038](../journal/2026-08/2026-08-26_adr-038-defensive-engineering-hardening-standards.md) | Post-Remediation Hardening & Defensive Engineering Standards | Accepted | 2026-08-26 |
| [ADR-037](../journal/2026-08/2026-08-26_adr-037-pure-declarative-markdown-prompting.md) | Pure Declarative Markdown-Driven Prompting & Zero-Code Injections | Accepted | 2026-08-26 |
| [ADR-036](../journal/2026-08/2026-08-26_adr-036-multi-agent-collaboration-circuit-breaker.md) | Multi-Agent Collaboration Protocol, Discussion Moderation & Safety Circuit Breaker | Accepted | 2026-08-26 |
| [ADR-035](../journal/2026-08/2026-08-26_adr-035-evidence-based-grounding-epistemic-humility.md) | Evidence-Based Grounding & Epistemic Humility Standard | Accepted | 2026-08-26 |
| [ADR-034](../journal/2026-08/2026-08-26_adr-034-autonomous-slack-reaction-autonomy.md) | Autonomous Slack Emotion & Reaction Autonomy | Accepted | 2026-08-26 |
| [ADR-033](../journal/2026-08/2026-08-26_adr-033-zero-key-native-web-search-ddgs.md) | Zero-Key Native Web Search & the ddgs Standard | Accepted | 2026-08-26 |
| [ADR-032](../journal/2026-08/2026-08-26_adr-032-first-class-mcp-directory-modular-hub.md) | First-Class mcp/ Directory Hierarchy & Modular Hub Refactor | Accepted | 2026-08-26 |
| [ADR-031](../journal/2026-08/2026-08-26_adr-031-slack-thread-deletion-command-ergonomics.md) | Slack Thread Deletion, Command Ergonomics & Memory Sovereignty | Accepted | 2026-08-26 |
| [ADR-030](../journal/2026-08/2026-08-26_adr-030-high-density-folder-digests-zero-delay.md) | High-Density Folder Digests & Universal Ban on Time-Delay Simulation | Accepted | 2026-08-26 |
| [ADR-029](../journal/2026-08/2026-08-25_adr-029-assume-interruption-write-through-state.md) | Assume Interruption Meta-Directive & Write-Through State Checkpointing | Accepted | 2026-08-25 |
| [ADR-028](../journal/2026-08/2026-08-25_adr-028-slack-socket-mode-thread-context-isolation.md) | Slack Socket Mode Integration & Thread Context Isolation | Accepted | 2026-08-25 |
| [ADR-027](../journal/2026-08/2026-08-25_adr-027-config-driven-spatial-compass.md) | Config-Driven Spatial Compass & Complete Vault Agnosticism | Accepted | 2026-08-25 |
| [ADR-026](../journal/2026-08/2026-08-25_adr-026-subagent-worker-spatial-environment-sandbox.md) | Sub-Agent Worker Spatial Environment & Inherited Sandbox Security | Accepted | 2026-08-25 |
| [ADR-025](../journal/2026-08/2026-08-25_adr-025-persistent-multi-turn-vault-context.md) | Persistent Multi-Turn Vault Context & Conversational Intent Stripping | Accepted | 2026-08-25 |
| [ADR-024](../journal/2026-08/2026-08-25_adr-024-ground-truth-sovereignty-axiom.md) | The Ground-Truth Sovereignty Axiom & Anti-Simulation Directives | Accepted | 2026-08-25 |
| [ADR-023](../journal/2026-08/2026-08-25_adr-023-centralized-vault-ignore-filters.md) | Centralized Vault Ignore Filters | Accepted | 2026-08-25 |
| [ADR-022](../journal/2026-08/2026-08-25_adr-022-local-first-hierarchical-retrieval.md) | Local-First Hierarchical Retrieval & Noise Pruning (vault_recall) | Accepted | 2026-08-25 |
| [ADR-021](../journal/2026-08/2026-08-25_adr-021-hierarchical-daily-notes-format-resolvers.md) | Hierarchical Daily Notes & Vault-Agnostic Format Resolvers | Accepted | 2026-08-25 |
| [ADR-020](../journal/2026-08/2026-08-25_adr-020-zero-maintenance-mandate.md) | The Zero-Maintenance Mandate & The Assistant Paradox | Accepted | 2026-08-25 |
| [ADR-019](../journal/2026-08/2026-08-25_adr-019-automated-memory-compaction-distillation.md) | Automated Memory Compaction & Distillation Protocol | Accepted | 2026-08-25 |
| [ADR-018](../journal/2026-08/2026-08-25_adr-018-multi-model-concierge-integration.md) | Multi-Model Concierge Integration (sympose_mastery) | Accepted | 2026-08-25 |
| [ADR-017](../journal/2026-08/2026-08-25_adr-017-openrouter-model-discovery-live-catalog.md) | Dynamic OpenRouter Model Discovery & Live Catalog Search | Accepted | 2026-08-25 |
| [ADR-016](../journal/2026-08/2026-08-25_adr-016-skill-driven-worker-model-auto-resolution.md) | Skill-Driven Sub-Agent Worker Model Auto-Resolution | Accepted | 2026-08-25 |
| [ADR-015](../journal/2026-08/2026-08-25_adr-015-multi-provider-routing-openrouter-key-injection.md) | Multi-Provider Routing & Explicit OpenRouter Key Injection | Accepted | 2026-08-25 |
| [ADR-014](../journal/2026-08/2026-08-24_adr-014-deterministic-native-tools-in-turn-synthesis.md) | Deterministic Native Tools & In-Turn Proactive Synthesis | Accepted | 2026-08-24 |
| [ADR-013](../journal/2026-08/2026-08-24_adr-013-mcp-ephemeral-subagent-worker-sandbox.md) | Model Context Protocol & Ephemeral Sub-Agent Worker Sandbox | Accepted | 2026-08-24 |
| [ADR-012](../journal/2026-08/2026-08-24_adr-012-modular-procedural-skills-system.md) | Modular Procedural Skills System (SKILL.md) | Accepted | 2026-08-24 |
| [ADR-011](../journal/2026-08/2026-08-24_adr-011-multi-folder-vault-whitelisting.md) | Multi-Folder Vault Whitelisting & Full-Vault Access Architecture | Accepted | 2026-08-24 |
| [ADR-010](../journal/2026-08/2026-08-24_adr-010-selective-memory-sharing-universal-user-profile.md) | Selective Memory Sharing & Universal User Profile Architecture | Accepted | 2026-08-24 |
| [ADR-009](../journal/2026-08/2026-08-24_adr-009-autonomous-agent-vault-access-action-protocol.md) | Autonomous Agent Vault Read/Write Access & Action Protocol | Accepted | 2026-08-24 |
| [ADR-008](../journal/2026-08/2026-08-24_adr-008-heuristic-gated-shadow-memory-extractor.md) | Heuristic-Gated Shadow Memory Extractor | Accepted | 2026-08-24 |
| [ADR-007](../journal/2026-08/2026-08-24_adr-007-memory-grounding-anti-hallucination.md) | Strict Memory Grounding, Anti-Hallucination & Honest Ignorance | Accepted | 2026-08-24 |
| [ADR-006](../journal/2026-08/2026-08-24_adr-006-autonomous-soul-memory-bootstrapping.md) | Autonomous Soul & Memory Bootstrapping | Accepted | 2026-08-24 |
| [ADR-005](../journal/2026-08/2026-08-24_adr-005-config-yaml-session-summarization-memory.md) | Centralized config.yaml, Session Summarization & Memory Consolidation | Accepted | 2026-08-24 |
| [ADR-004](../journal/2026-08/2026-08-24_adr-004-modular-package-architecture.md) | Industry-Standard Modular Package Architecture | Accepted | 2026-08-24 |
| [ADR-003](../journal/2026-08/2026-08-24_adr-003-pluggable-multi-tier-vault-search.md) | Pluggable Multi-Tier Vault Search Architecture | Accepted | 2026-08-24 |
| [ADR-002](../journal/2026-08/2026-08-24_adr-002-master-vault-domain-sandboxing.md) | Master Vault Domain Sandboxing & Access Control | Accepted | 2026-08-24 |
| [ADR-001](../journal/2026-08/2026-08-24_adr-001-core-runtime-execution-resilience.md) | Core Runtime & Execution Resilience | Accepted | 2026-08-24 |

> **ADR-060 – ADR-063 numbering.** Two sets of decisions drafted on 2026-08-29
> both claimed 060–063. The *Terminal Render Mode Knob* set keeps 060–063; the
> *Structured Vault Search* session's four extra decisions were renumbered to
> **ADR-066 – ADR-069** during the 2026-09 documentation-standard conformance
> pass. No decision content changed.
