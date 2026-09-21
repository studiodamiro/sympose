# 003 — Multi-vault: a comma-separated configured list, one active vault, a new settings-file store

## Context

`VISION.md`'s multi-vault section settles the shape: one active vault at a
time, switchable — not multiple vaults open or searched simultaneously,
since that would add a vault dimension to every sandboxing/persona check
in the backend. The backend tracks which vault is active via
`GET /api/vaults` and `POST /api/vaults/active`; the UI trigger is a
workspace-switcher popover off the existing brand mark.

Three things that decision doesn't yet pin down: what names the configured
list, how it's declared, and where "which one is active" is remembered
across restarts. The existing single-vault var was `MASTER_VAULT_PATH` —
every other piece of backend config so far (`SYMPOSE_PROFILES_DIR`) is a
plain env var read fresh on every call, and there is no
settings-persistence mechanism in this backend at all yet. The process
ledger has carried "Settings storage for app-wide knobs (active vault,
compaction default, Slack allowlist)" as a deferred item since the search
milestone, explicitly deferred to "whenever the vault switcher actually
lands." It has now landed.

## Decision

**Configured list:** a new env var, `VAULT_PATHS`, replaces
`MASTER_VAULT_PATH` outright — accepting a comma-separated list of
absolute (or `~`-expanded) paths, a single path being the list-of-one
case. `MASTER_VAULT_PATH`'s "master" framing stopped fitting the moment it
could name more than one vault, and nothing outside this checkout depends
on the old name yet, so this is a straight rename rather than a second var
kept alongside it (`.env.example`, `README.md`, and every existing local
`.env` update in the same change). Each vault's display name is its
directory basename; if two configured vaults share a basename, the name
falls back to `<parent>/<basename>` for just those entries, so the
switcher never shows two identically-labelled rows.

**Active-vault persistence:** a new `sympose/settings_store.py` module —
the settings storage the ledger deferred — backed by one JSON file,
`SYMPOSE_SETTINGS_PATH` (default `./settings.json`, same cwd-relative
convention `SYMPOSE_PROFILES_DIR` already uses). It exposes a plain
`get(key, default)` / `set(key, value)` pair over the whole file, not a
vault-specific API, so the compaction default and Slack allowlist the
ledger also named can land in the same file later without a second
storage mechanism. `active_vault` is the one key it holds today.

`vault_paths.get_master_vault()` — the single function every sandboxing
and vault-content call already goes through — now resolves the active
vault instead of reading `VAULT_PATHS` directly: settings-store
`active_vault` if it's still present in the configured list, else the
first configured vault, else `None`. Every existing caller is unchanged;
none of them cache the result across a vault switch, since every mtime-
keyed cache (`vault_paths.mtime_cached` and its callers) is keyed off the
resolved directory paths themselves, so switching the active vault
naturally invalidates them rather than silently serving stale content
from the previous vault.

`POST /api/vaults/active` validates the requested path against the
configured list before persisting it — it is not an arbitrary-path write.

## Consequences

No new dependency (`json` and the existing `os`/`yaml` stdlib-plus-PyYAML
footprint cover this). Every module downstream of `vault_paths` keeps
working unmodified, because they all already re-resolve the vault root
per call rather than holding it. `settings.json` is a local, gitignored,
per-checkout file, same treatment as `.env` — it's app state, not source.
A later knob (compaction default, Slack allowlist) is additive: a new key
in the same file, no new module.

## Alternatives rejected

- **Keep `MASTER_VAULT_PATH` and overload it with commas**, instead of
  renaming. Rejected: it reads wrong the moment it holds more than one
  path (`MASTER_VAULT_PATH=A,B` — a "master" of two), and this project's
  standing rule against compatibility shims (`CLAUDE.md`) applies here too
  — there's no external deployment depending on the old name yet, so
  there's nothing a rename needs to stay compatible with.
- **A prefixed `SYMPOSE_VAULT_PATHS`** rather than the unprefixed
  `VAULT_PATHS`. Rejected: `SYMPOSE_*` is this backend's convention for
  config introduced after `MASTER_VAULT_PATH` already existed unprefixed
  (`SYMPOSE_PROFILES_DIR`, `SYMPOSE_SETTINGS_PATH`); `VAULT_PATHS` is that
  same var's direct successor, not new config, so it keeps the original's
  unprefixed form.
- **YAML for the settings file, matching `profiles/*.yaml`.** Rejected for
  now — the profiles loader's YAML choice is about hand-editability for
  persona authoring; this file is only ever written by the backend itself
  in response to a UI action, never hand-authored, so JSON's stdlib-only
  read/write is the simpler fit. Revisit if a future knob genuinely needs
  hand-editing.
- **Porting legacy's `ConfigManager`/`config_schema`** (a declarative
  settings-schema class with dot-path get/set, YAML layering, and
  runtime-apply hooks for third-party libraries). Rejected as scope far
  beyond one key: it exists in legacy to serve a much larger settings
  surface (LLM performance knobs, MCP registry, etc.) this backend doesn't
  have yet. A flat `get`/`set` over one JSON file is the complete
  substitute for what's actually needed today; grow it only when a real
  second or third knob shows up, per this project's `surgical-port`
  practice of porting only what's reachable, not whole files.
