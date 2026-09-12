---
title: "Sympose Web Dashboard, Standalone Vault Explorer & 2D/3D Knowledge Nebula Specification"
created: 2026-08-27
updated: 2026-09-13
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
2. **Dual-Mode 2D Vector & 3D Spatial Canvas**: A persistent background visualizer that switches between a 2D top-down planar graph and a 3D WebGL orbit space. **As shipped in the app shell (ADR-088, "Phase A"), this is 2D-only** — the in-shell `2D | 3D` toggle exists but is disabled, pointing at a Phase B not yet built. Full 2D/3D parity, described below in Module A, lives today only on the standalone `/nebula` showcase route.
3. **Two Fluid Interaction States** (see Module A for the shipped ADR-088–091 specifics):
   * **Explore Mode**: The visualizer is 100% sharp and interactive with full orbit, pan, zoom, and node-click navigation (`pointer-events: auto`), and the workspace panels auto-collapse out of its way.
   * **Focus & Chat Mode**: The background visualizer dims via user-adjustable blur/tint scrim sliders (`pointer-events: none`) rather than a fixed amount, preventing click hijacking and visual distraction. Panels themselves are opacity-only, not frosted — the Main Menu and Chat panel are intentionally backgroundless so the nebula bleeds through.
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

A persistent spatial visualizer representing the organic idea web across the user's vault. It exists in two places that share the same `NebulaGraph` renderer but ship on different timelines:

* **The `/nebula` showcase route** — the full-featured surface described in the rest of this module: 2D/3D parity, the complete Obsidian-style Filters/Display/Forces control set.
* **The app-shell ambient background (ADR-088, "Phase A")** — a persistent background layer behind the main menu, content panel, editor, and chat, always mounted rather than a route you navigate to:
  * **2D only for now** — the shell's `2D | 3D` toggle is present but disabled; 3D in the shell is Phase B, not yet built.
  * **Two interaction states** (Core Tenet 3): **Explore** — the nebula is fully sharp and interactive, and entering it auto-collapses/stashes the open Main Menu, content, and editor panels (ADR-090) so nothing occludes it; a corner `NebulaModeToggle` is a faster way in than opening Settings. **Focus & Chat** — the nebula dims via two independent scrim sliders (blur, tint), the Main Menu and Chat panel are intentionally backgroundless so the nebula bleeds through them, and floating panels are opacity-only (ADR-089 dropped the earlier frosted-blur treatment for panels themselves).
  * **A floating control dock** surfaces the nebula's own knobs (mode, forces, appearance) without leaving the shell; every one of those knobs is also reachable from the Settings panel (ADR-091), and the dock itself can be hidden via a Settings toggle.
  * **Selection-driven focus (ADR-097)**: opening a note anywhere in the shell — a vault-tree click, following a `[[wikilink]]`, creating a new note — flies the ambient camera to and highlights that note's node cluster live, even while the background is dimmed in Focus mode. This supersedes the older "chat mention pulses the graph" behavior described in Module D, which is now one trigger among several rather than the only one.
* **Dual Rendering Engine** — one `NebulaGraph` feed, one imperative handle, a
  `mode` prop swaps the renderer (remembered in the `nebula-view-mode` cookie):
  * **2D Mode**: flat Obsidian-default canvas (`react-force-graph-2d`) — folder-
    coloured discs, hairline links, pan + scroll-zoom, labels that fade in on
    zoom (`globalScale` gate).
  * **3D Mode**: WebGL orbit space (Three.js / `react-force-graph-3d`) — orbit /
    auto-rotate, `three-spritetext` node labels culled by camera distance (the
    same "appears when you get close" behaviour as 2D).
* **Obsidian Graph Control Parity** (as built on the `/nebula` showcase route):
  * **Filters Panel**: `Search files…` · `Tags` toggle · `Attachments` toggle ·
    `Existing files only` toggle (drops ghost wikilinks) · `Orphans` toggle
    (dims zero-link notes; a search match still surfaces them).
  * **Display Panel**:
    * `Arrows` toggle · `Auto Rotate Camera` toggle *(3D only)* · `Node labels`
      toggle (both modes).
    * `Background separation` slider — signed `−75 … +75%` lightness shift of
      node colour vs the background (toward black in light mode, white in dark;
      negative blends *into* the background).
    * `Color vividness` slider — signed `−100 … +100%` HSL-saturation scale
      (greyscale → palette → fully saturated).
    * `Node size` multiplier · `Link thickness` · `Note Spawn Delay` (birth
      animation) · `Zoom In Closeness` (node-click framing distance).
    * `Center & Fit` and `Animate` (staggered node birth) triggers.
  * **Forces (Physics) Panel**: `Center force` · `Repel force` · `Link force` ·
    `Link distance` — identical d3-force math in both renderers.
* **Not yet built**: per-query colour **Groups** and a raw label
  zoom-threshold slider were scaffolded then removed as non-functional; label
  visibility is currently automatic (zoom / camera-distance gated) with a single
  on/off toggle.

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

* **Directory Tree Navigator**: Hierarchical folder tree respecting agent domain sandboxes and ignoring binary/system folders (`.obsidian`, `.git`, `Attachments`, `.trash`). Back/forward through the main-menu's section history (ADR-095), same semantics as a browser tab.
* **Row actions (ADR-086)**: both a `⋯` button (hover/focus) and a real pointer-anchored right-click / long-press context menu — not a fixed-anchor dropdown — attach to every row, sharing one item list. Note rows: Pin/Unpin (ADR-092, cookie-only for now, ahead of a Pinned/Recent list), Rename, Delete. Folder rows: New note here, Delete.
* **Inline note & folder management**: create, rename, and delete both from that row menu (ADR-084, ADR-095, ADR-099) — a rename rewrites every `[[wikilink]]` pointing at the note, and deleting either is recoverable via the vault Bin (a permanently-empty folder is the one exception: nothing to lose, so it's unlinked outright instead of round-tripping through `.trash/`).
* **Vault Bin**: recoverable trash view (ADR-085), surfaced as its own row in the main menu (ADR-086) rather than a header icon — restore a deleted note to its original path or purge it for good.
* **Rich Markdown Reader & Live Editor**, built on Stylo (ADR-080) — CodeMirror 6 in "in-place" live-decoration mode, editing canonical Markdown text directly with no shadow document tree, chosen over ProseMirror/Lexical specifically to protect frontmatter/wikilink/math round-trip fidelity:
  * Clean typography with GitHub-flavored markdown, syntax-highlighted code blocks, and math formulas.
  * Clickable `[[Wikilink]]` routing (clicking `[[OAuth]]` navigates directly to `OAuth.md` or centers the 3D nebula), with wikilink autocomplete while typing `[[`.
  * Dynamic YAML frontmatter inspector and tag editor, with a collapse toggle (ADR-095).
  * Autosave (ADR-081) on a debounce, and a "hide `.md` extensions" preference (ADR-092, Obsidian convention) — both togglable from Settings.
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
* **Active Nebula Synergy**: Referencing a note in chat is one of several triggers (alongside opening a note from the vault tree or a wikilink — see Module A's ADR-097) that fly the ambient background's camera to and highlight the corresponding node cluster.

---

### ⚙️ Module E: Settings & Preferences

A dedicated Settings panel (ADR-094 trimmed its row density and added a collapse-all control) that has grown well past Module B's original theme drawer:

* **Notifications & Confirmations (ADR-087)**: toast notification system, plus a three-way delete-confirmation style — modal dialog, inline, or none — governing every destructive vault action (note delete, folder delete, trash purge).
* **Nebula appearance mirror (ADR-091)**: every ambient-nebula dock knob from Module A (mode, forces, appearance, scrim sliders) is also exposed here inline, plus a toggle to hide the floating dock entirely.
* **Slack & theme footer (ADR-082)**: a read-only Slack daemon connectivity status pill, and the light/dark theme switch, pinned below the Settings scroll area so a long list can't scroll them out of reach.

---

## 3. Backend Primitives & Data Contracts

The dashboard communicates with Sympose's native FastAPI gateway on `http://localhost:8000`:

### 1. Vault Explorer & Graph API (`/api/vault/*`)
* **`GET /api/vault/graph`**:
  * Returns: `{ nodes: [{ id, label, folder, tags, val }], links: [{ source, target }] }`
  * Sub-5ms response time served directly from Python in-memory index.
  * Whole-vault, persona-independent — the nebula is an explorer surface.
* **`GET /api/vault/tree?persona=<handle>`** *(shipped)*:
  * Returns: `{ persona, tree: [{ name, path, type: "folder" | "note", children? }] }` — the ADR-078 manifest's note nodes folded into a nested directory tree, folders before notes, each group sorted case-insensitively. Ghost nodes (unresolved `[[wikilinks]]`) are excluded.
  * **Persona-scoped**: filtered to the persona's `vault_folders` via a vault-relative path-prefix match, the same sandbox every other `/api/vault/*` read honours. `samantha` (`["*"]`) sees the whole vault.
  * The manifest alone only knows about notes, so an empty folder is merged in from a live, directory-only disk listing (`VaultManager._list_real_folders`, ADR-098) — otherwise a folder with nothing in it yet would be structurally invisible rather than just stale.
* **`GET /api/vault/cloud`**:
  * Returns high-density note and tag taxonomy with reference counts for 2D bubble clouds.
* **`GET /api/vault/note?path=<rel_path>`**:
  * Returns raw Markdown, frontmatter metadata, and forward links.
* **`POST /api/vault/note`** *(shipped, ADR-083)* / **`PUT /api/vault/note`**:
  * `POST` creates a new note (404-free — 409 if one already exists at that path); `PUT` overwrites an existing one (404 if it doesn't exist). Both sandboxed.
* **`PATCH /api/vault/note`** *(shipped, ADR-084)*:
  * Renames a note and rewrites the `[[wikilinks]]` that pointed at it.
* **`DELETE /api/vault/note?path=<rel_path>`** *(shipped, ADR-084)*:
  * Moves a note to `<vault>/.trash/` — recoverable, not unlinked.
* **`POST /api/vault/folder`** *(shipped, ADR-095)* / **`DELETE /api/vault/folder?path=<rel_path>`** *(shipped, ADR-099)*:
  * `POST` creates an empty folder (409 if something's already there). `DELETE` removes an empty folder outright, or — if it holds notes and/or subfolders — moves the whole thing to `.trash/` in one step and de-indexes every note inside individually, so the subtree drops out of search/the graph while it's in the bin.
* **`GET /api/vault/trash?persona=<handle>`** / **`POST /api/vault/trash/restore`** / **`DELETE /api/vault/trash?path=<trash_rel_path>`** *(shipped, ADR-085)*:
  * The Bin: list recoverable notes (newest deletion first), restore one to its original path, or purge one permanently. Works file-by-file regardless of whether a note landed in `.trash/` via a single delete or a whole-folder delete.
* **`GET /api/vault/backlinks?note=<name>`**:
  * Queries the inverted index for all incoming references.

### 2. Conversational API (`/api/chat/*`)
* **`POST /api/chat/message`**: Dispatches user prompt to `PersonaEngine`.
* **`GET /api/chat/stream?session_id=<id>`**: SSE stream delivering text tokens and structured action events.

### 3. Settings & Theme API (`/api/config/*`)
* **`GET /api/config` / `PUT /api/config`**: Reads and updates runtime parameters in `config.yaml` (including visualizer and theme settings).

### 4. Persona Roster API (`/api/personas`)
* **`GET /api/personas`** *(shipped)*:
  * Returns: `{ default: <handle>, personas: [{ handle, name, title, model, skills, is_default }] }` — a trimmed projection of each `profiles/*.yaml`, never the raw profile (no `soul_file` / `memory_file` paths, no `thinking_phrases`).
  * Feeds the Agent panel's identity card and switcher.
* The **active persona is client state**, not a server session: a `sympose:active_persona` cookie the dashboard passes as `?persona=` on sandboxed vault requests, mirroring the CLI's per-handle scoping. `samantha` (`vault_folders: ["*"]`) is the default.
* Planned: `GET /api/personas/{handle}/soul` and `/memory` for the card's (currently disabled) Soul / Memory panels.
* The switcher writes the cookie; `GET /api/vault/tree?persona=` is its first consumer (the browser re-fetches the tree on every persona switch).

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

* **Frontend**: `Vite` + `React 19` + `TypeScript` + `TailwindCSS` + `shadcn/ui` in `/ui`. Nebula: `react-force-graph-2d` (canvas) and `react-force-graph-3d` (Three.js) behind a shared wrapper, with `d3-force` / `d3-force-3d` and `three-spritetext`.
* **Build Target**: `vite build` compiles into `sympose/webui/` (ADR-079) — committed as package data and shipped with every install, not built at install time or by a CI bot commit. Vite's own default output dir, `ui/dist/`, is gitignored and unused; it isn't what ships.
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

## 7. Dashboard Authentication (ADR-064, implemented 2026-09-04)

ADR-051–053 (below) specified UI/UX and performance exclusively, leaving access control an open gap — flagged and closed the same day as a two-part fix, both zero-manual-install:

* **Password guard (ADR-064.1)** — HTTP Basic Auth (`sympose/auth.py`), not the signed session-cookie originally sketched: a smaller mechanism sized to the single-user threat model. `DASHBOARD_PASSWORD` gates every route through one global FastAPI dependency (`/`, `/docs`, every `/api/*` route). If unset on first boot, Sympose generates one, persists it to the workspace `.env`, and logs it once — no manual setup step, but never open by default.
* **Self-signed TLS (ADR-064.2)** — a certificate generated in-process on first boot into `<workspace>/.certs/` (gitignored) via the `cryptography` package, no external `openssl`/`mkcert` binary and no OS trust-store mutation. Falls back to plain HTTP with a warning if `cryptography` isn't installed rather than refusing to boot; `SYMPOSE_DASHBOARD_TLS=0` opts out for anyone terminating TLS externally.

Slack access is unaffected either way — it never routes through this server.

## 8. Architectural Decision Records

Founding decisions for this spec. Everything shipped since (note/folder CRUD, the vault Bin, the ambient nebula, Settings) is cited inline above by ADR number — the master index is `docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md`, not a duplicate list here.

* **[Web Dashboard UI Design Reference](../reference/ui-design-reference.md)** — design brief distilled from this spec for Claude Design.
* **[ADR-051: Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine](../../../docs/journal/2026-08/2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md)**
* **[ADR-052: In-Memory Metadata Caching & Sub-5ms Scalability Standard for Multi-Thousand Note Vaults](../../../docs/journal/2026-08/2026-08-29_adr-052-in-memory-metadata-caching-scalability.md)**
* **[ADR-053: Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers](../../../docs/journal/2026-08/2026-08-29_adr-053-cross-platform-native-desktop-launchers.md)**
* **[ADR-064: Dashboard/API Gateway Auth — HTTP Basic Auth + Self-Signed TLS](../../../docs/journal/2026-08/2026-08-30_adr-064-dashboard-api-auth-plan.md)** — implemented 2026-09-04, see §7 above.
* **[ADR-044: In-Memory Inverted Index & Deterministic Backlink Lookup Engine](../../../docs/journal/2026-08/2026-08-27_backlink_lookup_engine_and_inverted_index.md)**
* **[ADR-011: Multi-Folder Vault Whitelisting & Sandboxing](../../../docs/journal/2026-08/2026-08-24_multi_folder_vault.md)**

