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
> **Downstream:** the ADRs below are distilled into a hand-off brief for visual mockups — [Web Dashboard UI Design Reference](../../wiki/reference/ui-design-reference.md).

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

## 2. Architectural Decision Records

- **[ADR-051 - Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine](./2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md):**
  flat matte design, one `/api/vault/graph` contract feeding a 2D or 3D
  renderer, Explore/Focus ambient states, a shadcn-style theme customizer, and
  full Obsidian graph control parity - rejecting the generic neon/glassmorphism
  aesthetic. (Security was out of scope - see
  [ADR-064](./2026-08-30_adr-064-dashboard-api-auth-plan.md).)
- **[ADR-052 - In-Memory Metadata Caching & Sub-5ms Scalability Standard](./2026-08-29_adr-052-in-memory-metadata-caching-scalability.md):**
  a tiered manifest/lazy pipeline, RAM cache with `st_mtime` invalidation, GPU
  `InstancedMesh` single-draw rendering, physics sleep - sub-5 ms API, < 165 MB
  RAM, 60 FPS. Rejected per-request filesystem walks and per-note DOM nodes.
- **[ADR-053 - Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers](./2026-08-29_adr-053-cross-platform-native-desktop-launchers.md):**
  ~60 KB macOS / Windows / Linux launchers invoking the system browser engine in
  frameless app mode - rejecting a 150 MB+ / 600 MB+ Electron bundle.

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
