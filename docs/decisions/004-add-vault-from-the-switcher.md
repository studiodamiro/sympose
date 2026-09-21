# 004 — Add a vault from the workspace switcher, persisted alongside the env-configured list

## Context

ADR 003 made the configured vault list purely a `VAULT_PATHS` env var —
static for the life of the process, set once at deploy/dev-server-start
time. Using the switcher day to day surfaced the obvious next need: a way
to add a vault without stopping the backend, editing `.env`, and
restarting. The switcher already had to become a real interactive popup
for switching; adding a second affordance to the same surface, rather than
sending the user to a separate flow, was the natural next step, and
damiro asked for exactly that live while the switcher landed. The
switcher's "Vault" caption above the list was dropped in the same pass —
plain, unlabelled rows read fine on their own once there's an add
affordance right below them.

## Decision

`vault_paths.get_configured_vaults()` now merges two sources, env-declared
vaults first: `VAULT_PATHS` (unchanged from ADR 003) and a new
`settings_store` key, `added_vaults` — a plain list of absolute paths,
appended to by a new `vault_paths.add_vault(path)`. `add_vault` requires
`path` to already be an existing directory (it points at a real,
already-created Obsidian vault; it does not create one) and is idempotent
— adding an already-configured path just returns that vault's existing
entry rather than duplicating it.

`POST /api/vaults` (new route, `server_vault_handlers.add_vault`) adds and
immediately activates the vault in one round trip — the switcher's
add-path input is the whole flow: type a path, hit Enter or the `+`
button, land in the new vault. Both `POST /api/vaults` and
`POST /api/vaults/active` share one request body shape (`VaultActivate`,
`{path}`) rather than a second identical model.

## Consequences

A vault added this way survives a backend restart (it's in
`settings_store`'s file, same as `active_vault`), but not a fresh checkout
or a different `SYMPOSE_SETTINGS_PATH` — it's this install's local state,
not shipped configuration. `VAULT_PATHS` stays the way to declare vaults a
deployment always wants present regardless of local UI actions;
`added_vaults` is purely additive on top of it, never removes or overrides
an env-declared entry. There's no remove-a-vault affordance yet — only add —
since nothing has asked for it yet; `settings_store`'s flat `get`/`set`
already has room for an `added_vaults` write that drops an entry, whenever
that's needed.

## Alternatives rejected

- **Route it through `POST /api/vaults/active` with an "upsert" flag**
  instead of a separate `POST /api/vaults`. Rejected: conflates two
  different actions (select among the configured list vs. extend the
  list) under one endpoint and one 404-vs-400 error contract, for no real
  code savings — the handler logic barely overlaps beyond both ending in
  `list_vaults()`.
- **Require the path to be typed exactly, no `~` expansion / relative
  resolution.** Rejected: `get_configured_vaults()` already
  `os.path.expanduser` + `os.path.abspath`s every source uniformly, so
  making `add_vault` do anything less would just mean a `~`-typed path
  silently fails to match on the next `get_configured_vaults()` call
  (different string, same real directory).
- **Auto-create the directory if it doesn't exist**, so a brand-new
  from-scratch vault can be typed in directly. Rejected for now: this
  input is about pointing at a vault that already exists (the same
  expectation `MASTER_VAULT_PATH`/`VAULT_PATHS` always had); silently
  creating a directory from a typo would be a surprising side effect for a
  400 that should instead tell the user their path is wrong.
