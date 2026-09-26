# Sympose

Sympose is a cheap, low-round-trip AI companion for direct dialogue with an
Obsidian vault: a personal agent hub where a persona (Samantha, by default)
talks to the user in tandem with their vault instead of through expensive
multi-call orchestration.

## Current status

What works today:

- **Terminal chat** (`sympose cli`): talk to a persona (Samantha by default) about your vault. Replies are grounded in real notes, found by meaning when a local embedding model is available and by keywords otherwise, and the CLI can show which notes grounded each one. It also has saved sessions, recaps of earlier conversations, a context meter, and a model picker (a local Ollama model by default; Gemini and OpenRouter are opt-in).
- **Web app** (`sympose web`): vault browsing, the markdown editor, note and folder create, rename and delete, trash recovery, full-text search, and the Knowledge Nebula graph.

Not built yet: chat inside the web app (its chat panel is a mock and the backend has no chat route), Slack, tool-calling, skills, durable memory and compaction, and a multi-persona roster. See `docs/VISION.md` for what's next and why.

## Project layout

- `sympose/` — the Python package: the chat engine and terminal chat (`engine/`, `cli/`), and the FastAPI backend for the web app (vault browsing, note editing, trash recovery, full-text search, the Knowledge Nebula graph API).
- `ui/` — the React/TypeScript web app (Vite): vault tree, markdown editor, the bin, Knowledge Nebula 2D/3D graph, and a chat panel that is a mock with no backend behind it yet. Its build is committed as `sympose/webui/`.
- `profiles/` — one directory per persona (`profiles/<handle>/persona.yaml`,
  plus that persona's soul, memory, and chat sessions). Only Samantha's
  `persona.yaml` and `soul.md` (the shipped default) are committed; any other
  persona is a personal customization and stays local-only, and no persona's
  memory or sessions are ever committed (see `.gitignore`).
- `docs/` — the product vision (`VISION.md`), engineering standards
  (`COLLABORATION_STANDARDS.md`, `CODE_QUALITY_STANDARDS.md`), and
  architecture decision records (`decisions/`).

## Local setup

1. Copy `.env.example` to `.env` and set `VAULT_PATHS` to an
   Obsidian vault on disk. Sympose reads the `.env` in the folder you run it from (and only that file).
2. Backend: `pip install -e ".[dev]"` from the repo root.
3. Frontend: `npm install` from `ui/`.
4. For chat: run [Ollama](https://ollama.com) and pull the default chat model (`ollama pull gemma2:9b`). For search by meaning also `ollama pull nomic-embed-text`; without it, search falls back to keywords.

## Running it

- Terminal chat: `sympose cli`.
- Health check: `sympose doctor` reports what is wrong with the installation (a persona folder that is not lower case, an unreadable persona or settings file, a setting of the wrong kind); `sympose doctor --fix` corrects what belongs to Sympose and never touches your notes.
- Web app: `sympose web` — the API and the built app together on
  `127.0.0.1:8000` (`--port` or `PORT` in `.env` changes it), this machine
  only, no auth yet.
- Working on the app itself: `python -m sympose.main` (repo root) for the
  API, and `npm run dev` (from `ui/`) on `localhost:5173`.

Checks: `pytest` and `ruff check .` from the repo root; `npm run test`, `npm run lint`, `npm run typecheck` and `npm run build` from `ui/` (the build writes into `sympose/webui/`).

## Standards and decisions

- `docs/VISION.md` — what Sympose is building toward beyond the
  web app: search, multi-vault, the chat engine and its channels
  (Slack, CLI, web), persona design, and what's deliberately out
  of scope.
- `docs/COLLABORATION_STANDARDS.md` — tone, pacing, and working practices.
- `docs/CODE_QUALITY_STANDARDS.md` — the engineering process: tooling,
  review tiers, verification discipline, commit hygiene.
- `docs/decisions/` — architecture decision records; see its `README.md`
  for the index.
- `CONTRIBUTING.md` — repository hygiene (commit authorship, no AI
  tooling artifacts committed).
