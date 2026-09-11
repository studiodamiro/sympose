---
title: "ADR-088 — Ambient Knowledge Nebula in the App Shell (Phase A)"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - knowledge-nebula
---

# ADR-088 — Ambient Knowledge Nebula in the App Shell (Phase A)

- **Status:** Accepted — implemented 2026-09-11 (Phase A).
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Promotes the Knowledge Nebula (Module A) from the standalone `/nebula`
  showcase into the product shell as the persistent background layer the design
  reference has always specified, in a deliberately narrow first phase.

## Context

The Knowledge Nebula was fully built but stranded. `KnowledgeNebula` (a shared
contract + a `react-force-graph-2d` renderer + a `react-force-graph-3d` / three.js
renderer + a `mode` wrapper, ADR-051/052 and the 2026-09-01 dual-renderer split)
existed only behind `/nebula` — a 400-line route component holding the graph
fetch, a tag-hub index pass, the filter derivation, and a hand-rolled
Obsidian-pink control dock. `GET /api/vault/graph` was live
([`server.py`](../../../sympose/server.py), whole-vault, persona-independent,
in-memory).

Meanwhile the design reference is unambiguous about where the nebula belongs
([`ui-design-reference.md`](../../wiki/reference/ui-design-reference.md) §4–§5,
[dashboard spec](../../wiki/architecture/dashboard-and-vault-explorer.md) §2
Module A): a **persistent full-bleed background layer behind the entire app
shell**, with two states — **Explore** (sharp, `pointer-events: auto`, panels
give way) and **Focus** (dimmed ambient drift, `pointer-events: none`, panels in
front) — a `2D | 3D` switch and an `Explore | Focus` switch, and **no top bar**.

The shell (`AppShell` at `/`) had no ambient layer and no such state. The risk
in wiring one is the performance SLA: an always-mounted WebGL scene behind every
panel is a standing cost even when idle, and three.js is ~600 kB.

## Decision

Ship it in phases. **Phase A** (this ADR) is the architecture — the layer, the
Explore/Focus machine, the Settings control, the 2D feed — with the smallest
possible shell edit so the risky part can be proven out. 3D and the "panels
collapse to the edges in Explore" behaviour are **Phase B**.

### The shell edit is four lines of intent

`AppShell` gains one hook (`useNebulaPreferences`), an idle gate
(`requestIdleCallback`, `setTimeout` fallback), and a lazy `<AmbientNebula>`
mounted `fixed inset-0` as the first child. The menu+stage row keeps no
stacking context of its own; `MainMenu` moves to `relative z-30` and the phone
`TopBar` to `z-30` so both outrank the layer. Everything else about the shell
is untouched. The root keeps `bg-background` — it is the backdrop the
transparent graph canvas composites onto; opaque panels (`bg-panel` /
`bg-background`) float over the nebula exactly as the §5 diagram shows.

The layer's own `z` is the Explore/Focus switch: `z-0` (behind everything,
`pointer-events: none`) in Focus, `z-20` (above the stage panels, live) in
Explore — with `MainMenu`'s `z-30` still on top so the rail stays usable and
Focus is one click away in Settings. Phase A Explore does not yet collapse the
panels to the edges (Phase B); the raised layer simply covers them.

### `<AmbientNebula>` — the layer

Imports `KnowledgeNebula2D` **directly**, not through the `mode` wrapper, so
three.js stays out of the bundle entirely in Phase A. Reads the graph, the
filter, and the effective theme through shared hooks (below). Renders the
2D canvas plus, in Explore only, the data-source badge, the folder legend, and
the control dock. `prefs.interaction` drives `dimmed` / `interactive` on the
renderer and `pointer-events` on the wrapper.

The app-shell lazy-imports it **after first paint** via the idle gate, so
`react-force-graph` never competes for TTFT. It builds to its own ~4.7 kB glue
chunk plus a separate ~335 kB (`gzip` ~92 kB) `knowledge-nebula-2d` chunk; the
main `index` bundle is byte-identical to before.

### Extraction — one implementation, two consumers

The showcase's duplicated logic is lifted to shared modules that both the
in-shell layer and `/nebula` now use:

| Module | Was |
| --- | --- |
| `lib/nebula-graph.ts` → `buildMasterGraph()` | a private function in the route |
| `lib/use-nebula-graph.ts` | the route's `fetch` + fallback + `useState` |
| `lib/nebula-filter.ts` → `deriveNebulaFilter()` / `useNebulaFilter()` | an ~80-line `useMemo` in the route |
| `lib/use-effective-theme.ts` | a private hook in `theme-toggle.tsx` |

The showcase refactor is behaviour-preserving and drops 10 `no-explicit-any`
lint errors on the way (the `any` casts are now typed in `nebula-filter.ts`).

### `useNebulaPreferences` — every knob, cookie-backed

One hook shaped like `useEditorPreferences` / `useNotificationPreferences`:
cookie-backed per the UI-preference convention
([`lib/cookies`](../../../ui/src/lib/cookies.ts), §5), **not** a
`config_schema.py` runtime knob (ADR-077 §scope — per-browser view state, not
agent/backend config). A single `SPEC` table declares each knob's cookie name,
kind and default, and the read/write paths derive from it — the same
single-declaration discipline ADR-077 applies server-side.

All 24 knobs are persisted now (`interaction`, `mode`, `legend`, the filter
toggles, the display sliders, the two Focus-scrim knobs, the two panel-frost
knobs, the four forces). Which ones the **dock** exposes is a separate,
deliberately smaller list agreed with the lead:

- **Toggles:** Orphans, Tags, Legend, `2D | 3D` (3D segment present but
  disabled — hint text points at Phase B).
- **Display:** Labels, Node size, Link thickness.
- **Forces:** Center, Repel, Link force, Link distance.

`focusBlur` / `focusTint` (the Focus scrim) and `panelBlur` / `panelOpacity`
(the frosted shell panels, below) are exposed in Settings, not the dock — the
dock is only on screen in Explore, where both are invisible. No search input in
Phase A. Every unexposed knob keeps its default.

### Controls surfaces

- **`NebulaControls`** — the dock, re-skinned from the showcase's hand-rolled
  Obsidian-pink panel onto the app's semantic tokens, `ControlSection` /
  `ControlRow` primitives, `SegmentedControl`, and Hugeicons. Floats
  bottom-right over the layer in Explore.
- **`NebulaAppearanceSection`** — Settings → *Knowledge Nebula*: the
  `Explore | Focus` `SegmentedControl`, then four sliders — **Focus blur**
  (0–24 px) and **Focus tint** (0–100 %) for the scrim, and **Panel blur** /
  **Panel opacity** for the frosted shell panels. Next to the editor and
  notification sections. Default **Focus** ("Engine First, Face Second"),
  remembered in a cookie so the default is itself a knob.
- `SegmentedControl` gained a `disabledValues` prop — a general, one-line
  addition — so the 3D segment can be shown-but-inert without a no-op handler.

### The Focus scrim — two independent layers

Blur and tint fought each other in a single `color-mix` layer (element opacity
would have killed the blur; a low `color-mix` alpha meant tint could never
reach *fully covered*). Split into two `absolute inset-0` siblings behind the
panels: a **blur layer** — no fill, just `backdrop-filter: blur(focusBlur)`,
always opaque-free so the blur renders — and a **tint layer** — a solid
`bg-background` card at `opacity: focusTint`, a clean `0` (clear) → `1` (fully
covered). Both clear in Explore.

### Frosted shell panels — scoped to content + editor

`panelBlur` / `panelOpacity` let the nebula show through the **vault content
and editor panels only** — the only two with a fill to knob. `MainMenu` and
`ChatPanel` carry **no background of their own at all**: the nebula shows
straight through the rail and the chat surface, at whatever the global Focus
state already leaves visible — not gated by, or affected by, the panel-frost
knobs. One drop-in utility class, `.sy-frosted-panel` (for `bg-panel`),
replaces the solid-fill class on the content and editor surfaces. The shell
root carries a tri-state `data-nebula-frost` that gates only that class:

- **`off`** (default, `panelOpacity` 1 & `panelBlur` 0) — resolves to exactly
  the old solid `--panel`, no backdrop layer, no visual change.
- **`tint`** (`panelOpacity` < 1) — the fill goes translucent via
  `--sy-panel-opacity`; still no backdrop layer.
- **`blur`** (`panelBlur` > 0) — adds `backdrop-filter: blur(...) saturate(1.3)`
  and caps the fill at 60 % so the blur reads clearly even with the opacity
  knob at 100 %.

The editor is a special case: stylo paints its own opaque `--stylo-bg`
(`= --panel`) over the frosted div, so under `tint` / `blur` the `.cm-editor`
/ `.cm-scroller` background is forced transparent and `.sy-frosted-panel`
behind it does the tinting. stylo's floating menus set their background
explicitly (the shared frosted-menu rule) and are untouched.

**Known limit:** `backdrop-filter` reads the actual composited pixels behind
the panel — which is the canvas *after* the (full-viewport) Focus blur/tint
layers have already been applied. A high `focusTint` leaves little for panel
blur to reveal, regardless of the panel's own knobs; the two aren't truly
independent. Genuinely excluding panels from the scrim would need per-panel
geometry tracking (a `ResizeObserver`-driven mask on the tint layer) — real,
buildable, but a materially bigger, continuously-running piece of work, and in
tension with the project's hot-path discipline if done naively (tracking panel
rects through their open/close transitions). Not attempted here; flag it if
true independence is worth that cost.

### `/nebula` route

Kept as-is (dev showcase / isolated tuning / screenshots), now running on the
shared hooks.

## Consequences

- The vault graph is now part of the product, not a side route. Default Focus
  keeps the shell visually close to before — an 80 %-tint, 12 px-blur scrim over
  the graph, both dialable from Settings — and Explore brings it forward,
  interactive, with the dock.
- `MainMenu` and `ChatPanel` having no background of their own means they now
  show a faint hint of the (Focus-scrimmed) graph through them even at every
  default — a real, deliberate change from the pre-ADR-088 shell, where both
  were always solid regardless of what sat behind them.
- Phase A Explore raises the layer *over* the panels rather than collapsing
  them to the edges as the design reference specifies — the graph and dock are
  fully usable, but a left-open panel is covered, not tucked away. The real
  collapse-and-restore is Phase B with the 3D renderer, to keep this shell edit
  minimal.
- A clicked node's selection (and the 1-hop highlight it drives) is kept across
  `Explore ⇄ Focus` — the selection only *changes* while the layer is
  interactive, so a Focus trip and back leaves the graph framed exactly as it
  was.
- The folder legend has an on/off knob (`legend`, in the dock); it only renders
  in Explore either way.
- three.js is not in the shell bundle at all until Phase B. The 2D renderer
  chunk loads on idle after first paint.
- One more cookie family (`sympose:nebula.*`, 24 keys). Cookies, not
  `localStorage`, per the standing convention.
- `useEffectiveTheme` moving out of `theme-toggle.tsx` is a pure extraction;
  the toggle's behaviour is unchanged.

## Alternatives rejected

- **A first-class "Nebula" menu view.** A main-menu sentinel rendering the graph
  full-bleed on the stage. Simpler to wire, but it directly contradicts the
  design reference's "persistent background layer" and its Explore/Focus model —
  the nebula is meant to be *behind* the work, not another panel beside it.
- **Full always-mounted `<KnowledgeNebula>` (through the `mode` wrapper) in
  Phase A.** Most faithful to "persistent", but pulls three.js into the shell's
  dependency graph immediately for a renderer Phase A never shows. The direct
  `KnowledgeNebula2D` import keeps the wrapper (and three.js) for Phase B.
- **Mount the layer only when Explore is entered.** Cheapest, but then Focus has
  no ambient layer at all and the "dimmed drift behind your work" the spec calls
  for never exists.
- **The full Obsidian dock, ported verbatim.** The lead trimmed it to the list
  above; the rest of the knobs stay persisted but unexposed. The verbatim
  showcase styling (rose-500 pills, emoji) would also have been a foreign object
  in the shell — re-skinned instead.
- **`2D | 3D` in Settings → Appearance** (where §6.4 places it). The lead moved
  it into the dock next to the other renderer toggles; Settings keeps only
  `Explore | Focus` for Phase A.
- **Persist the fine dock knobs as `config_schema.py` runtime knobs** so they
  survive across devices. They are cosmetics, not backend config — cookies per
  ADR-077 §scope, matching the editor and notification preferences.
- **Auto-collapse the panels on entering Explore, now.** In scope per the design
  reference, but it tangles with `usePanels`, the breakpoint caps, and
  stash/restore — deferred to Phase B rather than bloating a 690-line
  `app-shell.tsx` in the same pass that introduces the layer.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
