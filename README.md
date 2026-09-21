# Sympose

Sympose is a cheap, low-round-trip AI companion for direct dialogue with an
Obsidian vault: a personal agent hub where a persona (Samantha, by default)
talks to the user in tandem with their vault instead of through expensive
multi-call orchestration.

## Current status

A first vault-dashboard backend and frontend were built, then deleted
(2026-09-22) after both turned out to be salvaged from `sympose-legacy`
with far less filtering than intended. Both have since been rebuilt
properly — traced file-by-file and function-by-function down to only
what's actually reachable from the real dashboard shell. Working today:
vault browsing, the markdown editor, note/folder create/rename/delete,
trash recovery (list/restore/purge), full-text search, and the
Knowledge Nebula graph. Still not built: chat/persona dialogue (the
actual "talk to Samantha" feature), Slack status, and a multi-persona
roster — see `docs/VISION.md` for what's next and why.

## Project layout

- `sympose/` — Python backend (FastAPI): vault browsing, note editing,
  trash recovery, full-text search, the Knowledge Nebula graph API.
- `ui/` — React/TypeScript frontend (Vite): vault tree, markdown editor,
  the bin, Knowledge Nebula 2D/3D graph. No chat panel or Slack status
  yet — those still have no backend behind them.
- `profiles/` — persona definitions. Only `samantha.yaml` (the shipped
  default) is committed; any other profile is a personal customization
  and stays local-only (see `.gitignore`).
- `docs/` — the product vision (`VISION.md`), engineering standards
  (`COLLABORATION_STANDARDS.md`, `CODE_QUALITY_STANDARDS.md`), and
  architecture decision records (`decisions/`).

## Local setup

1. Copy `.env.example` to `.env` and set `VAULT_PATHS` to an
   Obsidian vault on disk.
2. Backend: `pip install -e ".[dev]"` from the repo root.
3. Frontend: `npm install` from `ui/`.

## Running it

- Backend: `python -m sympose.main` (repo root) — serves on
  `127.0.0.1:8000`, local dev only, no auth yet.
- Frontend: `npm run dev` (from `ui/`) — serves on `localhost:5173`.

See `CLAUDE.md`'s Primary Commands section for the full command list.

## Standards and decisions

- `docs/VISION.md` — what Sympose is building toward beyond the
  dashboard: search, multi-vault, the chat engine and its channels
  (Slack, CLI, dashboard), persona design, and what's deliberately out
  of scope.
- `docs/COLLABORATION_STANDARDS.md` — tone, pacing, and working practices.
- `docs/CODE_QUALITY_STANDARDS.md` — the engineering process: tooling,
  review tiers, verification discipline, commit hygiene.
- `docs/decisions/` — architecture decision records; see its `README.md`
  for the index.
- `CONTRIBUTING.md` — repository hygiene (commit authorship, no AI
  tooling artifacts committed).
