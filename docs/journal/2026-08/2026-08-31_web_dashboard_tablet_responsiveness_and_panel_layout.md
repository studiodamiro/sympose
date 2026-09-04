---
entry: 2026-08-31
created: 2026-08-31 14:05
type: journal
project: sympose
tags:
  - jour
  - sympose/journal
  - dashboard
  - ui
  - app-shell
  - responsiveness
  - tablet
  - breakpoints
  - animation
---

# 2026-08-31: App-Shell Tablet Responsiveness — Breakpoint Model, Panel-Cap State Machine & Live Width Adoption

> **Session Focus:** Make the three `/shell` stage panels (content, editor, chat) survive a tablet-width viewport gracefully, and fix the panel width/animation system so a panel adopts freed space *while* its neighbour is still sliding out.
> **Lead Architect:** damiro
> **Engineering Partner:** Claude (Sonnet 5, Claude Code)

---

## 1. Summary

The `/shell` mockup worked at desktop width but the UX broke down as the stage
narrowed toward tablet: three panels crowded the chat, the menu ate space, and
the reveal animations that had been added the previous session snapped or
stuttered under the new layout pressure.

This session added a real tablet story and rebuilt the width/animation
plumbing under it:

1. **Breakpoint model** (`use-breakpoint.ts`) — `phone / tablet / desktop`, keyed
   off the shell's own measured width, with a max-visible-panels cap per class.
2. **Panel-visibility state machine** (`use-panels.ts`) — one cookie holds the
   full open-intent; the breakpoint cap is a *view* over it, never a mutation.
   Opening past the cap evicts the oldest, sequenced so the two don't animate
   over each other.
3. **Live width adoption** (`use-fill-width.ts`, `use-transient-flag.ts`) — a
   panel now grows into the space a sliding neighbour frees *frame by frame*,
   instead of jumping once the neighbour finished.
4. **Chat-panel / stage refactor** — `ChatPanel` is now a pure body; the stage
   action group is a sibling (`ChatActionGroup`); chat visibility is driven by
   `usePanels` like the other two panels, not its own internal state.

Still a **mock** — inert toolbar/composer, hard-coded transcript, no data wiring.
`tsc` / `eslint` / `vite build` all clean; verified with frame-by-frame
Chrome-DevTools-Protocol capture at 1440 and 1024.

---

## 2. Key Decisions

### 2.1 Breakpoints off the shell's *own* width, not `window`

`useBreakpoint(ref)` measures the shell root element with a `ResizeObserver`.
`window.innerWidth` / `matchMedia` / `documentElement.clientWidth` all gave stale
or wrong first reads in practice (dev overlays, embedded webviews, headless
capture), which showed up as a "tablet experience in a desktop browser". The
element box is the source of truth.

| Class | Width | Stage behaviour |
| :-- | :-- | :-- |
| `phone` | `< 768` | cap 1 — layout is a **later pass** |
| `tablet` | `768–1279` | cap 2 — any pair of the three; editor toolbar wraps |
| `desktop` | `≥ 1280` | cap 3 — all inline |

iPad Mini sits on the 768 / 1280 boundaries, so it reads as `tablet` in both
orientations — deliberately, per damiro's "viewport width for simplicity, iPad
Mini reference".

### 2.2 One source of truth, the cap is a view

`usePanels` keeps the **full open-intent** in `sympose:shell.order` (a CSV of
panel ids, oldest-first). `visible` is `order.slice(-cap)` — a `useMemo`, never
written back. So a desktop three-panel layout that the user drops to two panels
by resizing to tablet width **returns intact** when they widen again; the cap
only ever changes which slice renders. First run (no cookie): `["chat"]` — menu
expanded, an empty chat, nothing else.

Opening a panel when `visible` is already at the cap **evicts the oldest visible
one**. Eviction is *sequenced*: the evicted panel is removed immediately (it
slides out), then after `SEQUENCE_MS` (320) the newcomer is appended (it slides
in) — so they don't cross-fade over each other.

### 2.3 Auto-collapse the menu on small breakpoints — but keep it draggable

`sympose:pref.autoCollapseMenu` (cookie, default **on**; the Settings UI toggle
is deferred). On a non-desktop breakpoint the menu snaps to its icon rail, but
the drag handle stays and the user can pull it back out. A `forced` flag
remembers the rail came from the breakpoint, not the user — so a trip back to
desktop restores the expanded width, *unless* the user has since collapsed it
themselves. The adjustment is done render-phase ("derive state from a changing
value"), not in an effect, to satisfy the project's strict
`react-hooks/set-state-in-effect` rule.

### 2.4 Only the editor fills; only on small breakpoints

`editorFill = breakpoint !== "desktop" && editorOpen && !chatOpen`.

- **Content never grows** — it is navigation, it keeps its dragged width even
  when it is the only panel open. (A full-width content panel on a tablet was
  explicitly rejected.)
- **The editor fills** the leftover width when nothing sits to its right — but
  **only on tablet/phone**. On desktop it keeps its dragged width and the freed
  area just sits blank; a full-bleed editor is an uncomfortable measure on a
  wide screen.
- Chat, being rightmost, always fills whatever it is given.

### 2.5 Panel z-stack: content (20) › editor (10) › chat (0)

Every panel parks one width to its left (`margin-inline-start: -size`) while
closed, clipped by the stage's `overflow-hidden`. With this z-order a parked
panel is always hidden *behind its left-hand neighbour* and appears to slide out
from that neighbour's right edge — the editor emerges from the content panel's
edge, chat from the editor's edge. Content parks off the stage's left edge and
is clipped there before it can reach the menu.

### 2.6 Chat reading column — symmetric gutters even in a narrow slot

The chat column is `mx-auto`, capped at the `42rem` measure. In the two-panel
tablet cases the slot is narrower than the measure, so the column goes
full-bleed — and it was reading as flush-cramped and slightly off-centre. Two
fixes: the chat slot's asymmetric `pe-2` (right-only) was removed so `mx-auto`
centres the column in the *full* slot; and the inner gutter went `px-4 sm:px-6`
→ `px-6 sm:px-8`, a guaranteed symmetric minimum so the text never runs to the
slot edges. Chat-only and desktop are unchanged — the column still caps at the
measure and dead-centres.

---

## 3. The width-adoption problem (and why the animations were jerky)

### 3.1 A `ResizeObserver` never sees a neighbour slide

`useFillWidth(ref)` returns the pixel width free to a panel: its flex parent's
inner width minus its own `offsetLeft`. It was kept live with a `ResizeObserver`
on the stage and left-hand siblings — which only fires on **content-box size**
changes. When the editor closes it animates `margin-inline-start`, a **position**
change the observer never reports, so the chat kept its stale (narrow)
`flex-basis` and only jumped to the new width once the editor's transition had
finished. This was visible on both desktop and tablet.

**Fix:** `useFillWidth` now *also* samples every animation frame while any stage
transition is running. Transition events bubble, so one `transitionrun` /
`transitionend` listener on the stage covers every panel; the sampler runs on a
self-expiring 600 ms deadline so a stray event can't leave it looping.

### 3.2 Chat slot rebuilt around `flex-grow`

The chat slot is now `flex-grow: 1` + a `max-width` clamp:

- `flex-grow: 1` makes it adopt the free width **live, via flex reflow**, as the
  editor's margin animates — no JS in that path at all.
- `max-width` clamps it to the same measurement, giving its *own* open/close a
  real pixel target to tween between.

### 3.3 `useTransientFlag` — arm the transition only for a deliberate toggle

`useTransientFlag(dep, ms = 320)` is `true` for `ms` after `dep` changes. It arms
the `max-width` CSS transition **only** for the ~320 ms a panel is deliberately
opening or closing (`chatToggling` on the chat slot, `fillToggling` on the
editor's fill clamp). The rest of the time `max-width` follows the live
measurement *instantly*, so a panel tracks its neighbour's slide instead of
chasing it with a 300 ms transition lag.

### 3.4 Real measured targets, not sentinels; symmetric easing

The editor's fill clamp previously interpolated from `stageW || 4000` — a
sentinel far larger than the real width, so ~90 % of the duration passed with
nothing visibly changing and then it snapped. It now interpolates to the real
measured `availW`. Easing on the width tweens went `ease-out` → `ease-in-out`;
`ease-out` front-loads the motion and still reads as a snap.

---

## 4. Files

| File | Change |
| :-- | :-- |
| `ui/src/lib/use-breakpoint.ts` | **new** — `Breakpoint` type, `PANEL_CAP` map, `useBreakpoint(ref)` (ResizeObserver on the shell root) |
| `ui/src/lib/use-panels.ts` | **new** — stage-panel visibility with a per-breakpoint cap; full intent in `sympose:shell.order`, cap is a derived view; sequenced oldest-wins eviction |
| `ui/src/lib/use-fill-width.ts` | **new** — real free width for a panel; `ResizeObserver` for static changes **plus** a per-frame sampler while any stage transition runs |
| `ui/src/lib/use-transient-flag.ts` | **new** — `true` for N ms after a dep changes; arms a CSS transition only for a deliberate open/close |
| `ui/src/lib/cookies.ts` | `getCookieBool` / `setCookieBool` helpers |
| `ui/src/routes/app-shell.tsx` | breakpoint + `usePanels` wiring; render-phase menu auto-collapse with a `forced` flag; `ChatActionGroup` as a stage sibling; chat slot rebuilt (`flex-grow` + measured `max-width` + `chatToggling`); `editorFill` gated to non-desktop |
| `ui/src/components/sympose/chat-panel.tsx` | `ChatPanel` is now a pure body (no internal `bodyOpen`); `ChatActionGroup` extracted as a second export; chat column gutters `px-4 sm:px-6` → `px-6 sm:px-8`, asymmetric slot padding removed |
| `ui/src/components/sympose/markdown-panel.tsx` | `fill` prop (grow into leftover width, no handle, toolbar end-padding clears the floating action group); toolbar mark buttons cluster in `MarkGroup`s that `flex-wrap` on narrow widths, save button pinned top-right; `max-width` fill clamp via `useFillWidth` + `fillToggling` |
| `ui/src/components/sympose/content-panel.tsx` | `z-20` (top of the stage panel stack); comment that it never grows |
| `ui/src/components/sympose/index.ts` | export `ChatActionGroup` |

---

## 5. Verification

Frame-by-frame CDP capture (headless Chrome, `Emulation.setDeviceMetricsOverride`)
at 1440 and 1024:

- **Desktop 3-panel retained** after a resize to tablet width and back (cookie
  holds intent, cap re-derives the view).
- **Tablet clamps to 2**; opening a third slides the oldest out first, then the
  newcomer in.
- **Editor fills only when alone on tablet**; on desktop it holds its width and
  the freed area is blank.
- **Chat tracks the editor's slide frame by frame** — chat's left edge follows
  the editor's right edge every frame, both breakpoints, landing at the correct
  full width (desktop 704 → 1184 px; tablet 496 → 976 px).
- **Chat column gutters symmetric** in `content+chat` and `editor+chat` on a
  1024 tablet; chat-only still dead-centred at the measure.
- **Menu** auto-collapses to the rail on tablet, stays draggable, restores on a
  desktop return.

---

## 6. Action Items & Next Steps

- [ ] **Phone (`< 768`) layout** — cap is 1, but the single-panel presentation,
      the menu, and the stage action group still need a portrait design pass.
- [ ] **Settings UI** — surface the `sympose:pref.autoCollapseMenu` toggle
      (cookie + behaviour exist; there is no control yet).
- [ ] Per-frame `offsetLeft` reads during a transition force layout — acceptable
      for the ≤ 600 ms window, but revisit if it shows on low-end hardware.
- [ ] Carry the remaining open items from the previous entry
      (`2026-08-31_web_dashboard_chat_and_markdown_panels.md`): save-button
      semantics, reader vs source wikilinks, MD prose contrast, real data wiring.
