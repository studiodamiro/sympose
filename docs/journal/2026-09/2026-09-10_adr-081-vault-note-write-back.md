---
title: "ADR-081 — Vault Note Write-Back from the Dashboard Editor"
created: 2026-09-10
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-081 — Vault Note Write-Back from the Dashboard Editor

- **Status:** Accepted — implemented 2026-09-10.
- **Date:** 2026-09-10
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Builds directly on
  [ADR-080 — Stylo as the Vault Markdown Editor](./2026-09-10_adr-080-stylo-vault-markdown-editor.md),
  which wired the editor for reading only.
- Reuses the sandbox primitives from
  [ADR-078 — Materialized Vault Manifest](./2026-09-09_adr-078-vault-manifest-materialized-map.md)
  (`is_safe_path`, persona-scoped allowed folders).

## Context

ADR-080 mounted `stylo` (`@damiro/stylo`) as the dashboard's Markdown editor.
Loading was wired to `GET /api/vault/note`; **saving was not**. The panel left
`onSave` unset, so stylo's `save` toolbar command rendered permanently disabled
(`disabled: (e) => e.facet(C) == null`) and `⌘/Ctrl-S` kept its browser
default. Every edit — body keystrokes and frontmatter-card pills alike — lived
only in React state and was lost on a note switch or reload.

The backend had no write route at all: `sympose/server.py` exposed only `GET`
endpoints for the vault. `VaultManager.write_note()` exists but is built for
agent tool-calls — it injects a title heading, applies a folder template, and
synthesises a `created:`/`tags:` frontmatter block when none is present. Pointing
the editor at it would mangle a hand-authored note on the first save.

The editor is only half a feature without a way back to disk.

## Decision

**Add a dedicated verbatim write path, driven by an explicit save with an
opt-in autosave knob.**

### Backend

1. **`VaultManager.overwrite_note(profile, note_name, content)`** — new
   classmethod alongside `write_note` / `append_note`. It resolves the *same*
   file `read_note` would return (direct path under the master vault →
   basename in an allowed folder → recursive case-insensitive stem match),
   confirms the resolved path is inside the persona's sandbox with
   `is_safe_path`, then writes `content` **exactly**, normalised only to a
   single trailing newline. On success it runs the same
   `_reindex_note_if_enabled` / `_update_manifest_if_enabled` hooks as
   `write_note`.
2. **Overwrite only.** A path with no existing file returns the sentinel
   `NOTE_NOT_FOUND`; a path resolving outside the sandbox returns
   `NOTE_DENIED`. Creating new notes from the editor is out of scope for this
   ADR — it needs a folder picker and a name prompt, which the dashboard does
   not have yet.
3. **`PUT /api/vault/note`** — body `{path, content, persona}` (a Pydantic
   `NoteWrite` model, `path` non-empty). Maps `NOTE_NOT_FOUND` → 404,
   `NOTE_DENIED` → 403, an `Error:` string → 500, otherwise 200 with the
   confirmation detail. Sits behind the same ADR-064.1 password guard as every
   other route.

### Frontend

4. **`saveVaultNote(path, content, persona)`** in `ui/src/lib/vault-note-api.ts`
   — `PUT`s and returns a discriminated `{ok: true} | {ok: false, error}` so
   the caller can toast rather than catch.
5. **`markdown-panel.tsx` recombines and saves.** A `joinNote(frontmatter,
   body)` helper puts the frontmatter card's `---` block (its inner text — the
   shape `splitFrontmatter` yields) back in front of stylo's body. `onSave`
   (fired by the toolbar button and `⌘/Ctrl-S`) calls a shared `saveNote()`
   that compares `joinNote(...)` against a `savedTextRef` snapshot, skips when
   unchanged or already in flight, `PUT`s, and updates the snapshot. A
   `loadedPathRef` guard blocks a save in the window between a note switch and
   its fetch resolving, so the previous body can never be written to the new
   note's path.
6. **Autosave is an editor preference, not a config-schema knob.**
   `EditorPreferences` gains `autosave: "on" | "off"` (default `"off"`),
   cookie-backed (`sympose:editor.autosave`) exactly like `surface` / `reveal`
   / `selectionUI` / `focusOutline`, with a toggle in
   Settings › Markdown editor. When on, a trailing 1.5 s debounce on
   body/frontmatter changes calls `saveNote({silent: true})`. This follows the
   precedent already codified for editor preferences (per-browser editing
   behaviour, not backend/agent configuration — ADR-077 §scope), so it does
   **not** enter `sympose/config_schema.py`.

## Consequences

- The editor round-trips: open a vault note, edit body or frontmatter, hit
  save (or `⌘/Ctrl-S`), and the file on disk changes, re-indexed and
  re-projected into the manifest/graph.
- **Frontmatter is re-serialised on every save**, even when only the body
  changed — `joinNote` rebuilds the block from the card's parsed model
  (`yaml.stringify`). Key order is preserved; incidental formatting (quote
  style, indentation, blank lines inside the block) is normalised. A note
  whose frontmatter is not a flat mapping is left untouched by the card
  (ADR-080) and round-trips as-is.
- No new-file creation, no rename, no delete from the editor. Those are
  separate features.
- Autosave writes on a debounce with no conflict detection — last write wins.
  Acceptable for a single-user local vault companion; a shared-vault scenario
  would need `If-Match`/mtime checks. Off by default keeps the surprise
  surface small.
- One new backend dependency-free method (~45 LOC) and one route; the request
  cost is a single local file write, no LLM round-trip.

## Alternatives rejected

- **Reuse `VaultManager.write_note()`.** It template-mangles: title heading,
  folder template application, synthesised frontmatter when none is detected.
  Fine for an agent creating a note from a prompt, destructive for a human
  saving an existing one. A verbatim writer is a different operation and
  deserves its own method.
- **Autosave only, no button.** Fewer controls, but it makes every idle pause
  a disk write and a manifest re-projection, offers no "I'm done" moment, and
  needs dirty/race handling to not fight a fast typist. The explicit save is
  the honest default; autosave rides on top for those who want it.
- **Autosave as a `config_schema.py` runtime knob (ADR-077).** The schema is
  for backend/agent configuration read by the Python runtime. Autosave is
  per-browser editor behaviour with no backend meaning — the same category as
  the existing `surface`/`reveal` cookies, which `use-editor-preferences.ts`
  already documents as deliberately *not* schema knobs. Putting it in the
  schema would split one concept across two config systems.
- **`POST` that also creates missing notes.** Folds "save" and "new note"
  into one endpoint before the dashboard has any new-note UI, and makes a
  typo'd path silently spawn a file instead of erroring. Overwrite-only with a
  404 is the safer contract; create-new gets its own ADR when the UI needs it.
- **Persist to a scratch/draft store instead of the vault.** Keeps the vault
  read-only from the dashboard, but the whole point of ADR-080 was direct
  dialogue *with* the vault; a shadow copy is a second source of truth to
  reconcile.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
