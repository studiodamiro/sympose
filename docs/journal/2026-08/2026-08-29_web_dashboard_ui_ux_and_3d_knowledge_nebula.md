---
entry: 2026-08-29
created: 2026-08-29 15:35
type: daily-log
project: sympose
tags:
  - jour
  - sympose/journal
  - dashboard
  - knowledge-graph
  - 3d-galaxy
  - shadcn
  - theme-engine
  - ui-ux-spec
---

# Sympose Daily Log: 2026-08-29 (Part 3)

> **Session Focus:** Web Dashboard UI/UX Specification, 2D/3D Ambient Knowledge Nebula, Flat Architectural Design Standard, and Dynamic shadcn Theme Customizer Engine.  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
>
> **Downstream:** the ADRs below are distilled into a hand-off brief for visual mockups — [Web Dashboard UI Design Reference](../../UI_DESIGN_REFERENCE.md).

---

## 1. Executive Summary & Objectives

In this session, we established the comprehensive architectural specification for the **Sympose Web Dashboard, Standalone Vault Explorer, and 2D/3D Knowledge Nebula**.

We critically evaluated common AI web application aesthetics and deliberately rejected generic neon glows, heavy glassmorphism, and sluggish electron-style architectures. Instead, we established a **flat, high-craft architectural design system** prioritizing crisp geometry, Swiss/Bauhaus typography, pristine text legibility, instant light/dark mode adaptation, and complete theme customization.

Key architectural breakthroughs:
1. **Decoupled 2D/3D Ambient Knowledge Universe**:
   * A persistent background visualizer displaying the organic idea web of the user's Obsidian vault.
   * Instant toggle between **2D Flat Vector Map** (planar graph) and **3D Spatial Nebula** (WebGL/Three.js orbit space).
   * Two ergonomic operating states: **Explore Mode** (100% interactive, orbit/zoom/pan) and **Focus/Chat Mode** (ambient background drift behind frosted/matte workspace panels with zero click interference).
2. **Dynamic shadcn Theme Customizer Engine (Inspired by `ui.shadcn.com/create`)**:
   * Modular theme bar with dropdowns for **shadcn Styles** (*Nova, Maia, Sera, New York*), **Icon Packs** (*Lucide, Phosphor, Hugeicons*), **Corner Radius** (`0rem` sharp flat to `0.75rem`), and **Light/Dark Mode**.
   * Curated Sympose presets (*Obsidian Matte*, *Blueprint & Paper*, *Nordic Spruce*, *Swiss Grid*) and full custom color pickers for node bubbles and link strings.
3. **1:1 Parity with Obsidian Graph Controls**:
   * Complete physics and filter controls: Search, Tags, Existing Files Only, Orphans, Color Groups, Node Size, Link Thickness, Center Force, Repel Force, Link Force, and Link Distance.
4. **Sub-5ms Scalability Across 10,000+ Notes**:
   * In-memory inverted index and metadata caching in Python RAM.
   * Incremental `st_mtime` cache invalidation.
   * GPU `InstancedMesh` and Point Particles (single draw call) with physics equilibrium sleeping to eliminate CPU/GPU drain.
5. **Zero-Bloat Deployment Pipeline**:
   * Built with **Vite + React + TypeScript + TailwindCSS + shadcn/ui + Three.js** inside `ui/`.
   * Compiled to static assets in `ui/dist/` and served directly by Sympose's native FastAPI server (`sympose --web`), requiring zero Node.js runtime for end users.

---

## 2. Architectural Decision Records (ADRs)

### ADR-051: Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine

* **Context**:
  Most modern AI web interfaces copy generic dark-purple neon glows and heavy blur effects that cause visual fatigue, reduce text contrast, and lack customization. Users need a sovereign, high-contrast, flat architectural interface that works seamlessly in light and dark modes, provides full control over visualizer physics/colors, and supports both 2D and 3D knowledge exploration.
* **Decision**:
  * **Design Philosophy**: Reject gratuitous neon glows. Default to flat matte cards, crisp 1px borders (`border: 1px solid var(--border)`), and Swiss/editorial typography.
  * **Dual 2D/3D Renderer**: Feed a single backend graph contract (`/api/vault/graph`) into either a 2D HTML5 Canvas/SVG engine or a 3D WebGL (Three.js) orbital universe.
  * **Ambient Background States**:
    * *Explore Mode*: Background canvas is 100% sharp and interactive (`pointer-events: auto`).
    * *Focus/Chat Mode*: Background canvas dims by ~75% with a slow ambient drift (`pointer-events: none`), allowing users to chat and edit notes without visual distraction or click hijacking.
  * **Theme & Style Customizer**:
    * Adopt the `ui.shadcn.com/create` control pattern with custom Sympose tokens.
    * Support dynamic shadcn styles (`data-style="nova|maia|sera"`), corner radius (`0rem` flat to `0.75rem`), and interchangeable icon libraries (`lucide`, `phosphor`, `hugeicons`).
    * Provide curated presets (*Obsidian Matte*, *Blueprint & Paper*, *Nordic Spruce*, *Swiss Grid*) and live color pickers for node bubbles, link strings, and folder domains.
  * **Obsidian Graph Control Suite**: Implement full 1:1 control parity (Filters: Search, Tags, Existing, Orphans, Groups; Display: Arrows, Text fade, Node size, Link thickness; Forces: Center, Repel, Link force, Link distance).
* **Consequences**:
  * ✅ Timeless, distraction-free aesthetic with perfect WCAG contrast.
  * ✅ Instant 1-click theme and light/dark switching.
  * ✅ Complete parity with Obsidian's power-user graph controls.
  * ✅ Seamless multi-agent visual cues (nodes pulse when referenced by `@samantha`, `@grace`, or `@anais`).

---

### ADR-052: In-Memory Metadata Caching & Sub-5ms Scalability Standard for Multi-Thousand Note Vaults

* **Context**:
  Walking the filesystem and parsing regex across 5,000 to 20,000 Markdown files on every web request takes 200ms–800ms of disk I/O, violating Sympose's sub-second SLA. Rendering 10,000 individual DOM elements in the browser causes severe layout thrashing and drops frame rates to 5 FPS.
* **Decision**:
  * **Tiered Data Pipeline**:
    * *Tier 1 (Graph/Cloud Manifest)*: `/api/vault/graph` and `/api/vault/cloud` return high-density node metadata (stem, tags, folder, link count, weight) compiled from Python RAM in $<2\text{ms}$.
    * *Tier 2 (Lazy Loading)*: Full note Markdown content is only loaded when a specific node is clicked (`GET /api/vault/note?path=...`).
  * **Python In-Memory Invalidation**:
    * Cache parsed note metadata in RAM.
    * Check `st_mtime` on file access and selectively patch updated notes when agent actions (`[WRITE_NOTE]`, `[APPEND_NOTE]`) execute.
  * **GPU Instanced Rendering & Physics Sleep**:
    * WebGL renders note nodes using `THREE.InstancedMesh` / Point Particles in a single GPU draw call.
    * Force-directed physics calculation automatically sleeps (`simulation.stop()`) after equilibrium is reached (~3s), reducing idle CPU to $<0.5\%$.
    * Background throttling halts animation loop when browser tab is inactive.
* **Consequences**:
  * ✅ Sub-5ms API response times across 20,000+ notes.
  * ✅ Total combined system RAM footprint under 165 MB (Python + Browser).
  * ✅ Silky 60 FPS rendering on entry-level hardware (Apple M-Series, Intel Core i3 8th Gen+).
  * ✅ Zero fan noise and minimal battery impact.

---

### ADR-053: Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers

* **Context**:
  Requiring users to open a terminal, remember flags (`sympose --web`), and manually navigate to `http://localhost:8000` creates significant daily friction. However, bundling Electron to get a native desktop icon introduces 150MB+ download bloat, 600MB+ RAM usage, and complex subprocess management.
* **Decision**:
  * **Zero-Bloat Native Launchers**:
    * **macOS**: Generate a lightweight (~60 KB) `/Applications/Sympose.app` bundle containing a native shell launcher and custom vector icon. Fully supports **Spotlight (`Cmd + Space`)**, Launchpad, and Dock pinning.
    * **Windows**: Generate a standard `Sympose.lnk` shortcut in the **Start Menu** and on the **Desktop**, targeting `msedge.exe --app="http://localhost:8000"`. Fully supports Windows Search (`Win + S`) and Taskbar pinning.
    * **Linux**: Generate a standard `~/.local/share/applications/sympose.desktop` entry integrating with GNOME Dash, KDE Kickoff, RoFi, and desktop panels.
  * **Frameless "App Mode" Execution**:
    * Launchers invoke the system's native browser engine in dedicated **App Mode** (`--app="http://localhost:8000"` or `pywebview` Cocoa/Edge WebView2).
    * Eliminates browser chrome, tabs, URL bars, and bookmark clutter, presenting a pristine standalone application window.
  * **Automated Post-Install Provisioning**:
    * Provide a built-in `sympose --install-app` command and automatic detection during 1-line installation (`pipx install git+https://github.com/studiodamiro/sympose.git`).
* **Consequences**:
  * ✅ 1-Click desktop launching from Spotlight, Start Menu, or Dock without terminal interaction.
  * ✅ Clean frameless window experience with zero browser tab clutter.
  * ✅ 100% cross-platform parity across macOS, Windows, and Linux.
  * ✅ **Zero Electron overhead**: <60 KB launcher footprint with <165 MB total system RAM.

---

## 3. Technology Stack & Distribution Pipeline

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               DEVELOPMENT ENVIRONMENT (ui/)                            │
│  - Framework: Vite + React 18 + TypeScript                                             │
│  - Styling: TailwindCSS + shadcn/ui (Radix Primitives)                                 │
│  - Icons: @phosphor-icons/react, lucide-react, @hugeicons/react                         │
│  - 3D/2D Engines: Three.js / 3d-force-graph / HTML5 Canvas                             │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                  📦 `npm run build`
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION DISTRIBUTION (ui/dist/)                              │
│  - Single static bundle (HTML, JS, CSS) embedded in Sympose package                    │
│  - Served locally by FastAPI (`sympose --web` / `app.py`) on http://localhost:8000     │
│  - Zero Node.js or npm runtime dependency for end users                                │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                  🚀 `sympose --install-app`
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        CROSS-PLATFORM DESKTOP LAUNCHERS                                │
│  - 🍎 macOS: `/Applications/Sympose.app` (Spotlight & Dock)                            │
│  - 🪟 Windows: `Sympose.lnk` (Start Menu & Taskbar)                                    │
│  - 🐧 Linux: `sympose.desktop` (Application Grid & Panel)                              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
