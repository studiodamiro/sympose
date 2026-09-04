# Sympose Web Dashboard (`ui/`)

The third Sympose surface — a local-first dashboard served by the FastAPI process in
[`sympose/server.py`](../sympose/server.py) on `http://localhost:8000`.

Design source of truth: [`docs/wiki/reference/ui-design-reference.md`](../docs/wiki/reference/ui-design-reference.md)
("Flat Sovereign Craft" — flat matte surfaces, crisp 1px borders, `0rem` radius by
default, instant light/dark, no neon).

## Current state — vanilla scaffold

There is **no build step yet**. The dashboard is a hand-authored static shell:

```
ui/
├── index.html          # three-column shell placeholder
├── assets/
│   ├── styles.css      # "Flat Sovereign Craft" design tokens + layout
│   └── app.js          # wires the status bar to GET /health
└── README.md
```

`sympose/server.py` serves `ui/index.html` at `/` and mounts `ui/assets/` at
`/assets`. Only the runtime status bar talks to a real endpoint (`/health`); the
tree, chat, and nebula regions are static placeholders labelled with the endpoint
each one still needs.

Run it:

```bash
sympose --dashboard        # or: ./chat.sh --dashboard  /  python3 app.py --dashboard
open http://localhost:8000
```

## Target stack — Vite + React + TypeScript

Chosen to match the design brief (shadcn/ui components, `@react-three/fiber` for the
WebGL knowledge nebula, SSE streaming chat). Node is **not** installed on this
machine — install Node 20+ first, then scaffold here:

```bash
cd ui
npm create vite@latest . -- --template react-ts
npm install
npm run dev                # dev server on :5173, already CORS-whitelisted in server.py
```

Build output must land at **`ui/dist/index.html`** with hashed assets under
`ui/dist/assets/` — `server.py` already prefers `ui/dist/` over this scaffold when it
exists, and mounts `ui/dist/assets/`. Migrate the tokens in `assets/styles.css` into
the React app's global stylesheet; they are the palette contract.

For local development, proxy API calls to the FastAPI process (add to
`vite.config.ts`):

```ts
server: {
  proxy: {
    "/api": "http://localhost:8000",
    "/health": "http://localhost:8000",
    "/docs": "http://localhost:8000",
  },
},
```

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
