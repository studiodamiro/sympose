---
title: "Sympose Web Dashboard, Standalone Vault Explorer & 2D/3D Knowledge Nebula Specification"
created: 2026-08-27
updated: 2026-08-29
type: wiki-architecture
parent: architecture/overview
tags:
  - sympose/dashboard
  - vault-explorer
  - knowledge-graph
  - 3d-nebula
  - shadcn-ui
  - theme-engine
  - multi-agent-ui
  - architecture-spec
---

# 🖥️ Sympose Web Dashboard, Vault Explorer & 2D/3D Knowledge Nebula Specification

> **Design Philosophy: Engine First, Face Second & Flat Sovereign Craft**  
> The Sympose Dashboard provides an integrated, local-first web interface for multi-agent conversations, real-time configuration, a **2D/3D Ambient Knowledge Nebula**, and a **standalone Vault Explorer** that eliminates the requirement for users to install or run Obsidian.

> **Designing the UI?** See the [Web Dashboard UI Design Reference](../reference/ui-design-reference.md) — a self-contained brief (visual language, theme presets, layout shell, per-screen artboard list, mock content) built from this spec and ADR-047 / ADR-051–053, meant to be fed directly into Claude Design.

---

## 1. Architectural Vision & Core Principles

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       SYMPOSE WEB DASHBOARD                                     │
│  [ 🎨 Preset: Obsidian Matte ▾]  [ 🏛️ Style: Nova ▾]  [ 📐 Radius: 0px ]  [ 💡 Dark ]  [ 2D | 3D ]│
├──────────────────────────┬──────────────────────────────────────────┬───────────────────────────┤
│ 📁 VAULT EXPLORER        │ 💬 MULTI-AGENT CHAT & TIMELINE           │ 🌌 AMBIENT KNOWLEDGE      │
│                          │                                          │    NEBULA (2D/3D)         │
│ ▾ Projects/              │ [@samantha]: Formulating auth plan...    │   • (Architecture)        │
│   ▾ Sympose/             │                                          │      /      \             │
│     Architecture.md      │ [@grace]: Inverted index verified (<2ms) │   (OAuth)   (FastAPI)     │
│     Roadmap.md           │ > 📝 Action: Note saved to Vault         │                           │
│ ▾ Daily/                 │                                          │ ◀ OBSIDIAN CONTROLS       │
│   ▸ 2026-08-29.md        │ ──────────────────────────────────────── │ 🔍 Search   [ Filters ▾ ] │
│ ▾ Thoughts/              │ [ Ask @grace, @samantha, @anais...     ] │ 🧲 Forces   [ Sliders ▾ ] │
└──────────────────────────┴──────────────────────────────────────────┴───────────────────────────┘
```

### Core Tenets
1. **Flat High-Craft Aesthetics (Anti-AI Cliché)**: Rejects gratuitous purple neon glows and heavy glassmorphism. Defaults to clean flat geometry, Swiss/editorial typography, crisp 1px borders, and high WCAG text contrast.
2. **Dual-Mode 2D Vector & 3D Spatial Canvas**: A persistent background visualizer that seamlessly switches between a 2D top-down planar graph and a 3D WebGL orbit space.
3. **Two Fluid Interaction States**:
   * **Explore Mode**: The 3D/2D visualizer is 100% sharp and interactive with full orbit, pan, zoom, and node-click navigation (`pointer-events: auto`).
   * **Focus & Chat Mode**: Workspace panels expand with matte/frosted backings while the background visualizer dims by ~75% with a gentle ambient drift (`pointer-events: none`), preventing click hijacking and visual distraction.
4. **Dynamic shadcn Theme & Style Customizer (Inspired by `ui.shadcn.com/create`)**:
   * Dropdowns for **shadcn Styles** (*Nova, Maia, Sera, New York*).
   * Dropdowns for **Icon Libraries** (*Lucide, Phosphor, Hugeicons*).
   * Corner radius control (`0rem` sharp flat to `0.75rem`).
   * Seamless Light & Dark mode adaptation.
   * Full custom color pickers for node bubbles, link strings, and folder domains.
5. **Sub-5ms Scalability Across 10,000+ Notes**: In-memory metadata caching in Python RAM and single-draw-call GPU instancing deliver instant load times and 60 FPS physics without CPU/GPU drain.
6. **Zero External Software Lock-In**: Open flat Markdown files with YAML frontmatter and `[[Wikilinks]]` remain the sovereign ground truth on local disk.

---

## 2. Core Functional Modules

### 🌌 Module A: 2D/3D Ambient Knowledge Nebula

A persistent spatial visualizer representing the organic idea web across the user's vault:
* **Dual Rendering Engine**:
  * **2D Mode**: Fast, top-down planar vector canvas (HTML5 Canvas/SVG) for clear mapping.
  * **3D Mode**: Interactive 3D WebGL space (Three.js / `3d-force-graph`) with smooth orbit controls and particle pulse animations along links.
* **1:1 Parity with Obsidian Graph Controls**:
  * **Filters Panel**:
    * File search input (`Search files...`).
    * `Tags` toggle (render tag nodes as vertices).
    * `Attachments` toggle.
    * `Existing files only` toggle (filter out ghost/unresolved wikilinks).
    * `Orphans` toggle (hide notes with zero links).
  * **Groups Panel**:
    * Color-coding rules by folder (`path:Projects`), tag (`tag:#architecture`), or persona.
  * **Display Panel**:
    * `Arrows` toggle (directional link indicators).
    * `Text fade threshold` slider (adjusts label visibility based on zoom/distance).
    * `Node size` multiplier slider.
    * `Link thickness` slider.
    * `Animate` / Pulse trigger.
  * **Forces (Physics) Panel**:
    * `Center force` slider (gravity pulling nodes toward origin).
    * `Repel force` slider (charge repulsion separating nodes).
    * `Link force` slider (spring tension between connected notes).
    * `Link distance` slider (resting edge length).

---

### 🎨 Module B: Dynamic Theme & Style Customizer

An integrated appearance drawer providing instantaneous UI re-theming:
* **Curated Presets**:
  * **Obsidian Matte (Dark)**: Deep graphite `#0A0F1D`, sharp `0rem` radius, Phosphor icons, subtle slate strings, cyan/mint/purple bubbles.
  * **Blueprint & Paper (Light)**: Warm architectural parchment `#F9F7F1`, Lucide icons, drafting cobalt accents, fine ink links.
  * **Nordic Spruce (Balanced)**: Dark spruce `#1A2421`, moss green `#7EC7A2`, birch accents.
  * **Swiss Grid (Minimal)**: High-contrast monochrome, Bauhaus primary accents, sharp borders.
  * **Custom Studio**: Live color pickers for background, text, borders, node fills, and link strings.
* **Component Styles**: Switch between `nova`, `maia`, `sera`, and `new-york` stylesheets.
* **Icon Packs**: Interchangeable rendering across `@phosphor-icons/react`, `lucide-react`, and `@hugeicons/react`.

---

### 🌿 Module C: Standalone Vault Explorer & Markdown Editor

* **Directory Tree Navigator**: Hierarchical folder tree respecting agent domain sandboxes and ignoring binary/system folders (`.obsidian`, `.git`, `Attachments`, `.trash`).
* **Rich Markdown Reader & Live Editor**:
  * Clean typography with GitHub-flavored markdown, syntax-highlighted code blocks, and math formulas.
  * Clickable `[[Wikilink]]` routing (clicking `[[OAuth]]` navigates directly to `OAuth.md` or centers the 3D nebula).
  * Dynamic YAML frontmatter inspector and tag editor.
* **Backlink & Mention Inspector**: Dedicated side panel displaying incoming links, exact line numbers, and verbatim surrounding context lines via our In-Memory Inverted Index ([ADR-044](../../../docs/journal/2026-08/2026-08-27_backlink_lookup_engine_and_inverted_index.md)).
* **Daily Reflections Calendar**: Interactive calendar view mapping `Daily/YYYY/mm-Month/YYYY-MM-DD.md` entries to dates for chronological reminiscence.

---

### 💬 Module D: Multi-Agent Conversational Hub

* **Sub-Second Streaming Timeline**: Real-time token streaming via Server-Sent Events (SSE).
* **Persona Drawer & Selector**: Switch between **Samantha** (Orchestrator), **Grace** (Systems Engineer), and **Anaïs** (Diarist), or trigger `@mentions`.
* **Visual Action Event Badges**:
  * `[WRITE_NOTE]` / `[APPEND_NOTE]` $\to$ File saved badge with a direct link to open in the editor.
  * `[DAILY_NOTE]` $\to$ Reflection badge with frontmatter tag sync indicator.
  * `[SEARCH]` $\to$ Live web search badge displaying query and retrieved citations.
  * `[SPAWN_WORKER]` $\to$ Sub-agent task progress drawer showing tool execution logs.
  * `[REACT]` $\to$ Expressive animated emoji reactions on chat bubbles.
* **Active Nebula Synergy**: Referencing a note in chat gently pulses the corresponding 3D node cluster in the ambient background.

---

## 3. Backend Primitives & Data Contracts

The dashboard communicates with Sympose's native FastAPI gateway on `http://localhost:8000`:

### 1. Vault Explorer & Graph API (`/api/vault/*`)
* **`GET /api/vault/graph`**:
  * Returns: `{ nodes: [{ id, label, folder, tags, val }], links: [{ source, target }] }`
  * Sub-5ms response time served directly from Python in-memory index.
* **`GET /api/vault/cloud`**:
  * Returns high-density note and tag taxonomy with reference counts for 2D bubble clouds.
* **`GET /api/vault/note?path=<rel_path>`**:
  * Returns raw Markdown, frontmatter metadata, and forward links.
* **`POST /api/vault/note`**:
  * Creates or updates a note safely within sandboxed directories.
* **`GET /api/vault/backlinks?note=<name>`**:
  * Queries the inverted index for all incoming references.

### 2. Conversational API (`/api/chat/*`)
* **`POST /api/chat/message`**: Dispatches user prompt to `PersonaEngine`.
* **`GET /api/chat/stream?session_id=<id>`**: SSE stream delivering text tokens and structured action events.

### 3. Settings & Theme API (`/api/config/*`)
* **`GET /api/config` / `PUT /api/config`**: Reads and updates runtime parameters in `config.yaml` (including visualizer and theme settings).

---

## 4. Hardware Resource Budget & Performance SLAs

```text
┌─────────────────────────────────┬─────────────────┬──────────────────┬──────────────────┐
│ Component                       │ RAM Footprint   │ CPU (Idle/Active)│ GPU / VRAM       │
├─────────────────────────────────┼─────────────────┼──────────────────┼──────────────────┤
│ 🐍 Python Backend (FastAPI)     │ ~25 MB – 45 MB  │ < 0.1% / ~2%     │ 0 MB (Headless)  │
│ 🌐 Browser UI (React + shadcn)  │ ~50 MB – 80 MB  │ < 0.2% / ~1%     │ ~10 MB           │
│ 🌌 3D WebGL Engine (Three.js)   │ ~20 MB – 40 MB  │ < 0.5% / ~5%*    │ ~25 MB VRAM      │
├─────────────────────────────────┼─────────────────┼──────────────────┼──────────────────┤
│ 🚀 TOTAL COMBINED FOOTPRINT     │ ~100 MB – 165 MB│ < 1.0% (Idle)    │ ~35 MB VRAM      │
└─────────────────────────────────┴─────────────────┴──────────────────┴──────────────────┘
```

* **GPU Instanced Mesh**: Renders up to 20,000 nodes in **1 single draw call**.
* **Physics Sleep**: Force simulation automatically halts (`simulation.stop()`) after equilibrium is reached (~3s), reducing idle CPU to **0%**.
* **Target System Requirements**: Runs at 60 FPS on any dual-core machine with 4GB RAM (Apple Silicon M-Series, Intel Core i3 8th Gen+, Raspberry Pi 5).

---

## 5. Technology Stack & Distribution Pipeline

* **Frontend**: `Vite` + `React 18` + `TypeScript` + `TailwindCSS` + `shadcn/ui` + `Three.js` / `3d-force-graph` in `/ui`.
* **Build Target**: Static assets compiled to `/ui/dist/`.
* **Runtime**: Zero Node.js runtime required for end users. Served natively by FastAPI via `sympose --web` or `sympose --dashboard`.

---

## 6. Cross-Platform Native Desktop Launchers & Frameless App Mode

Sympose eliminates terminal friction while strictly avoiding Electron bloat (<60 KB launcher overhead):

* **🍎 macOS**:
  * **Launcher**: `/Applications/Sympose.app` generated via `sympose --install-app`.
  * **Access**: 100% native **Spotlight (`Cmd + Space`)**, Launchpad, and Dock pinning.
  * **Engine**: Launches the browser in dedicated frameless App Mode (`--app="http://localhost:8000"`) or native Cocoa WebKit (`pywebview`).
* **🪟 Windows**:
  * **Launcher**: `Sympose.lnk` shortcut in **Start Menu** and on the **Desktop**.
  * **Access**: Windows Search (`Win + S`) and Taskbar pinning.
  * **Engine**: Built-in Microsoft Edge / WebView2 in frameless app mode.
* **🐧 Linux**:
  * **Launcher**: Standard `~/.local/share/applications/sympose.desktop`.
  * **Access**: GNOME Dash, KDE Kickoff, RoFi, and desktop panels.
  * **Engine**: WebKit2GTK / Qt or Chromium `--app`.

---

## 7. Known Gap: No Authentication Was Ever Designed for This Surface

ADR-051–053 (below) specify UI/UX and performance exclusively — no access-control question was raised anywhere in this spec, and `sympose/server.py` currently exposes every route (including `/api/config` and `/api/vault/note`) with zero authentication, bound to `0.0.0.0` by default. **[ADR-064](../../../docs/journal/2026-08/2026-08-30_dashboard_api_security_design_gap_and_auth_plan.md) documents this gap and proposes a fix** (shared-password guard + auto-generated self-signed HTTPS, both zero-manual-install); it is not yet implemented. Slack access is unaffected either way — it never routes through this server.

## 8. Architectural Decision Records
* **[Web Dashboard UI Design Reference](../reference/ui-design-reference.md)** — design brief distilled from this spec for Claude Design.
* **[ADR-051: Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine](../../../docs/journal/2026-08/2026-08-29_web_dashboard_ui_ux_and_3d_knowledge_nebula.md#adr-051-flat-architectural-web-dashboard-2d3d-knowledge-nebula--shadcn-theme-customizer-engine)**
* **[ADR-052: In-Memory Metadata Caching & Sub-5ms Scalability Standard for Multi-Thousand Note Vaults](../../../docs/journal/2026-08/2026-08-29_web_dashboard_ui_ux_and_3d_knowledge_nebula.md#adr-052-in-memory-metadata-caching--sub-5ms-scalability-standard-for-multi-thousand-note-vaults)**
* **[ADR-053: Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers](../../../docs/journal/2026-08/2026-08-29_web_dashboard_ui_ux_and_3d_knowledge_nebula.md#adr-053-cross-platform-native-desktop-launchers--zero-bloat-frameless-app-mode-wrappers)**
* **[ADR-064 (Proposed): Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan](../../../docs/journal/2026-08/2026-08-30_dashboard_api_security_design_gap_and_auth_plan.md)**
* **[ADR-044: In-Memory Inverted Index & Deterministic Backlink Lookup Engine](../../../docs/journal/2026-08/2026-08-27_backlink_lookup_engine_and_inverted_index.md)**
* **[ADR-011: Multi-Folder Vault Whitelisting & Sandboxing](../../../docs/journal/2026-08/2026-08-24_multi_folder_vault.md)**

