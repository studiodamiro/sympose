---
title: "Sympose Web Dashboard & Standalone Vault Explorer Specification"
created: 2026-08-27
type: wiki-architecture
parent: architecture/overview
tags:
  - sympose/dashboard
  - vault-explorer
  - knowledge-graph
  - multi-agent-ui
  - architecture-spec
---

# 🖥️ Sympose Web Dashboard & Standalone Vault Explorer Specification

> **Design Philosophy: Engine First, Face Second & Zero-Dependency Sovereignty**  
> The Sympose Dashboard provides an integrated, local-first web interface for multi-agent conversations, real-time configuration, interactive knowledge graphs, and a **standalone Vault Explorer** that eliminates the requirement for users to install or run Obsidian.

---

## 1. Architectural Vision & Pillars

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       SYMPOSE WEB DASHBOARD                                     │
├──────────────────────────┬──────────────────────────────────────────┬───────────────────────────┤
│ 📁 VAULT EXPLORER        │ 💬 MULTI-AGENT CHAT & TIMELINE           │ 🕸️ GRAPH & BACKLINKS      │
│                          │                                          │                           │
│ ▾ Projects/              │ [@samantha]: Analyzing system spec...    │ [ Interactive 2D Graph ]  │
│   ▾ Sympose/             │                                          │ ◉ Architecture.md         │
│     Architecture.md      │ [@grace]: Verified Inverted Index SLA.   │ ├── ➔ [[OAuth]]           │
│     Roadmap.md           │ > 📝 Action: Saved to Vault (<3ms)       │ └── ➔ [[FastAPI]]         │
│ ▾ Daily/                 │                                          │                           │
│   ▸ 2026-08-27.md        │ ──────────────────────────────────────── │ ◀ BACKLINKS (3)           │
│ ▾ Thoughts/              │ [ Ask @grace, @samantha, @anais...     ] │ • Daily/2026-08-25.md     │
│ ▾ People/                │                                          │ • Thoughts/Reflections.md │
└──────────────────────────┴──────────────────────────────────────────┴───────────────────────────┘
```

### Core Tenets
1. **Zero External Software Lock-In:** Users gain a rich knowledge garden explorer, daily note timeline, and graph visualizer without installing Obsidian or running background plugins.
2. **Open Flat-File Storage:** All notes, daily logs, and canvases remain standard Markdown files with YAML frontmatter and `[[Wikilinks]]` stored on local disk.
3. **Sub-Second Reactivity (<0.8s SLA):** Fast local Python engine primitives serve file trees, graph nodes, and backlink queries in $<5\text{ms}$.
4. **Unified Multi-Agent Ergonomics:** Chatting with specialist agents, triggering autonomic file actions, and browsing memory archives happen in one cohesive workspace.

---

## 2. Core Functional Modules

### 🌿 Module A: Standalone Vault Explorer & Markdown Editor
A full-featured file manager and editor operating directly over the user's sandboxed markdown archives:
* **Directory Tree Navigator:** Hierarchical folder tree respecting agent domain sandboxes and ignoring binary/system folders (`.obsidian`, `.git`, `Attachments`, `.trash`).
* **Rich Markdown Reader & Live Editor:**
  * Clean typographic rendering with Github-flavored markdown, code blocks, and math formulas.
  * Clickable `[[Wikilink]]` routing (clicking `[[OAuth]]` navigates directly to `OAuth.md` or filters backlinks).
  * Dynamic YAML frontmatter inspector and tag editor.
* **Backlink & Mention Inspector:** Dedicated side panel displaying incoming links, exact line numbers, and verbatim surrounding context lines via our In-Memory Inverted Index ([ADR-044](file:///Users/damiro/Development/sympose/docs/journal/2026-08/2026-08-27_backlink_lookup_engine_and_inverted_index.md)).
* **Daily Reflections Calendar:** Interactive calendar view mapping `Daily/YYYY/mm-Month/YYYY-MM-DD.md` entries to dates for chronological reminiscence.
* **Tag Taxonomy Cloud:** Filter notes and graph nodes by extracted tags (e.g., `#jour`, `#architecture`, `#music`, `#growth`).

---

### 🕸️ Module B: Interactive Knowledge Graph Visualizer
Visualizes the organic idea web across the user's vault:
* **Force-Directed Node-Link Graph:** Visualizes notes as nodes and `[[Wikilinks]]` as directed edges.
* **Domain Color-Coding:** Color-codes nodes by folder/persona domain (e.g. Blue = `Projects/`, Purple = `Thoughts/`, Green = `Daily/`, Orange = `People/`).
* **Filtering Controls:** Filter graph density by folder whitelist, tag clusters, orphaned notes (notes with zero links), or degree of separation from the active note.
* **Instant Jump:** Clicking a graph node opens the document in the Vault Explorer pane.

---

### 💬 Module C: Multi-Agent Conversational Hub
A high-performance streaming chat interface designed for multi-agent collaboration:
* **Sub-Second Streaming Timeline:** Real-time token streaming via Server-Sent Events (SSE) / WebSocket.
* **Persona Drawer & Selector:** Switch between **Samantha** (Orchestrator), **Grace** (Systems Engineer), and **Anaïs** (Diarist), or trigger `@mentions` in multi-agent discussions.
* **Visual Action Event Cards:** Instead of raw bracketed tags, the UI renders interactive action badges for:
  * `[WRITE_NOTE]` / `[APPEND_NOTE]` $\to$ File saved badge with a direct link to open the file in the Vault Explorer.
  * `[DAILY_NOTE]` $\to$ Reflection badge with frontmatter tag sync indicator.
  * `[SEARCH]` $\to$ Live web search badge displaying query and retrieved source citations.
  * `[SPAWN_WORKER]` $\to$ Sub-agent task progress drawer showing tool execution logs.
  * `[REACT]` $\to$ Expressive animated emoji reactions on chat bubbles.

---

### ⚙️ Module D: Runtime Configuration & Persona Studio
A control panel for system tuning and agent lifecycle management:
* **Live Configuration Knobs:** Visual controls for `config.yaml` parameters:
  * `performance.request_timeout`, `performance.max_context_turns`, `performance.max_worker_tool_turns`.
  * `memory.compaction_threshold`, `memory.auto_compact`.
  * `vault.search_mode`, `vault.daily_notes_format`.
* **Persona Studio:**
  * Visual 7-point agent creator/editor (`profiles/*.yaml`).
  * Live Soul Directive editor (`profiles/*_soul.md`).
  * Working Memory inspector with 1-click `/compact` execution (`profiles/*_memory.md`).
* **Dynamic Model Catalog Explorer:**
  * Live search across OpenRouter's dynamic model catalog ([ADR-019](file:///Users/damiro/Development/sympose/docs/journal/2026-08/2026-08-25_openrouter_and_model_catalog.md)).
  * Context length, pricing, and latency metadata.
  * Per-agent live model override selector.

---

## 3. Backend Primitives & Data Contracts

The dashboard communicates with a lightweight Python backend service (FastAPI / Starlette) exposing standard REST and WebSocket endpoints:

### 1. Vault Explorer & Graph API (`/api/vault/*`)
* **`GET /api/vault/tree`**: Returns nested JSON directory tree.
* **`GET /api/vault/note?path=<rel_path>`**: Returns raw markdown, parsed AST, frontmatter metadata, and forward links.
* **`POST /api/vault/note`**: Creates or updates a note safely within sandboxed directories.
* **`GET /api/vault/backlinks?target=<note_name>`**: Returns structured backlink records via `VaultManager.get_backlinks()`.
* **`GET /api/vault/graph`**: Returns `{ nodes: [{ id, label, folder, tags }], edges: [{ source, target }] }` for D3 / Cytoscape graph rendering.
* **`GET /api/vault/calendar`**: Returns chronological index mapping dates to daily note paths.

### 2. Conversational & Event Stream API (`/api/chat/*`)
* **`POST /api/chat/message`**: Dispatches user prompt to `PersonaEngine`.
* **`GET /api/chat/stream?session_id=<id>`**: SSE / WebSocket stream delivering text tokens and structured action events.
* **`POST /api/chat/reset`**: Resets conversational context window.

### 3. Settings & Persona API (`/api/config/*` & `/api/personas/*`)
* **`GET /api/config` / `PUT /api/config`**: Reads and updates runtime parameters in `config.yaml`.
* **`GET /api/personas`**: Lists all active agent profiles.
* **`POST /api/personas`**: Creates a new specialist persona.
* **`POST /api/personas/{handle}/compact`**: Triggers memory compaction on demand.

---

## 4. Phased Build Sequence

```text
Phase 1: Backend Data Primitives (Completed: Inverted Index & Backlink Engine - ADR-044)
   │
   ▼
Phase 2: Local HTTP/WebSocket API Gateway (<150 LOC FastAPI / Starlette runner)
   │
   ▼
Phase 3: Vault Explorer & Knowledge Graph UI (File Tree, Markdown Editor, D3 Graph)
   │
   ▼
Phase 4: Multi-Agent Chat Timeline & Action Event Bus (Streaming SSE, Action Badges)
   │
   ▼
Phase 5: Persona Studio & Live Config Control Panel
```

---

## 5. Architectural Decision Record Reference
* **[ADR-044: In-Memory Inverted Index & Deterministic Backlink Lookup Engine](file:///Users/damiro/Development/sympose/docs/journal/2026-08/2026-08-27_backlink_lookup_engine_and_inverted_index.md)**: Foundational graph and reverse-index primitives powering the Vault Explorer.
* **[ADR-011: Multi-Folder Vault Whitelisting & Sandboxing](file:///Users/damiro/Development/sympose/docs/journal/2026-08/2026-08-24_multi_folder_vault.md)**: Security boundary isolating persona directory access.
