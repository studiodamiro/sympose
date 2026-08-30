---
title: "Sympose Web Dashboard — UI Design Reference"
created: 2026-08-30
type: design-brief
project: sympose
status: reference
tags:
  - sympose/design
  - dashboard
  - ui-ux
  - design-system
  - claude-design-brief
---

# Sympose Web Dashboard — UI Design Reference

> **Purpose.** A single self-contained brief to feed directly into Claude Design as the
> reference for mocking the Sympose web dashboard. It consolidates every UI/UX decision
> already ratified in the project journal and wiki so the design canvas can be seeded
> without re-reading the whole repo. Where this document and a source doc disagree, the
> **source doc wins** — this is a synthesis, not a new decision.

## How to use this document

1. Read §1–§4 for philosophy and the visual language (non-negotiable).
2. Use §5 as the layout skeleton for the main dashboard artboard.
3. Produce one artboard per screen in §6, in the order listed.
4. Pull mock content from §9 so the mockups read as a real vault, not lorem ipsum.
5. Respect §10 (out of scope) — do not design surfaces that are explicitly deferred.

---

## Source documents (authoritative)

Everything below is derived from these. Cross-reference them for detail; cite them, don't contradict them.

| Ref | Document | What it fixes |
| :-- | :-- | :-- |
| Journal index | [`docs/PROJECT_JOURNAL.md`](./PROJECT_JOURNAL.md) | Master ADR index; entry points for all decisions |
| **ADR-051 / 052 / 053** | [`docs/journal/2026-08/2026-08-29_web_dashboard_ui_ux_and_3d_knowledge_nebula.md`](./journal/2026-08/2026-08-29_web_dashboard_ui_ux_and_3d_knowledge_nebula.md) | Flat design philosophy, 2D/3D nebula, shadcn theme customizer, desktop launchers |
| **Dashboard spec (wiki)** | [`docs/wiki/architecture/dashboard-and-vault-explorer.md`](./wiki/architecture/dashboard-and-vault-explorer.md) | Full functional module spec, layout diagram, API contracts, performance budget |
| ADR-047 | [`docs/journal/2026-08/2026-08-29_sovereign_packaging_and_cli_design_system.md`](./journal/2026-08/2026-08-29_sovereign_packaging_and_cli_design_system.md) | CLI design system — semantic color tokens the web palette should echo for brand continuity |
| ADR-051 (again) | same as above | shadcn styles (`nova / maia / sera / new-york`), icon packs, curated presets |
| ADR-064 (Proposed) | [`docs/journal/2026-08/2026-08-30_dashboard_api_security_design_gap_and_auth_plan.md`](./journal/2026-08/2026-08-30_dashboard_api_security_design_gap_and_auth_plan.md) | Password gate + self-signed TLS — **not yet implemented**; design a login screen only as a stub (§6.6) |
| Triad / personas | [`README.md`](../README.md) | Persona roster, action-tag catalog, product framing |

---

## 1. Product context (one paragraph)

**Sympose** ("a symposium — a forum of gathering experts") is a zero-bloat, local-first
multi-agent hub. Multiple AI personas (cloud + local models) share a sandboxed Obsidian
vault and an autonomous memory layer. It runs as a macOS Terminal REPL and a Slack bot
today; the web dashboard is the third surface. The dashboard is served by a native
FastAPI process on `http://localhost:8000` (no Node runtime for end users) and is
launched frameless via a lightweight native app wrapper (Spotlight / Start Menu / Dock).
It is a **single-user, personal-LAN tool** — not a SaaS product, not a team console.
Primary target is the desktop window (≥1280px, graceful to ≥1024px); a portrait **mobile**
layout is also in scope (§6.8) as a responsive view of the same surface.

The dashboard has four jobs, all on one screen:
- Talk to the agents (streaming multi-agent chat).
- See the vault as a living idea-web (2D/3D ambient knowledge nebula).
- Browse and edit vault notes without opening Obsidian (standalone vault explorer).
- Re-theme the whole UI live from **Settings → Appearance** (no persistent theme bar).

---

## 2. Design philosophy — non-negotiable

From ADR-051, stated as an explicit rejection of common AI-app aesthetics.

**Reject:**
- Purple/blue neon glows, glowing borders, laser accents.
- Heavy glassmorphism, frosted-everything, thick backdrop blur as decoration.
- Low-contrast "moody" text (grey-on-grey).
- Sluggish, Electron-heavy visual weight.

**Adopt — "Flat Sovereign Craft":**
- **Flat matte surfaces.** Cards are solid fills, not gradients.
- **Crisp 1px borders.** `border: 1px solid var(--border)` is the primary separator, not shadow.
- **Swiss / Bauhaus / editorial typography.** Strong type hierarchy, generous leading, real
  headings. Think a well-set technical journal, not a dashboard template.
- **Pristine legibility.** WCAG AA minimum for all text; AAA for body copy where possible.
- **Instant light/dark.** Both modes are first-class and equally finished — neither is an afterthought.
- **Geometry over effects.** Structure communicated by alignment, spacing, and rule lines.
- **Calm motion.** Slow ambient drift in the background; snappy, short transitions in the UI (120–180ms).

"Engine First, Face Second" — the UI is a quiet, precise instrument over a fast engine.

---

## 3. Visual language

### 3.1 Curated theme presets (design all mockups in **Obsidian Matte** by default; also show **Blueprint & Paper**)

From the wiki spec §2 Module B. These are the shipped presets — treat them as the palette source of truth.

| Preset | Mode | Background | Accent / notes | Icon pack |
| :-- | :-- | :-- | :-- | :-- |
| **Obsidian Matte** *(default)* | Dark | Deep graphite `#0A0F1D` | Subtle slate link strings; node bubbles in cyan / mint / purple; `0rem` radius | Phosphor |
| **Blueprint & Paper** | Light | Warm parchment `#F9F7F1` | Drafting-cobalt accents; fine ink-line links | Lucide |
| **Nordic Spruce** | Balanced (dark) | Dark spruce `#1A2421` | Moss green `#7EC7A2`; birch accents | — |
| **Swiss Grid** | Minimal | High-contrast monochrome | Bauhaus primary accents (red/blue/yellow), sharp borders | — |
| **Custom Studio** | either | user-picked | Live pickers for background, text, borders, node fills, link strings | — |

### 3.2 Semantic tokens (mirror the CLI design system, ADR-047, for cross-surface brand continuity)

The terminal UI already ships this palette. The web dashboard should feel like the same product.

| Role | CLI treatment (ADR-047) | Web token intent |
| :-- | :-- | :-- |
| Brand / primary headers | bold cyan | `--brand` — cyan family, used sparingly for primary headings & active nav |
| Category subheaders | bold white | `--fg-strong` |
| Interactive handles / code chips | bold yellow on `grey11` | `--chip-bg` / `--chip-fg` — `@handle` pills, inline code, kbd |
| Success / active | bold green | `--ok` |
| Error / missing | bold red | `--danger` |
| Vault paths / entities | magenta | `--entity` — file paths, `[[Wikilinks]]`, note titles |
| Latency / metadata | dim cyan / dim white | `--fg-muted` — timestamps, token counts, ms readouts |

Define the full set as CSS custom properties on `:root` (light) and override under the dark preset.
Every mockup must be legible in both without re-picking colors by hand.

### 3.3 Typography

- **Display / headings:** a grotesque or neo-grotesque sans with real weight range
  (e.g. Inter Tight, Söhne, Aktiv Grotesk, Helvetica Now — pick one and commit).
  Tight tracking on large sizes. Sentence case, not ALL CAPS, except small labels.
- **Body / UI:** the same family or a highly legible sans at 14–15px base, 1.6 line-height.
- **Mono:** for code blocks, file paths, `ms` readouts, YAML frontmatter, kbd chips
  (e.g. JetBrains Mono, Berkeley Mono, IBM Plex Mono).
- **Markdown reader:** editorial measure — ~68–74ch max line length, clear `h1–h4` scale,
  GitHub-flavored markdown, syntax-highlighted code, math formulas.

### 3.4 Shape, border, elevation

- **Corner radius is a live control:** `0rem` (sharp flat — Obsidian Matte default) → `0.75rem`.
  Design the default at `0rem`; show one artboard at `0.5rem` to prove the system flexes.
- **Borders:** 1px solid `--border`; slightly dimmer `--border-subtle` for internal rules.
- **Elevation:** minimal. Panels sit on the background by fill + border. Reserve a single
  soft shadow tier only for true overlays (theme drawer, command palette, modals).

### 3.5 Iconography

Interchangeable at runtime from **Settings → Appearance** (§6.4): **Lucide**, **Phosphor**,
**Hugeicons**. Design with Phosphor (Obsidian Matte's default). Keep icon usage structural
and sparse — line weight consistent with the 1px border language.

---

## 4. Motion & the two interaction states

The ambient knowledge nebula is a **persistent full-bleed background layer** behind the whole
app. It has two states (ADR-051, wiki spec §1):

| | **Explore Mode** | **Focus / Chat Mode** |
| :-- | :-- | :-- |
| Background | 100% sharp, full color | dimmed ~75%, slow ambient drift |
| Pointer | `pointer-events: auto` — orbit / pan / zoom / click nodes | `pointer-events: none` — no click hijack |
| Foreground panels | collapsed to edges / minimized | expanded with matte backing, in front |
| Use | "show me my vault" | "let me work / chat" |
| Transition | 300–400ms cross-fade + panel slide | same, reversed |

Node/link motion: gentle particle pulse along links; a referenced note **pulses its node cluster**
when an agent mentions it in chat ("Active Nebula Synergy"). Physics visibly settles and stops
after ~3s (it is not perpetually jittering).

The **2D/3D mode switch** and the **Explore ⇄ Focus** toggle are reached from Settings → Appearance
(§6.4), plus the optional panel-corner quick-toggle noted in §5 — not from a top bar.

---

## 5. Main dashboard layout (primary artboard)

**No persistent global chrome bar.** The window is just the working panels — the frameless
app wrapper (Spotlight / Dock) is the only chrome. All appearance controls that a theme bar
would have carried (preset, shadcn style, corner radius, light/dark, 2D/3D mode) live inside
the **Settings** panel — see §6.4. Light/dark and the 2D/3D mode switch may *also* appear as
one small, quiet quick-toggle docked to a panel corner, but nothing spans the full width and
nothing sits permanently across the top.

Three-column shell, derived from the wiki spec §1 diagram (theme-bar row removed):

```
┌──────────────────────┬───────────────────────────────────────┬─────────────────────────┐
│  LEFT  ▸ VAULT       │  CENTER ▸ MULTI-AGENT CHAT & TIMELINE  │  RIGHT ▸ NEBULA CONTROLS │
│  EXPLORER            │                                       │  (over the ambient bg)   │
│                      │  [@samantha] Formulating auth plan…   │                          │
│  ▾ Projects/         │  [@grace]   Inverted index verified   │  🔍 Search files…        │
│    ▾ Sympose/        │             (<2ms)                    │  ▸ Filters   ▾           │
│      Architecture.md │  > 📝 Note saved to Vault             │  ▸ Groups    ▾           │
│      Roadmap.md      │  ─────────────────────────────────    │  ▸ Display   ▾           │
│  ▾ Daily/            │  [ Ask @grace, @samantha, @anais…  ▷] │  ▸ Forces    ▾           │
│    ▸ 2026-08-29.md   │                                       │  ─────────────           │
│  ▾ Thoughts/         │                                       │  ⚙ Settings   ☀/🌙  2D|3D │
└──────────────────────┴───────────────────────────────────────┴─────────────────────────┘
```

- **Left panel** (~260–320px): directory tree. Collapsible. Respects agent domain sandboxes;
  hides `.obsidian`, `.git`, `Attachments`, `.trash`.
- **Center** is the anchor: streaming chat timeline + composer. In Focus Mode it widens and
  gets a matte backing; in Explore Mode it can minimize to a docked bar.
- **Right panel** (~300–340px): the Obsidian-parity graph control stack, floating over the
  ambient background. Collapsible to icon rail. A **Settings** entry lives at its foot,
  alongside the optional light/dark and 2D/3D quick-toggles.
- Panels are resizable; remember width per session (localStorage is fine for that).

---

## 6. Screens / artboards to produce

Produce these as separate artboards on the canvas, in this order. All in Obsidian Matte / dark unless noted.

### 6.1 Dashboard — Explore Mode
Full 3-column shell, 3D nebula sharp and interactive behind, right-panel controls expanded,
a node hover-tooltip showing note title + tag + link count. Chat docked/minimized.

### 6.2 Dashboard — Focus / Chat Mode
Same shell, background dimmed with drift, center chat expanded with matte backing, an
in-progress streaming reply from `@samantha`, one visible action badge (`📝 Note saved`),
persona selector visible. This is the "hero" screen — make it the most finished.

### 6.3 Ambient Knowledge Nebula — control panels (detail)
The right-side control stack fully expanded, 1:1 with Obsidian's graph view (wiki spec §2 Module A):
- **Filters:** search input; toggles for `Tags`, `Attachments`, `Existing files only`, `Orphans`.
- **Groups:** color-coding rules — add rule rows like `path:Projects → cyan`, `tag:#architecture → mint`, `persona:@grace → amber`.
- **Display:** `Arrows` toggle; `Text fade threshold` slider; `Node size` slider; `Link thickness` slider; `Animate / pulse` trigger.
- **Forces:** `Center force`, `Repel force`, `Link force`, `Link distance` sliders.
Show both a **2D planar** variant and a **3D orbit** variant of the canvas itself.

### 6.4 Settings panel — Appearance section (this replaces the old theme bar)
Opened from the **Settings** entry (foot of the right panel / an app menu item), Settings
renders as its own left-hand contextual panel — same width and matte treatment as the vault
tree. It has grouped sections; the first is **Appearance**, which absorbs everything the
persistent theme bar used to hold (wiki spec §2 Module B):
- Preset gallery (the five presets in §3.1 as selectable swatched cards).
- `Style` selector: `nova / maia / sera / new-york`.
- `Icon pack` selector: `Lucide / Phosphor / Hugeicons` with a live icon preview row.
- `Corner radius` slider `0rem → 0.75rem`.
- Light / Dark toggle.
- **Nebula mode:** `2D | 3D` segmented control and the `Explore | Focus` toggle.
- **Custom Studio:** color pickers for background, text, borders, node fills, link strings,
  folder-domain colors.
- Everything applies live (show a "preview updates instantly" affordance, no Save button needed).

Also show the other Settings groups so the panel reads as complete: **Shared Memory Compactor**
(capacity meter `18/25 lines · 72%`, "Compact memory" button), **Runtime Parameters** (`Context
window` slider `1K–8K`, `Streaming responses` toggle, `Deterministic output` toggle), **Vault
Parameters** (`Daily notes directory`, `Daily notes format` inputs).

### 6.5 Vault Explorer + Markdown reader/editor
Left tree + a wide reading pane (wiki spec §2 Module C):
- Rendered markdown (editorial type, code highlighting, a math formula).
- Clickable `[[Wikilink]]` — hovering one shows it will "open note / center nebula".
- YAML frontmatter inspector + tag editor at the top of the note.
- **Backlink & Mention inspector** side panel: incoming links with exact line numbers and
  verbatim surrounding context lines (powered by the inverted index).
- A **Daily Reflections calendar** view mapping `Daily/YYYY/mm-Month/YYYY-MM-DD.md` to dates.
- Show a read state and an inline-edit state.

### 6.6 Login gate (stub only — ADR-064 is *Proposed*, not implemented)
A single minimal screen: Sympose wordmark, one password field, one "Unlock" button, a small
line noting the one-time self-signed-certificate browser warning is expected. Flat, centered,
no marketing. Do **not** design account creation, SSO, multi-user, or password-reset flows —
none exist and none are planned.

### 6.7 States pass
For chat, nebula, and vault explorer, show: **empty** (fresh vault / no messages),
**loading** (skeletons — no spinners as the primary device), **error** (e.g. model
unreachable, note failed to save), and **offline/local-model** indicator.

### 6.8 Mobile (portrait, ~390×844)

The mobile layout does **not** shrink the three-panel desktop shell. It replaces persistent
navigation with a **bottom-anchored radial launcher** and opens each area as its own
full-screen view. Assume a responsive web view inside the same frameless wrapper, not a
separate native app. Produce these mobile artboards:

- **6.8a — Radial launcher (home / idle).** The Sympose hex mark docked bottom-centre on an
  otherwise empty matte canvas. Tapping it fans a short **arc of icons** up-and-right from the
  mark: Vault, Chat/AI (sparkle), Settings (gear), Code, Daily (clock), Writing (ink-pot),
  etc. Show a 3–4 frame progressive reveal (mark only → 2 icons → full arc). Motion is a
  quick spring, ~200ms staggered.
- **6.8b — Radial launcher (agent switch).** Same gesture, but the arc is **agent avatars**
  (Samantha, Grace, Anaïs) with a small green "online / on-device" dot on the active one.
- **6.8c — Chat (full screen).** Back chevron + agent avatar + name in the header (or the
  conversation title when opened from history); user message right-aligned in a filled
  bubble; agent reply as plain flowing text; `0.68 TTFT` chip; thumbs-up + emoji react;
  composer pinned to the bottom safe-area with `+` attach and a `3.7 Flash` model chip +
  agent avatar.
- **6.8d — Agent home (conversation list).** Header (back + avatar + name + gear); `PINNED:`
  then `RECENT:` conversation lists as plain tappable rows; composer docked at bottom.
- **6.8e — Vault (list).** Header (back + vault icon + "Vault" + gear); `PINNED:` Projects /
  Code / Daily; `RECENT:` the vault folders (Drawings, General, Limbo, Movies, People,
  Quotes, Reading, Recipes, Templates, Writing) as icon rows; `Search Vault` field pinned
  to the bottom. Also show the **expanded-tree** state (nested folders + `.md` leaves, e.g.
  `Daily / 2023 / 07-July / 2023-07-04.md`).
- **6.8f — Note reader (full screen).** Back chevron + note title + breadcrumb
  (`Projects / Design Assets`); the **contextual formatting toolbar** (B I U S · bullet /
  numbered list · code / quote · send) directly under the header — present only here, never
  global; frontmatter card (`TITLE / DATE / AGENT / TAGS`); body with inline `[[wikilinks]]`
  in the brand accent and a blockquote; `LINKS:` chips at the foot.
- **6.8g — Settings (full screen).** Header (back + "Settings"); the same grouped sections as
  §6.4 stacked as cards: Shared Memory Compactor (meter + button), Runtime Parameters
  (sliders + toggles), Vault Parameters (inputs). Appearance is one of these cards on mobile
  too — there is still no bar.

---

## 7. Multi-agent chat — component detail (wiki spec §2 Module D)

- **Streaming timeline:** token-by-token via SSE. Show a mid-stream message with a caret.
- **Message identity:** each turn led by a colored `@handle` pill + persona icon + model chip
  + timestamp/latency in `--fg-muted`. Distinguish user vs persona turns by alignment/fill,
  not by chat-bubble kitsch.
- **Persona selector / drawer:** switch active persona or `@mention` several. See §8.
- **Visual action-event badges** — inline, below the message that produced them:

| Action tag | Badge | Affordance |
| :-- | :-- | :-- |
| `[WRITE_NOTE]` / `[APPEND_NOTE]` | 📝 "Note saved — `Projects/…`" | click → open in editor (6.5) |
| `[DAILY_NOTE]` | 📓 "Reflection added" + frontmatter-tag-sync chip | click → open today's daily note |
| `[SEARCH]` | 🔎 "Web search: <query>" + citation count | expand → list retrieved sources |
| `[SPAWN_WORKER]` | ⚙ "Sub-agent: <task>" progress row | expand → tool execution log drawer |
| `[REACT]` | animated emoji on the bubble | — |
| `[CONFIG_SET]` | 🎛 "config.yaml updated: <key>" | — |
| `[CREATE_PERSONA]` / `[DELETE_PERSONA]` | 🧬 / 🗄 persona lifecycle chip | — |

- **Composer:** single flat input, `Ask @grace, @samantha, @anais…` placeholder, `@` autocomplete,
  send on ⌘/Ctrl-Enter. No formatting toolbar clutter.

---

## 8. Persona visual identity

Roster (from `profiles/*.yaml` + README). Seeded clean-slate with **Samantha** only; others are
example specialists spawned via `[CREATE_PERSONA]`. Give each a stable accent color + the icon
shown; keep them distinct but within the preset palette.

| Handle | Name | Title | Model tier | Icon | Suggested accent (Obsidian Matte) |
| :-- | :-- | :-- | :-- | :-- | :-- |
| `@samantha` | Samantha | Polymath Strategic Master Orchestrator | cloud (Gemini) | 🧠 `:brain:` | cyan `--brand` |
| `@grace` | Grace Hopper | Surgical Software & Systems Engineer | cloud (Gemini / Claude) | 💻 `:computer:` | mint / green |
| `@anais` | Anaïs Nin | Literary Sensualist, Intimate Diarist & Confidante | **local** (Ollama) | 🌹 `:rose:` | magenta / rose |

- Mark **local** personas with a small "on-device / private" indicator (Anaïs is air-gapped).
- Model chip shows the backend family (e.g. `gemini-3.6-flash`, `ollama:qwen2.5-14b`), muted.

---

## 9. Mock content (use this, not lorem ipsum)

**Vault tree:**
```
Projects/
  Sympose/
    Architecture.md
    Roadmap.md
    Dashboard-UI.md
General/
Thoughts/
  creativity.md
Daily/
  2026/08-August/
    2026-08-29.md
    2026-08-30.md
Templates/
```

**`GET /api/vault/graph`** →
```json
{
  "nodes": [
    { "id": "Architecture",  "label": "Architecture",  "folder": "Projects/Sympose", "tags": ["architecture","adr"], "val": 12 },
    { "id": "OAuth",         "label": "OAuth",          "folder": "Projects/Sympose", "tags": ["security"],           "val": 4  },
    { "id": "FastAPI",       "label": "FastAPI",        "folder": "Projects/Sympose", "tags": ["backend"],            "val": 7  },
    { "id": "2026-08-29",    "label": "2026-08-29",     "folder": "Daily/2026/08-August", "tags": ["jour"],           "val": 3  }
  ],
  "links": [
    { "source": "Architecture", "target": "OAuth" },
    { "source": "Architecture", "target": "FastAPI" }
  ]
}
```

**Chat transcript (for 6.2):**
```
[@samantha]  Formulating the auth plan — shared-password guard plus an in-process
             self-signed cert, no manual install. Grace, can you confirm the index latency?
[@grace]     Inverted index verified — backlink lookup at <2ms across the current vault.
             > 📝 Note saved to Vault — Projects/Sympose/Architecture.md
[you]        Good. Draft the ADR and link it from the journal.
[@samantha]  ▍(streaming…)
```

**API surface** (for realism in any "connection / status" UI — wiki spec §3, current `server.py`):
`GET /health` · `GET /api/personas` · `GET /api/config` · `GET /api/vault/graph` ·
`GET /api/vault/cloud` · `GET /api/vault/note?path=` · `POST /api/vault/note` ·
`GET /api/vault/backlinks?note=` · `POST /api/chat/message` · `GET /api/chat/stream?session_id=`
· served on `http://localhost:8000`.

---

## 10. Out of scope — do not design these

- **Authentication beyond the §6.6 stub.** ADR-064 (password gate + TLS) is *Proposed*, not
  built. No signup, SSO, multi-user, roles, org/team, billing, or password-reset UI.
- **Slack UI.** Slack is a separate surface with its own native chrome; it never routes through
  this dashboard.
- **Onboarding wizards, tours, marketing pages, settings sprawl.** Runtime config is a thin
  `config.yaml` view; the Appearance section (§6.4) is the only "settings" surface that
  matters visually.
- **Obsidian itself.** The vault explorer replaces the *need* to open Obsidian; it does not
  reimplement Obsidian's full editor.

---

## 11. Performance constraints that shape the visuals

From ADR-052 / wiki spec §4 — these bound what the design may ask for:

- Nebula renders up to ~20,000 nodes in **one GPU draw call** (instanced). Node styling must
  work as instanced geometry — avoid per-node DOM, per-node drop-shadows, or effects that
  can't batch.
- Physics **sleeps after ~3s**. No design that depends on perpetual motion.
- Total RAM budget ~100–165MB (Python + browser + WebGL). Keep the asset/typography footprint lean.
- Target 60 FPS on a dual-core / 4GB machine. Ambient motion must stay cheap.
- Sub-5ms API responses — UI should feel instant; loading states are the exception, not the rule.

---

## 12. Artboard checklist

- [ ] 6.1 Dashboard — Explore Mode (3D nebula sharp), no top bar
- [ ] 6.2 Dashboard — Focus / Chat Mode (hero, streaming reply + action badge), no top bar
- [ ] 6.3 Nebula control panels — Filters / Groups / Display / Forces (2D + 3D canvas variants)
- [ ] 6.4 Settings panel — Appearance section + the other Settings groups (replaces the theme bar)
- [ ] 6.5 Vault Explorer + markdown reader + backlink inspector + daily calendar (read + edit states)
- [ ] 6.6 Login gate stub (ADR-064, minimal)
- [ ] 6.7 States pass — empty / loading (skeleton) / error / local-model, for chat + nebula + explorer
- [ ] 6.8a–g Mobile — radial launcher (home + agent-switch), chat, agent home, vault (list + tree), note reader, settings
- [ ] Palette proof — one screen rendered in Blueprint & Paper (light) + one at `0.5rem` radius
