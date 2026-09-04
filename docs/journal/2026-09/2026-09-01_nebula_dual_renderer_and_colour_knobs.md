---
entry: 2026-09-01
created: 2026-09-01 11:38
type: journal
project: sympose
tags:
  - jour
  - sympose/journal
  - dashboard
  - ui
  - knowledge-nebula
  - force-graph
  - 2d-3d
  - obsidian-graph
---

# 2026-09-01: Knowledge Nebula — Audit, Dual 2D/3D Renderer Split & Node Colour Knobs

> **Session Focus:** Review / audit / test the `/nebula` showcase and its 3D graph, then build the 2D (Obsidian-default) renderer behind a `2D | 3D` switch, give both a zoom-gated label toggle, and add two signed colour knobs for light/dark legibility.
> **Lead Architect:** damiro
> **Engineering Partner:** Claude (Sonnet 5, Claude Code)

---

## 1. Summary

Started with an audit of the single 3D `KnowledgeNebula` component
(`react-force-graph-3d` / three.js) shipped in the previous nebula commit. Found
six real defects and three fully dead controls; fixed the clear wins and, per
damiro's call, **removed** the two controls that were pretending to work
(`Text fade threshold`, `Groups`) rather than half-building them.

Then delivered the ADR-051 "dual 2D vector / 3D WebGL" commitment for real: the
monolithic component was split into a **shared contract + two renderers + a thin
`mode` wrapper**, and a new `react-force-graph-2d` canvas renderer reproduces
the Obsidian default graph (flat discs, pan/zoom, labels that fade in as you
zoom). A top-bar `2D | 3D` pill switches them, remembered in a cookie.

Follow-ups in the same session, all driven by damiro iterating on legibility:

- **Node labels** toggle — gates the 2D zoom-gated labels; then extended to 3D
  with `three-spritetext` sprites culled by camera distance (same "appears when
  you get close" behaviour), sharing the one toggle.
- **Background separation** knob — signed lightness shift of node colours vs the
  background (toward black in light mode, toward white in dark; negative pulls
  them *into* the background for a softer read).
- **Color vividness** knob — signed HSL-saturation scale, orthogonal to
  separation ("how colourful" vs "how visible").

Still a **mock/showcase** on `mock-nebula.json` (868 notes + 188 tag hubs);
`tsc` and `vite build` clean throughout; `eslint` unchanged except its
pre-existing `no-explicit-any` debt across these files.

---

## 2. Audit of the 3D nebula

### 2.1 Defects fixed

| # | Problem | Fix |
| :- | :- | :- |
| 1 | `ToggleSwitch` was declared **inside** the route component — new type every render, so all six toggles remounted on every keystroke / slider drag (killed the pill transition; `react-hooks/static-components` errors). | Hoisted to module scope, takes `isLight` as a prop, added `role="switch"` / `aria-checked`. |
| 2 | `animateBirth` had **no unmount cleanup** — leaving `/nebula` mid-animation left a `setInterval` firing `refresh()` / `d3ReheatSimulation()` against a disposed renderer. | Added a teardown `useEffect` clearing `timerRef` / `animFrameRef`. |
| 3 | Orphan nodes were **unsearchable** — the orphan-dim `return` ran before the query match, so a matching disconnected note was never highlighted or framed (up to 372 nodes with Tags off). | Compute the query match first; an active match overrides the orphan dim. |
| 4 | `d3-force-3d` was imported but only resolved as a **transitive** dep of `react-force-graph-3d`. | Added as a direct dependency (kept the local `src/types/d3-force-3d.d.ts` shim). |
| 5 | `__scale` birth-ramp value was written but **never read** — "Animate" is a staggered pop-in, not a grow-in. | Left as-is (documented); real grow-in deferred. |
| 6 | Node click always snapped the camera to a **fixed frontal angle** (`z + distance`) instead of dollying along the current orbit. | Left as-is (documented); deferred. |

### 2.2 Dead controls removed

- **`Text fade threshold`** slider — state existed and rendered, but was never
  passed to the component and the 3D renderer draws no in-scene text at all.
  Removed. Its intent is now served by the always-on zoom/distance-gated labels
  plus the new **Node labels** toggle.
- **`Groups`** accordion — "New group" pushed a hard-coded
  `{query:"path:Projects", color:"#ec4899"}` row that nothing consumed. Removed
  the section and `customGroups` state.
- **Reset defaults** cleaned up (`nodeRelSize` back to the true initial
  `1.67 × 2.4`, section-number comments renumbered).

> The wiki spec (`dashboard-and-vault-explorer.md` §2 Module A) still listed both
> as parity items. Updated there to match what actually ships.

---

## 3. Key Decisions

### 3.1 One component → shared contract + two renderers + wrapper

| File | Role |
| :- | :- |
| `knowledge-nebula-shared.ts` | `KnowledgeNebulaHandle`, `KnowledgeNebulaProps` (+ `mode`), `useElementSize`, `createNodeTooltip`, `clamp`, `nodeRenderVal`, and the colour helpers `blendHex` / `adjustSaturation` / `nebulaNodeColor`. |
| `knowledge-nebula-3d.tsx` | the WebGL cloud, moved verbatim from the old file, plus the SpriteText labels (§3.4). Exports `KnowledgeNebula3D`. |
| `knowledge-nebula-2d.tsx` | **new** — the `react-force-graph-2d` canvas renderer. Exports `KnowledgeNebula2D`. |
| `knowledge-nebula.tsx` | thin `forwardRef` wrapper: `({ mode = "3d", ...props }, ref)` renders one child or the other and forwards the ref. |

The public API (`<KnowledgeNebula ref={…}>` + `KnowledgeNebulaHandle`) is
unchanged, so the route never sees the swap — `ref.current` stays valid across a
mode toggle because both children bind the same imperative handle
(`zoomToFit` / `focusNode` / `fitNodes` / `animateBirth`).

`index.ts` still does **not** re-export the barrel (it pulls three.js +
`react-force-graph`); import it directly and lazily as before.

### 3.2 2D renderer = the Obsidian default graph

- Folder-coloured discs (default node paint), degree-sized, hairline links,
  transparent background.
- **Pan + scroll-zoom** (`enablePan/ZoomInteraction`), node drag, hover tooltip
  (shared HTML), highlight/dim on search + selection, arrows.
- **Zoom-gated labels** drawn under each disc via `nodeCanvasObject` /
  `nodeCanvasObjectMode: "after"`, alpha ramping between `globalScale`
  `LABEL_FADE_START` (1.6) → `LABEL_FADE_END` (3.4). Below that, zero label cost.
- Camera flights map to `centerAt()` + `zoom()` — `focusNode` / click frames the
  1-hop cluster (centroid + radius → zoom factor, biased by the
  `clickZoomDistance` knob: `60 / distance`); `fitNodes` uses the built-in
  filtered `zoomToFit`.
- **Same force math** as 3D (`charge = -repel*12`, link distance/strength,
  `forceRadial(0).strength(center*0.8)`) so the Forces sliders feel identical in
  both modes. Added `d3-force` as a direct dep + `src/types/d3-force.d.ts` shim.
- Initial framing via `onEngineStop` → `zoomToFit`, with a 1.5s `setTimeout`
  safety net.

### 3.3 Mode switch + persistence

Top-bar `2D | 3D` segmented pill, built inline to match the page's bespoke
overlay chrome rather than the token-based `<SegmentedControl>` (the nebula page
theming is manual `isLight`, not `data-theme`). Choice stored in the
`nebula-view-mode` cookie (UI-pref convention: cookies, not `localStorage`).
`Auto Rotate Camera` shows only in 3D; the subtitle reads `… · 2D vault graph` /
`3D`.

### 3.4 In-scene 3D labels (`three-spritetext`)

The 3D renderer had no in-scene text — only the hover tooltip. Rather than gate
nothing, added `three-spritetext` sprites via `nodeThreeObject` +
`nodeThreeObjectExtend` (keeps the sphere). A `requestAnimationFrame` loop fades
each sprite by **camera distance** — `LABEL_FADE_FAR` 260 → `LABEL_FADE_NEAR`
110 world units — the 3D analogue of the 2D `globalScale` gate. The loop only
touches cheap props (`.visible`, `.material.opacity`, `.position.y`); dynamic
inputs (`showLabels`, highlight set, `nodeRelSize`) are read through refs so the
sprite builder and loop stay identity-stable and never trigger a node rebuild.
Theme recolour walks the sprite map once on `isLight` change (the colour setter
regenerates the texture — never per frame). Textures disposed on unmount.

**Cost noted:** ~1050 `SpriteText` textures are built up front in 3D, so
entering 3D can hitch briefly on weak GPUs. 2D has no such cost (one `fillText`
per frame). Deferred: lazy sprite build / smaller `textHeight`.

### 3.5 Two signed colour knobs

Both applied in one shared path, `nebulaNodeColor(node, isLight, separation,
vividness)`, consumed identically by both renderers for the non-dimmed node
case:

1. **`nodeVividness`** ∈ `[-1, +1]` — `adjustSaturation` converts the folder hex
   to HSL, scales `S` (`-1` = greyscale, `0` = as-is, `+1` = full), back to hex.
2. **`nodeSeparation`** ∈ `[-0.75, +0.75]` (UI) — `blendHex` toward `#000000`
   (light mode) / `#ffffff` (dark mode) when positive, toward the opposite when
   negative. `0` = palette untouched.

Vividness runs first, then separation. Default `0` for both, so today's look is
unchanged until a knob moves. Rejected a photo-style contrast S-curve: a flat
disc has no tonal range to spread, and it collapses the 14 folder hues toward
indistinct extremes.

### 3.6 Final control roster (`/nebula` showcase)

- **Top bar:** `2D | 3D` · 🎯 Center & Fit · ☀︎/🌙 theme · ← back
- **Filters:** Search · Tags · Attachments · Existing files only · Orphans
- **Display:** Arrows · Auto Rotate Camera *(3D)* · Node labels · Background
  separation · Color vividness · Node size · Link thickness · Note Spawn Delay ·
  Zoom In Closeness · 🎯 Center & Fit · Animate
- **Forces:** Center force · Repel force · Link force · Link distance

---

## 4. Files

| File | Change |
| :- | :- |
| `ui/src/components/sympose/knowledge-nebula.tsx` | **rewritten** as the thin `mode` wrapper (was the full 3D component). |
| `ui/src/components/sympose/knowledge-nebula-shared.ts` | **new** — shared types/helpers + `blendHex` / `adjustSaturation` / `hexToHsl` / `hslToHex` / `nebulaNodeColor`. |
| `ui/src/components/sympose/knowledge-nebula-3d.tsx` | **new** — 3D renderer (moved + audit fixes + `three-spritetext` labels + `nodeSeparation` / `nodeVividness`). |
| `ui/src/components/sympose/knowledge-nebula-2d.tsx` | **new** — Obsidian-style 2D canvas renderer. |
| `ui/src/types/d3-force.d.ts` | **new** — module shim for `forceRadial` etc. (mirrors `d3-force-3d.d.ts`). |
| `ui/src/routes/nebula-showcase.tsx` | `ToggleSwitch` hoist; removed `Text fade threshold` + `Groups`; orphan/search reorder; `mode` state + cookie + `2D\|3D` pill; `showLabels` / `nodeSeparation` / `nodeVividness` state, sliders, prop pass, reset. |
| `ui/package.json` / `package-lock.json` | `+ react-force-graph-2d`, `+ d3-force`, `+ d3-force-3d` (promoted), `+ three-spritetext`. |
| `docs/wiki/architecture/dashboard-and-vault-explorer.md` | Module A control roster + stack updated to the as-built implementation. |

*(The 2D/3D split + labels landed in commit `2efcb8a`; the colour knobs + these
docs are this commit.)*

---

## 5. Verification

- `cd ui && npm run typecheck` — clean.
- `cd ui && npm run build` — clean (nebula chunk ~1.65 MB / ~440 KB gzip:
  three.js + canvas + spritetext).
- `cd ui && npm run lint` — no new hard errors; the ~70 `no-explicit-any` and
  one `react-hooks/exhaustive-deps` warning are pre-existing style debt across
  these files. The six `Cannot create components during render` errors from the
  audit are gone.
- Vite dev server transforms all five modules (HTTP 200, valid output) and
  pre-bundles `react-force-graph-2d` / `d3-force` / `three-spritetext`.
- **No browser-automation pass this session** (no CDP/Playwright tool available;
  shared dev server left running). Live check is manual at `:5173`.

---

## 6. Action Items & Next Steps

- [ ] **3D label hitch** — ~1050 SpriteText textures built on mount; lazy-build
      or shrink `textHeight` if it's noticeable on weak GPUs.
- [ ] **Node click camera angle (3D)** — dolly along the current orbit instead
      of snapping to `z + distance`.
- [ ] **`__scale` grow-in** — wire the birth-animation scale ramp (currently a
      staggered pop-in only).
- [ ] **`no-explicit-any` debt** — 70 across the nebula files; the rest of `ui/`
      passes the rule.
- [ ] **`Thoughts` folder** has no palette entry (`FOLDER_COLORS`) — renders
      fallback grey with no legend row; the mock vault uses it.
- [ ] **Dual-fire background click (3D)** — container `pointerup` guard +
      `onBackgroundClick` can both fire; harmless today, fragile.
- [ ] Consider cookie-persisting `showLabels` / `nodeSeparation` /
      `nodeVividness` (currently session-only, like the other Display knobs).
- [ ] Real data: swap `mock-nebula.json` for `GET /api/vault/graph` (one-line
      change upstream; contract identical).
- [ ] Fold `separation` + `vividness` into a single "Pop" preset with the raw
      knobs behind an "advanced" toggle if the Display panel gets busier.
