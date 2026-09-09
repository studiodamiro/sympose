---
title: "ADR-083 — Editor Note Creation & Frontmatter Round-Trip Fidelity"
created: 2026-09-10
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - vault
---

# ADR-083 — Editor Note Creation & Frontmatter Round-Trip Fidelity

- **Status:** Accepted — implemented 2026-09-10.
- **Date:** 2026-09-10
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Extends [ADR-081 — Vault Note Write-Back](./2026-09-10_adr-081-vault-note-write-back.md),
  which shipped save as overwrite-only and re-serialised the frontmatter block
  on every save. This ADR closes both gaps it named.

## Context

ADR-081 gave the dashboard editor a save path but deliberately left two things:

1. **No way to create a note.** `PUT /api/vault/note` 404s on a path with no
   file. Starting a new note meant creating the `.md` in Obsidian (or the shell)
   first, then refreshing the dashboard.
2. **Frontmatter got reformatted on every save.** `joinNote` always rebuilt the
   block as `---\n${cardModel}\n---\n\n`, so editing only the body still
   normalised the YAML (quote style, indentation, blank lines, CRLFs) because
   the card round-trips through `yaml.stringify`.

## Decision

### New-note creation

- **`VaultManager.create_note(profile, note_name, content=None)`** — sibling of
  `overwrite_note`. `note_name` is a vault-relative path (`Folder/Sub/Title`);
  it lands under the master vault when it contains a separator, else in the
  persona's primary folder. `realpath` + `is_safe_path` sandbox check.
  **Refuses to clobber** — an existing file returns `NOTE_EXISTS`, not an
  overwrite. When `content` is omitted it seeds a minimal stub:

  ```
  ---
  title: <Title from filename>
  created: <YYYY-MM-DD>
  tags: []
  ---

  # <Title>
  ```

  so the editor opens onto something with a working frontmatter card. Re-indexed
  and added to the manifest like every other write.
- **`POST /api/vault/note`** `{path, content?, persona}` → `201` with the
  confirmation detail, `409` if a note already exists there, `403` outside the
  sandbox. Behind the ADR-064.1 password guard.
- **Dashboard UI.** A `NoteAdd` button next to the vault-panel heading toggles an
  inline name field. Enter creates the note in the folder currently in view (or
  the vault root when a root note is the active surface), re-pulls the tree
  (a `vaultRefreshKey` bump on the existing `fetchVaultTree` effect), selects
  the new note, and opens the editor. `Esc` cancels. Errors surface as a
  `sonner` toast.

### Frontmatter round-trip fidelity

- `markdown-panel` now keeps the note's **exact original `---`…`---` prefix**
  (`result.content.slice(0, content.length - body.length)`) and a
  `frontmatterEditedRef` flag, set only when the card's `onChange` actually
  fires.
- `joinNote(frontmatter, body, originalPrefix, frontmatterEdited)`:
  - card untouched → `originalPrefix + body` (block preserved byte-for-byte);
  - card edited a field → re-serialise from its model, as before (normalising
    is unavoidable once a pill changes).

## Consequences

- A note can be created and edited entirely from the dashboard.
- A body-only save no longer perturbs the frontmatter block — no phantom diffs
  on notes with hand-formatted YAML, comments, or unusual quoting.
- `create_note` seeds `title` / `created` / `tags` — an opinion, not verbatim.
  A caller that wants a blank file can pass `content: ""` … which the stub
  branch treats as "seed it"; passing a single newline gets a near-empty file.
  Good enough; a "blank note" affordance can come later if wanted.
- New-note creation targets the folder in view. Creating into an arbitrary
  nested folder needs a folder picker — deferred.
- No rename or delete from the editor yet.

## Alternatives rejected

- **One `PUT` that also creates on 404.** Collapses "save" and "new note", so a
  typo'd path silently spawns a file instead of erroring. A separate `POST`
  with a `409` keeps the two intents distinct — the same split ADR-081 already
  argued for.
- **Create blank, no stub.** A zero-byte `.md` opens with no frontmatter card
  and no title; every new note would need the same three lines typed by hand.
  The stub matches what `write_note` (the agent path) already seeds and what
  Obsidian templates do.
- **A modal dialog for new-note (name + folder picker + template).** More UI
  than the action needs today. The inline field in the panel header is one
  keystroke to open, one to confirm; a picker lands when "create anywhere"
  is actually asked for.
- **Diff the re-serialised frontmatter against the original and keep the
  original when "equivalent".** Needs a semantic YAML comparison and still
  reformats the moment anything genuinely changes. Tracking "did the card fire
  `onChange`" is exact and cheap.
- **Make the frontmatter card edit CodeMirror text directly** (no separate
  model). Removes the round-trip entirely but throws away the structured pill
  UI ADR-080 chose. Out of scope here.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
