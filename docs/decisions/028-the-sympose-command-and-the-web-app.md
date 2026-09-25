# 028 — One `sympose` command with `cli` and `web`, and the browser app is the "web app"

> **Status: Proposed.** Built. Amends the name used in ADRs 004, 005, 010, 011 and later ("the dashboard"), which keep their wording as a record of what was decided then. Nothing about the API or the chat engine changes.

## Context

There were two ways in and neither had a name you could type. The terminal chat started with `python -m sympose.cli`, the browser app's backend with `python -m sympose.main` and its interface with `npm run dev` in `ui/`, and no `sympose` command existed at all (`pyproject.toml` defines no console script). The word for the browser app, "dashboard", was also wrong: it is where you browse, edit, search and explore your notes and will host chat, and nothing in it is a dashboard. And the built app is committed in `sympose/webui/` but nothing serves it and the package data does not include it, so a normal install (no Node) could not open it at all.

## Decision

**The name.** The browser app is the **web app** (the command is `web`). VISION already calls the ways in "channels", and this names the channel by how you reach it: `cli`, `web`, later `slack`. "UI" was rejected as a name: the terminal chat is a UI too, and the chat panel to come is a UI inside the web app. The word "dashboard" is replaced in the user-facing places (the README, VISION, the reference notes Sam quotes, messages the app shows, code comments). Old records keep it, and the reference note says the web app is "also called the dashboard", so a person or a persona using the old word still lands on it (as with persona, agent and profile, ADR 024).

**The command.** `sympose` is a console script with two subcommands:

- `sympose cli`: the terminal chat, what `python -m sympose.cli` did.
- `sympose web`: the API and the built web app together, from one process, on `http://127.0.0.1:8000` (the port is `PORT` in `.env`, or `--port`). It prints the address and does not open a browser. It listens on the local machine only, as the backend always has (no TLS, no auth): there is no `--host`. No auto-reload.
- `sympose` alone, or with `-h`, lists them. `python -m sympose.cli` and `python -m sympose.main` keep working; `npm run dev` in `ui/` is still how the app itself is developed, with its own reload, against a `python -m sympose.main` backend.

**Serving the built app.** `sympose web` serves the files in `sympose/webui/`, and any path that is not a file and not the API (`/api/...`, `/health`, `/docs`, `/openapi.json`) gets `index.html`, since the app has routes of its own in the browser. An unknown `/api/...` path stays a 404 and is never answered with the page. A file is served only from inside that folder (a path that climbs out of it is not). If the folder is missing (a checkout that never built the app) the command says so and exits with an error instead of starting an API nobody can see. The folder is added to the package data so an install ships it. `HEAD` works like `GET`, and a missing file under `/assets/` is a 404 (a cached page from before a rebuild would otherwise be sent HTML where it asked for a script, which a browser refuses).

**Only this machine's own names may address it.** `sympose web` refuses any request whose `Host` header is not `127.0.0.1` or `localhost` (with or without a port). The API can read, change and delete notes with no login, and a web page you visit could otherwise point its own domain name at `127.0.0.1` (DNS rebinding) and reach it as if it were the same site; its `Host` would then be its own domain, which this refuses. Checked for real: `Host: evil.example` and `localhost.evil.example` got a 400, `localhost:8123` and `127.0.0.1:8123` a 200. Not covered: `python -m sympose.main` (the development server the app's own `npm run dev` talks to) has never had this check and still does not, since a Vite proxy and the tests use their own Host values; if that server is ever run for real use it needs the same.

## Checked

Run for real on a spare port: the page, an in-app route, the 1.3 MB script, `/health`, `/api/vaults`, `/docs` all answered as they should, an unknown `/api/...` path was a 404 with JSON, and a path that climbs out of the folder returned the page and not the file. Asked "how do I start the web app?" and "how do I start the dashboard?", Samantha answered `sympose web` both times (two runs each). One old-name question cannot be answered by the library: a lone "what is the dashboard?" finds nothing, because the strict search needs two of a message's words in a note's own text (ADR 019); it is recorded as a known gap in the library eval, and searching by meaning (ADR 027) would cover it.

## Consequences

- One word to remember for each way in, and a normal install (pipx, no Node) can open the web app.
- The API server and the built app are one process on one port, so there is no proxy and no second terminal; the two-terminal setup remains for people working on the app itself.
- Two visible messages in the app said "dashboard API"; they say "API" now, which needs the app rebuilt (`npm run build`), so `sympose/webui/` changes with this.
- Old ADRs and the checklist still say "dashboard".

## Not built yet

Opening the browser for you (`--open`), a `sympose slack`, serving the web app from `python -m sympose.main` too, and a check that the committed build is up to date with `ui/src`.
