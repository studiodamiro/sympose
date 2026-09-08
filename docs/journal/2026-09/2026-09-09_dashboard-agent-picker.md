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

# Sympose Engineering Log: Dashboard Agent Picker & Persona-Scoped Vault Tree

> **Date:** Tuesday, September 9, 2026
> **Topic:** First two slices of stitching the terminal into the web dashboard
> — a trimmed `/api/personas` roster contract with the Agent panel's identity
> card + switcher, and the persona-scoped `/api/vault/tree` directory map it
> drives
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Implemented, tested (`.venv/bin/pytest` 309 passing,
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
- **`src/components/sympose/agent-card.tsx`** — the Agent panel body (a
  full-width section of the content panel, not a bordered card): a rounded
  accent band tinted with the persona's own `--persona-accent` (the same
  custom property `<PersonaPill>` uses), initials avatar lifting into it,
  name, title, `<ModelChip>`, and a "Switch agents" row of avatar buttons.
  Soul / Memory buttons are rendered **disabled** pending their endpoints.
- **`src/routes/app-shell.tsx`** — roster fetched once on mount, the active
  handle lifted to the shell, `<AgentCard>` rendered in the existing
  `MENU_ACCOUNT_ID` content panel.
- **`src/components/sympose/main-menu.tsx`** — the footer account row wears
  the active persona: `account` gained optional `icon` / `accent`, so the
  avatar shows the persona's glyph on its accent instead of a grey initial,
  and the label is the persona's full name rather than the word "Agent".

## 3. Deferred

- `GET /api/personas/{handle}/soul` and `/memory` — the content endpoints the
  disabled Soul / Memory buttons will call.
- The card's PINNED / RECENT lists — no defined data source yet.
- The chat stream — the other consumer of the active-persona handle.
- Auth: the UI's `fetch()` calls still send no credentials against the
  ADR-064.1 password guard.
- Persona avatars are initials / icons — there is no photo field in the
  profile schema.

## 4. Follow-up (same day): the persona-scoped vault tree

The picker's first real consumer landed immediately after: `GET
/api/vault/tree?persona=<handle>`, the vault-mapping half of the stitching
work.

- **`sympose/vault_tree.py`** (new) — `build_tree(nodes, allowed_prefixes)`, a
  pure fold of the ADR-078 manifest `nodes` into the nested `VaultNode` shape
  the frontend already defines (`{name, path, type, children?}`): folders
  before notes, each group case-insensitively sorted, ghosts (no `rel_path`)
  dropped. Persona scoping is a vault-relative path-prefix filter applied
  here, so the single whole-vault manifest still backs both the unscoped
  nebula and the scoped tree.
- **`VaultManager.get_vault_tree(profile)`** — resolves the master vault and
  `get_allowed_dirs(profile)` to relative prefixes (`realpath` compare; the
  vault root itself becomes `""` = whole vault), then delegates to
  `build_tree`. Ephemeral in-memory manifest build when
  `vault.manifest.enabled` is off, matching `get_vault_graph`.
- **`sympose/server.py`** — `GET /api/vault/tree`, persona query param
  defaulting to `samantha`, same pattern as `/api/vault/backlinks`.
- **`ui/`** — `fetchVaultTree(persona)` in `src/lib/vault-tree-api.ts`; the
  shell re-fetches the whole scoped tree on every persona switch. Each menu
  row's panel then shows just that entry's contents — a folder's own subtree,
  or a single root note — sliced client-side from the one fetched tree (no
  per-folder round-trip). Selecting a note only records the path for now;
  note-open is a later slice. `<VaultTree>` gained an optional `storageKey`
  that persists the expanded-folder set to a cookie (`sympose:vault.expanded`)
  so the open/closed shape survives a reload — the same `storageKey`
  convention `<MainMenu>` / `<ContentPanel>` already use.
- **`ui/` main menu is now live** — the left rail is built from the tree's
  surface (top-level folders + root notes like `README.md`) in the tree's own
  order, not the static 13-entry `VAULT_FOLDERS` list. `VAULT_FOLDERS` is kept
  only as a curated name→icon map (unknown folders fall back to a generic
  folder glyph; root notes get a note glyph). The highlighted section is
  *derived* — a persisted id that no longer exists after a persona switch
  falls back to the first surface entry, no `setState`-in-effect. The demo
  routes (`menu-showcase`, `components-gallery`) still use the static list.
- Tests: `tests/unit/test_vault_tree.py` (nesting, ordering, ghost exclusion,
  prefix scoping, path-boundary match) and a route-registered assertion in
  `test_server.py`. Full suite 309 passing.

## 5. Notes

- `ui/dist` is git-ignored, so the branch does not carry a built bundle; the
  install side needs `cd ui && npm run build` after pulling, and a restart of
  `app.py --dashboard` to serve the new `/api/personas` and `/api/vault/tree`
  routes.
- `sympose/server.py` is now ~235 LOC, over the 200-LOC guideline. The
  `/api/personas` change was a trim of an existing endpoint; `/api/vault/tree`
  is a ~7-line thin route delegating to `VaultManager`, with the real logic in
  `vault_tree.py`. If the persona/soul/memory endpoints land, the route
  definitions in `create_app` should move to per-domain routers.
