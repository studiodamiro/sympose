---
title: "ADR-079 — Prebuilt Dashboard Bundle Shipped in the Package"
created: 2026-09-09
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - packaging
---

# ADR-079 — Prebuilt Dashboard Bundle Shipped in the Package

- **Status:** Accepted — implemented 2026-09-09.
- **Date:** 2026-09-09
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Follows the dashboard slices in
  [2026-09-09 — Dashboard Agent Picker & Persona-Scoped Vault Tree](./2026-09-09_dashboard-agent-picker.md).
- Touches the install paths documented in the
  [README](../../../README.md) Quickstart (`pipx install git+…` and the
  developer clone).

## Context

`sympose/server.py` serves the React dashboard from a built Vite bundle. That
bundle was written to `ui/dist/`, which is git-ignored (`.gitignore` `dist/`),
and no packaging rule shipped `ui/` at all — `MANIFEST.in` and
`[tool.setuptools.package-data]` covered only the Python package, `profiles/`,
`mcp/` and `docs/`.

The consequences:

- `pipx install git+https://github.com/studiodamiro/sympose.git` — the
  **primary documented install** (README Quickstart, Option A) — produced a
  wheel with **no frontend**. `sympose --dashboard` on such an install fell
  through to the API-only placeholder at `/`.
- A developer clone only showed the dashboard if it had run `cd ui && npm run
  build` locally, and every subsequent `git pull` left that build stale with
  no signal. Rebuilding in one checkout (the working repo) did nothing for
  another (a test install).

The dashboard is a first-class surface of the product; a zero-config
`pipx install` has to serve the real thing.

## Decision

**Commit the built bundle inside the Python package and ship it as package
data.**

1. **Vite builds into `sympose/webui/`.** `ui/vite.config.ts` sets
   `build.outDir` to `../sympose/webui` with `emptyOutDir: true`. The output
   is flat: `index.html`, `sympose.svg`, `assets/*` (hashed JS/CSS + fonts).
2. **`sympose/webui/` is committed.** It is not matched by any `.gitignore`
   rule (the ignored token is `dist/`). The old `ui/dist/` path is retired.
3. **Packaging ships it.** `[tool.setuptools.package-data]` gains
   `"webui/*"` and `"webui/assets/*"`; `include-package-data = true` is set
   explicitly; `MANIFEST.in` gains `recursive-include sympose/webui *`. A
   built wheel now contains all of `sympose/webui/` (verified: 17 files).
4. **`server.py` resolves the packaged bundle first.** `ui_candidates` is
   prepended with `os.path.join(os.path.dirname(__file__), "webui")`, so the
   in-package copy wins in every install mode. `ui/dist` and the `ui/`
   scaffold remain as fallbacks for a stale source tree.
5. **CI guards freshness.** `.github/workflows/tests.yml` gains a `ui-bundle`
   job that runs `npm ci && npm run build` (Node 20) and fails if
   `git diff -- sympose/webui` is non-empty. A stale bundle cannot land
   silently.
6. **Contributor workflow.** `CONTRIBUTING.md` states that any `ui/` change
   must be followed by `cd ui && npm run build` and a commit of the
   regenerated `sympose/webui/` in the same change, built with the Node
   version CI uses (20).

## Consequences

- `pipx install git+…` and a plain `git pull` both deliver a working
  dashboard with no Node toolchain required at the install site.
- Build artifacts now live in git. UI-only changes carry a bundle diff
  (hashed asset names churn); reviewers skim `sympose/webui/` rather than
  reading it. The repo grows by the gzipped bundle size (~700 KB JS + a
  1.6 MB lazy nebula chunk + fonts) plus history.
- Local and CI builds must agree byte-for-byte or the `ui-bundle` job fails.
  Dependency versions are already pinned by `ui/package-lock.json`; the Node
  **major** is the remaining variable, hence the "build with Node 20"
  instruction. If cross-environment drift proves fickle, the fallback is to
  pin CI to the maintainer's exact Node version.
- The dashboard bundle is decoupled from the Python version string; a UI fix
  ships whenever `sympose/webui/` is committed, no version bump needed.

## Alternatives rejected

- **Build hook at install time** (`pyproject.toml` custom command runs
  `npm ci && npm run build` during wheel/sdist build). Keeps artifacts out of
  git, but makes Node + npm a hard build dependency wherever Sympose is
  installed, slows every install, and turns a missing/old toolchain into an
  install failure. Contrary to the "sovereign, few moving parts" posture and
  the zero-config `pipx` promise.
- **CI builds and commits the bundle** (an Action rebuilds `sympose/webui/`
  on push and pushes a bot commit, or attaches it to a GitHub Release).
  Working tree stays clean, but every UI change grows a follow-up bot commit,
  installs are only current when CI is green, and `git+…` installs would need
  to target a release artifact rather than a ref. More infrastructure than a
  git-install project needs.
- **Keep `ui/dist/` at the repo root, ship via `data-files`.**
  `setuptools` `data-files` install relative to `sys.prefix`, landing at
  `<venv>/ui/dist`, which `server.py`'s package-relative resolution would not
  find without more special-casing. Putting the bundle *in* the package is
  the idiomatic path for "static assets a package serves".
- **Leave it as-is; document "run `npm run build`".** The status quo. Fails
  the primary `pipx` install path outright and offers no staleness signal for
  clones.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
