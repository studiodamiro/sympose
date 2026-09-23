# 011 — One directory per persona

## Context

A persona is more than its config. VISION.md defines it as soul (voice), memory (accumulated, private), expertise (a grounded domain), and a vault-folder scope, plus each persona has its own chat sessions. Until now those were planned, and partly built, as scattered flat files keyed by handle: `profiles/<handle>.yaml` for config, `profiles/<handle>_soul.md` and `profiles/<handle>_memory.md` (ADR 001, `.gitignore`), and a separate top-level `sessions/<handle>/` (ADR 006). Only the config file and the sessions exist in code today; soul, memory, and expertise are unbuilt, which makes this the cheapest moment to settle the layout: nothing yet depends on the flat naming except the YAML loader, the session path, `.gitignore`, and two ADRs' wording.

## Decision

Each persona is a directory, `profiles/<handle>/`, holding everything that belongs to it:

- `persona.yaml` — config: name, title, `vault_folders`, `model`, `skills`. Named `persona.yaml` rather than `profile.yaml` or `personal.yaml`: it is the persona's definition, and `personal` would read as if it were the private file (that is `memory.md`).
- `soul.md`, `memory.md`, `expertise.md` — created by the milestones that build them, not now.
- `sessions/<id>.jsonl` — that persona's chat sessions, replacing the top-level `sessions/<handle>/`.

A persona exists if and only if its directory contains `persona.yaml`. ADR 009's fail-closed contract is unchanged, restated against the new shape: with no `profiles/` directory at all the whole-vault fallback still applies; once `profiles/` exists, a handle with no `persona.yaml`, an unsafe path, or an unparseable file resolves to nothing. The roster (`list_profiles`) is every `profiles/*/persona.yaml`, so anything else sitting in `profiles/` (a stray file, a directory without a config) is not a persona.

Sessions live in the persona's directory, except when no `profiles/` directory exists (the fallback mode), where they stay in `./sessions/<handle>/` as before: writing a session under `profiles/` would create that directory and flip the whole system out of fallback mode as a side effect of a chat. `SYMPOSE_SESSIONS_DIR` is removed; it described a location that no longer exists as a separate concept, and the persona directory is already relocatable through `SYMPOSE_PROFILES_DIR`.

`.gitignore` is rewritten around the directory: everything under `profiles/` is ignored except Samantha's `persona.yaml` and `soul.md`, the shipped baseline. Memory and sessions are therefore ignored for every persona with no exception (ADR 001's invariant, restated as `profiles/*/memory.md` and `profiles/*/sessions/`), and a new persona directory is local by default with nothing to remember to add. Whether Samantha's `expertise.md` ships is decided when expertise is built.

## Consequences

A persona can be created, exported, backed up, or deleted as one folder, which is also the shape "Sam can create a persona" needs. The old flat `profiles/<handle>.yaml` files are no longer read; a persona left in the old layout silently drops out of the roster, so the CLI's "no personas configured" message now names the expected `<handle>/persona.yaml` shape. There is no compatibility reader for the old layout: two layouts would be permanent bloat for a project that has not shipped. Existing sessions in the old `sessions/` location are not migrated; the maintainer's development sessions were deleted (the older legacy app's sessions under `~/.sympose/` are a different format the rewrite never reads, and are untouched). Sessions now sit inside a mostly committed folder, so the `sessions/` ignore rule under every persona is load-bearing, and is verified with `git check-ignore` rather than trusted. The cross-persona files legacy kept (`_shared_memory.md`, `user_profile.md`) are not part of this decision; they belong to no single persona, would sit as plain files directly in `profiles/` (which the roster scan ignores), and are decided if and when something needs them. Directory names are expected to be lowercase handles: the loader lowercases a handle before building its path, so on a case-sensitive filesystem a mixed-case directory is listed but not found (the flat layout had the same limit for a mixed-case filename); macOS's case-insensitive default hides it. Sessions are tied to the mode in effect when they are read: history written in fallback mode under `./sessions/` is not found once a `profiles/` directory is later created, the same no-migration stance as above. ADR 001, 006, and 009 keep their text and gain a pointer here, since the invariants they record still hold and only the paths changed.

## Alternatives rejected

- **Keeping the flat `<handle>_soul.md` / `<handle>_memory.md` naming.** Rejected: it spreads one persona across several sibling files that have to be found, ignored, and deleted together by convention, and leaves sessions somewhere else entirely.
- **Leaving sessions in a top-level `sessions/<handle>/`** while moving only the config files. Rejected as a half-move: sessions are per-persona state, and a second root to configure, ignore, and clean up is the duplication this record removes. Kept only as the no-`profiles/`-directory fallback, for the reason above.
- **A compatibility reader for the old flat layout**, or an automatic migration on startup. Rejected: nothing shipped in the old layout except one config file, moved here in the same change.
- **`profile.yaml` or `personal.yaml` as the config name.** Rejected as described above.
- **Migrating the old development sessions.** Rejected by the maintainer; they were throwaway.
