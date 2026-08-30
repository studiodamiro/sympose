# Sympose Web Dashboard (`ui/`)

The third Sympose surface — a local-first dashboard served by the FastAPI process in
[`sympose/server.py`](../sympose/server.py) on `http://localhost:8000`.

Design source of truth: [`docs/UI_DESIGN_REFERENCE.md`](../docs/UI_DESIGN_REFERENCE.md)
("Flat Sovereign Craft" — flat matte surfaces, crisp 1px borders, `0rem` radius by
default, instant light/dark, no neon).

## Current state — Vite + React + TypeScript + shadcn/ui

Scaffolded with the `shadcn` CLI (`init --template vite --preset b4Xd5yqcRW`):

- **Vite 8** + **React 19** + **TypeScript 6**, `@` aliased to `src/`
- **Tailwind CSS v4** via `@tailwindcss/vite` (no `tailwind.config` — config lives in
  `src/index.css`)
- **shadcn/ui** (`base-maia` style, `hugeicons` icon library); `components.json`
  drives `npx shadcn@latest add <component>`
- Theme preset baked into [`src/index.css`](src/index.css) — `zinc` base color,
  Inter + Merriweather (`@fontsource-variable`), light/dark via a `.dark` class
- [`src/components/theme-provider.tsx`](src/components/theme-provider.tsx) —
  system/light/dark with `localStorage` persistence; press `d` to toggle

```
ui/
├── index.html                    # Vite entry
├── src/
│   ├── main.tsx                   # ThemeProvider + TooltipProvider + App mount
│   ├── App.tsx                    # react-router: /, /components, /menu, /shell
│   ├── index.css                  # Tailwind v4 config + theme tokens
│   ├── components/
│   │   ├── theme-provider.tsx
│   │   ├── logo.tsx
│   │   ├── ui/                    # shadcn primitives (base-maia) — 34 added
│   │   └── sympose/              # Sympose-specific molecules (see below)
│   ├── routes/
│   │   ├── root-layout.tsx        # top-nav chrome for /, /components, /menu
│   │   ├── dashboard-placeholder.tsx
│   │   ├── components-gallery.tsx # the /components page
│   │   ├── menu-showcase.tsx      # the /menu page (MainMenu deep-dive)
│   │   ├── app-shell.tsx          # the /shell page — MainMenu as a real shell
│   │   └── gallery-data.ts        # mock vault + theme presets
│   └── lib/
│       ├── utils.ts              # cn()
│       ├── personas.ts           # persona roster (§8): handle, accent, icon
│       ├── vault-folders.ts      # top-level vault folders + their icons
│       ├── cookies.ts            # get/set cookie helpers (UI prefs — §5)
│       └── use-resizable.ts      # drag/keyboard resize hook (+ cookie persist)
├── components.json
├── vite.config.ts                # @ alias + dev proxy to :8000
└── legacy/                        # pre-Vite vanilla shell (see below)
```

> The theme preset ships `--radius: 0.625rem` and its own palette, which do **not**
> yet match the "Flat Sovereign Craft" contract in
> [`docs/UI_DESIGN_REFERENCE.md`](../docs/UI_DESIGN_REFERENCE.md) (`0rem` radius, flat,
> no neon). Reconciling the two is a separate follow-up — the token contract to port
> from is [`legacy/assets/styles.css`](legacy/assets/styles.css).

### Component library — `/components`

`src/components/sympose/` holds the Sympose-specific components, each built on
shadcn principles (`cva` variants, `cn()`, `data-slot` hooks, semantic tokens) —
built by hand only where the shadcn registry has no equivalent. Browse them live
at [`/components`](http://localhost:5173/components) (`src/routes/components-gallery.tsx`).

| Component | Purpose (UI_DESIGN_REFERENCE.md) |
| :-- | :-- |
| `MainMenu` | app-shell sidebar (`/menu`, `/shell`) — one fixed icon axis, drag-resizable right edge (cookie-persisted), snaps collapsed near the minimum; active row fuses into the content panel (§5) |
| `ContentPanel` | the panel that docks flush against `MainMenu` — drag-resizable between ¼ and ½ of the stage, cookie-persisted (§5) |
| `MarkdownPanel` | markdown editor/reader in the `/shell` stage — `bg-panel` fill, mark toolbar (H1/H2 · B/I/U/S · lists · code · quote) + save, read-only frontmatter header, prose + outbound-links footer; drag-resizable, minimum matched to `ContentPanel` (§6.5, §7) — *mock, controls inert* |
| `ChatPanel` | centred chat reading column — transcript scrolls, composer docks at the bottom on the same axis; column caps at a comfortable measure and centres itself in the space it is given (§7) — *mock* |
| `PersonaPill`, `ModelChip` | `@handle` identity + muted backend-model chip with on-device marker (§7–§8) |
| `ChatMessage`, `StreamingCaret` | chat turns by alignment/fill; mid-stream caret; `reaction` slot — a floated line-icon chip straddling the user bubble's edge (§7) |
| `ActionBadge` | inline action-event badges — `[WRITE_NOTE]`, `[SEARCH]`, … (§7) |
| `Composer` | flat `@`-mention input, ⌘/Ctrl-Enter (§7) |
| `VaultTree` | sandbox-aware directory tree; hides `.obsidian` / `.git` / … (§5, Module C) |
| `WikiLink`, `EntityPath` | `[[wikilinks]]` + vault paths in the `--entity` accent (§6.5) |
| `ControlSection` / `ControlRow` | collapsible nebula control groups (§6.3) |
| `SegmentedControl` | `2D \| 3D`, `Explore \| Focus` switches (§6.4) |
| `PresetCard`, `CapacityMeter` | theme-preset cards + memory-compactor meter (§6.4) |
| `Panel` shell, `StatusBar`, `StatusTag`, `MetaText`, `QuietToggle` | matte panel primitives + runtime readouts (§5) |

Semantic accent tokens (`--brand`, `--ok`, `--danger`, `--entity`, `--chip`,
`--fg-strong`, `--fg-muted`) are defined in `src/index.css` on top of the preset
and exposed as Tailwind utilities (`text-brand`, `bg-ok`, `border-danger`, …).

Add more registry primitives with `npx shadcn@latest add <name>`.

### Develop

```bash
cd ui
npm install
npm run dev        # http://localhost:5173, /api /health /docs proxied to :8000
```

Run the FastAPI process alongside it (`sympose --dashboard`, or `./chat.sh
--dashboard`, or `python3 app.py --dashboard`) so the proxied endpoints resolve.

### Build

```bash
npm run build      # -> ui/dist/index.html + ui/dist/assets/ (hashed)
npm run typecheck  # tsc --noEmit
npm run lint       # eslint .
```

`sympose/server.py` serves **`ui/dist/index.html`** at `/` and mounts
`ui/dist/assets/` at `/assets` whenever `ui/dist/` exists, falling back to its
built-in placeholder page otherwise. `dist/` is git-ignored — build before shipping.

### `legacy/`

The pre-Vite hand-authored shell (`index.html` + `assets/styles.css` +
`assets/app.js`) lives in [`legacy/`](legacy/) as migration reference. `styles.css`
is the "Flat Sovereign Craft" palette contract; `server.py` no longer serves any of
it.

## Backend endpoints still needed

The shell is designed around routes that do **not** exist in `server.py` yet:

| Region        | Needs                                                         |
| :------------ | :----------------------------------------------------------- |
| Vault tree    | `GET /api/vault/tree`                                        |
| Markdown edit | `POST /api/vault/note` (only `GET` exists today)             |
| Chat          | `POST /api/chat/message`, `GET /api/chat/stream` (SSE)       |
| Nebula        | `GET /api/vault/graph`, `GET /api/vault/cloud`               |

Implemented today: `GET /health`, `/api/personas`, `/api/config`,
`/api/vault/backlinks`, `/api/vault/note`.

## Not in scope (per design reference §10)

Auth beyond the ADR-064 login stub, Slack UI, onboarding wizards, marketing pages, a
reimplementation of Obsidian's editor.
