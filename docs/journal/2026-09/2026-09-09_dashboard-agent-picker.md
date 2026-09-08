---
entry: 2026-09-09
created: 2026-09-09 05:10
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/ui
  - sympose/dashboard
---

# Sympose Engineering Log: Dashboard Agent Picker & Persona Roster Contract

> **Date:** Tuesday, September 9, 2026
> **Topic:** First slice of stitching the terminal's persona surface into the
> web dashboard — a trimmed `/api/personas` roster contract and the Agent
> panel's identity card + switcher
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Implemented, tested (`.venv/bin/pytest` 304 passing,
> `npm run typecheck` + `eslint` clean), pushed on
> `feat/dashboard-agent-picker`.

---

## 1. Context

The dashboard so far consumes only read-only vault endpoints
(`/api/vault/graph`, `/api/vault/note`, `/api/vault/backlinks`) plus
`/health` and `/api/config`. Everything the terminal does — the chat stream,
the slash-command surface, persona switching — is CLI-only. damiro opened a
scoping pass on "stitching the terminal functions to the dashboard" and,
after mapping the dependencies, chose to land the **agent picker first**: the
smallest self-contained piece, and a prerequisite for scoping every later
`?persona=` call.

Two directional decisions came out of that discussion and are recorded here
so the later slices inherit them:

- **The dashboard vault tree will be persona-scoped**, not whole-vault —
  filtered through `VaultManager.get_allowed_dirs(profile)` like every other
  sandboxed vault call, rather than persona-independent like the nebula
  graph. Because the only shippable default persona (`samantha`) is scoped to
  `vault_folders: ["*"]`, a persona-scoped tree defaulted to her produces
  byte-identical output to a whole-vault tree today — so doing it right costs
  almost nothing and avoids a contract migration when other personas reach
  the dashboard.
- **The active persona is client state, not a server session.** The dashboard
  is single-user; a cookie (`sympose:active_persona`) plus a `?persona=`
  query argument on scoped requests matches how `/api/vault/note` and
  `/api/vault/backlinks` already default `persona="samantha"`, and keeps the
  engine's per-handle history keying untouched.

## 2. What shipped

### Backend

- **`sympose/server.py`** — `GET /api/personas` now returns a trimmed
  projection instead of the raw profile dicts:

  ```json
  {
    "default": "samantha",
    "personas": [
      { "handle": "...", "name": "...", "title": "...",
        "model": "...", "skills": [...], "is_default": true }
    ]
  }
  ```

  The raw response leaked `soul_file` / `memory_file` disk paths and
  `thinking_phrases`; the picker needs none of that. `default` is read from
  `runtime.default_persona`.

- **`tests/unit/test_server.py`** — `test_personas_endpoint_is_a_trimmed_projection`
  asserts the exact projected shape and that `soul_file` / `thinking_phrases`
  are absent.

### Frontend (`ui/`)

- **`src/lib/personas.ts`** — `fetchPersonas()` (falls back to the static
  `PERSONA_LIST` when the API is unreachable, so the picker always renders)
  and `resolvePersonaVisuals(handle)` (curated icon + light/dark accent when
  the handle is in the static roster, a neutral grey otherwise, so
  runtime-created personas still get a stable colour).
- **`src/lib/use-active-persona.ts`** — `useActivePersona()`, a cookie-backed
  `[handle, setHandle]` pair defaulting to `samantha`. Cookie, not
  localStorage, per UI_DESIGN_REFERENCE.md §5.
- **`src/components/sympose/agent-card.tsx`** — the Agent panel card: accent
  band tinted with the persona's own `--persona-accent` (the same custom
  property `<PersonaPill>` uses), initials avatar, name, title, `<ModelChip>`,
  and a "Switch agents" row of avatar buttons. Soul / Memory buttons are
  rendered **disabled** pending their endpoints.
- **`src/routes/app-shell.tsx`** — roster fetched once on mount, the active
  handle lifted to the shell, `<AgentCard>` rendered in the existing
  `MENU_ACCOUNT_ID` ("Agent") content panel.

## 3. Deferred

- `GET /api/personas/{handle}/soul` and `/memory` — the content endpoints the
  disabled Soul / Memory buttons will call.
- The card's PINNED / RECENT lists — no defined data source yet.
- Consumers of the active-persona handle: the persona-scoped vault tree
  (`GET /api/vault/tree?persona=`) and the chat stream. The picker only
  writes the cookie today.
- Auth: the UI's `fetch()` calls still send no credentials against the
  ADR-064.1 password guard.
- Persona avatars are initials / icons — there is no photo field in the
  profile schema.

## 4. Notes

- `ui/dist` is git-ignored, so the branch does not carry a built bundle; the
  install side needs `cd ui && npm run build` after pulling, and a restart of
  `app.py --dashboard` to serve the new `/api/personas` shape.
- `sympose/server.py` is now ~226 LOC, over the 200-LOC guideline. The
  `/api/personas` change is a trim of an existing endpoint rather than a new
  concern, so it was made in place; if the Soul / Memory endpoints land, the
  personas routes should move to their own router module.
