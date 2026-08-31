---
entry: 2026-08-31
created: 2026-08-31 19:20
type: journal
project: sympose
tags:
  - jour
  - sympose/journal
  - dashboard
  - ui
  - app-shell
  - responsiveness
  - mobile
  - phone
  - top-bar
---

# 2026-08-31: App-Shell Phone Shell — TopBar, Sliding Menu Rail & Per-View Surfaces

> **Session Focus:** Give the `/shell` mockup a phone layout (`< 768`) — the same tablet mechanics with the menu access moved to a fixed top bar, plus per-view surface treatments and remembered state.
> **Lead Architect:** damiro
> **Engineering Partner:** Claude (Sonnet 5, Claude Code)

---

## 1. Summary

The tablet pass left `phone` as a stub. This session filled it in, iterating
heavily against damiro's feedback. The guiding decision, after a false start
with a drawer/scrim menu, was **"almost the same as tablet"**: keep the tablet
stage mechanics wholesale and change only two things —

1. A fixed **`<TopBar>`** (phone only) carries what `<MainMenu>` normally holds:
   the brand mark, the vault button, Settings, the account, and the chat action
   group.
2. The menu is **hidden by default** and slides in and out — the same
   `margin-inline-start` park the stage panels use, **not** an overlay — driven
   by the TopBar's vault button, which toggles the rail and the content panel as
   one "vault view".

On top of that: per-view surface treatments (plain Settings/Agent pages, a
borderless plain editor), a tablet animation fix, and cookie-remembered state.
Still a **mock**; `tsc` / `eslint` / `vite build` clean; verified with
frame-by-frame and state-dump CDP captures at 360 / 390 px and a
tablet/desktop regression pass.

---

## 2. Key Decisions

### 2.1 `<TopBar>` — the phone-only header

`ui/src/components/sympose/top-bar.tsx`. One fixed row:

```
[hex] Sympose ............. [ new-chat · bookmark ] [ vault ] [ cog ] [ @ ]
```

- `Sympose` wordmark is `hidden min-[380px]:inline` — the first thing to drop on
  the narrowest phones.
- The chat action group is the **same `<ChatActionGroup>`** the desktop stage
  floats top-right, just relocated.
- No bottom border (see §2.5).

`<MainMenu hideChrome>` drops its brand header and the Settings + account footer
rows (they are in the TopBar now) — **and nothing else**. The Collapse row, the
resize handle, and the rail ↔ labels toggle all still work exactly as on
tablet / desktop (this was a back-and-forth: an interim version locked the rail
to `MENU_MIN` and dropped Collapse entirely; damiro reverted that — the width
default is the rail, but Collapse must still expand it to labels like elsewhere).

### 2.2 The menu slides — it is not a drawer

`<MainMenu>` gained an `open` prop mirroring the stage panels: `open={false}`
parks it `margin-inline-start: -width`, clipped by the row's `overflow-hidden`,
and fades. On phone `open` is driven by the vault view state; on tablet/desktop
it is always `true`. The menu + stage are now wrapped in one
`flex … overflow-hidden` row so the menu can be clipped while parked.

### 2.3 The vault button toggles one "vault view" (rail + content together)

`revealMenu` in `AppShell`:

- **open** — remember the panel that was up (`beforeVault` ref), reset `active`
  off a Settings/Agent sentinel to `"Projects"`, `panels.open("content")`, show
  the rail.
- **close** (`closeVault`) — hide the rail, `panels.close("content")`, and
  `panels.open(beforeVault)` so the previous chat/editor comes back.

The rail is only rendered alongside content — `menuOpen = menuShown &&
contentOpen` — so the two can never desync into a rail floating over chat.

### 2.4 Per-view surfaces on phone

| View | Surface |
| :-- | :-- |
| **content** (a folder) | `<ContentPanel phone>` — `bg-panel`, **only** the top-left corner rounded, flush to every other edge; fills the space next to the 48px rail as an `absolute inset-0` crossfade layer |
| **Settings / Agent** | `<ContentPanel phone plain>` — no `bg-panel`, no rounding; `px-4 py-6` gutter — reads on the same plain background as the chat/editor. They are destinations, not the vault surface, so selecting them from the TopBar also hides the rail |
| **editor** | `<MarkdownPanel phone>` — the raised card drops entirely (no `bg-panel`, no rounding, no toolbar divider); `px-4` gutter, toolbar `ps-4 pe-4`, all aligned to the chat column |
| **chat** | `<ChatPanel compact>` — `px-4 py-6` gutter |

All of `settings · agent · chat · editor` share the same background, margin, and
padding, referenced to the chat panel (`px-4 py-6`, plain background, zero outer
margin).

### 2.5 Removed dividers

The TopBar's `border-b` and the editor toolbar's `border-b` **on phone** are
gone — per damiro, the phone chrome should read as continuous rather than
ruled. Tablet/desktop keep their toolbar divider.

### 2.6 Auto-hide the rail on a destination

Opening chat or the editor (chat icon, `[WRITE_NOTE]` badge) on phone slides the
rail away; so does selecting Settings or Agent from the TopBar. A folder pick
**keeps** the rail so its highlight stays as context beside the panel.

### 2.7 Tablet: sequence the editor-shrink before the chat enters

Regression damiro caught: on tablet, pressing chat while the editor is
full-width made the editor **snap** to its dragged width. The editor's
contraction and the chat's entrance were colliding. `toggleChat` now runs two
phases when `editorFill` is active: set `unfillFirst` (which forces `editorFill`
false → the editor's `max-width` tweens `availW → size` over ~300ms), then after
340ms `panels.open("chat")` so the chat slides into the space the editor
vacated. Frame capture confirms the two-phase motion.

---

## 3. Remembered state (cookies)

| Cookie | What |
| :-- | :-- |
| `sympose:shell.section` | the highlighted folder / section (`active`), validated against the known set on load |
| `sympose:shell.panel.scroll` | the content panel's inner scroll offset — debounced write, `useLayoutEffect` restore (via a new `scrollKey` prop on `<ContentPanel>`) |
| `sympose:shell.rail` | the phone vault-view open/closed state (`menuShown`) |
| `sympose:shell.order` | (existing) the stage-panel open set — content/chat/editor visibility rides on this |

---

## 4. Files

| File | Change |
| :-- | :-- |
| `ui/src/components/sympose/top-bar.tsx` | **new** — phone shell header (brand · chat actions · vault · Settings · account) |
| `ui/src/components/sympose/main-menu.tsx` | `open` prop (slide/park reveal); `hideChrome` prop (drop brand header + Settings/account rows only — Collapse, handle, rail↔labels toggle all unchanged) |
| `ui/src/components/sympose/content-panel.tsx` | `phone` prop (absolute crossfade layer, top-left-corner-only rounding, flush, no handle); `plain` prop (no fill/rounding — Settings/Agent); `scrollKey` prop (scroll persistence) |
| `ui/src/components/sympose/markdown-panel.tsx` | `phone` prop (drop the card + toolbar divider, `px-4` gutter aligned to chat, no handle, absolute crossfade layer) |
| `ui/src/components/sympose/chat-panel.tsx` | `compact` prop (`px-4 py-6` phone gutter) |
| `ui/src/components/sympose/index.ts` | export `TopBar` |
| `ui/src/routes/app-shell.tsx` | phone branch: `<TopBar>`, menu+stage wrapper row, `menuShown` / `revealMenu` / `closeVault` / `beforeVault`, `plainPage`, `toggleChat` / `toggleEditor` helpers, `unfillFirst` two-phase tablet sequencing, `active` + rail cookie persistence, `contentBody` / `chatMessages` hoisted for reuse across the phone/desktop branches |

---

## 5. Verification

CDP captures (`Emulation.setDeviceMetricsOverride`, `deviceScaleFactor: 2`):

- **360 / 390 px** — chat (rail hidden), content (48px rail + top-left-rounded
  panel), editor (plain, no dividers), Settings/Agent (plain background, `px-4`
  gutter matching chat).
- Vault button: chat → tap → Projects + rail; tap again → back to chat.
- Collapse row in the phone rail: state dump confirms it expands the menu to
  256px with labels, content stays open, chat stays hidden (it does **not**
  dismiss the vault view).
- Auto-hide: menu-shown → open editor / select Settings → rail slides away.
- **Tablet** editor-fill → chat: frame capture shows the editor narrowed with
  blank space to its right, then the chat populates it — sequenced.
- **Tablet / desktop** regression: unchanged (separate render branch).

---

## 6. Action Items & Next Steps

- [ ] Expanded rail on a 390px phone crushes the content column to ~130px —
      acceptable ("same as tablet", collapse it back) but a lower phone
      expand-ceiling could be nicer.
- [ ] `sympose:pref.autoCollapseMenu` still has no Settings UI toggle (carried
      from the tablet pass).
- [ ] Closing the vault view when nothing preceded it (first-run) can land on a
      brief blank stage before the previous panel restores.
- [ ] `UI_DESIGN_REFERENCE.md` §6.8 still describes a radial-launcher mobile
      concept — superseded by this shell; reconcile when the brief is next
      revised.
- [ ] Reconcile the `--panel` vs `--background` near-identity in light mode so
      the content-panel fill is visible on phone.
- [ ] Carry over the open items from the earlier entries (save-button
      semantics, reader vs source wikilinks, real data wiring).
