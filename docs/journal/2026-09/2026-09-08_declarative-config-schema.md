---
entry: 2026-09-08
created: 2026-09-08 19:40
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/config
---

# Sympose Engineering Log: Declarative Config Schema (Tier 1)

> **Date:** Monday, September 8, 2026
> **Topic:** Formalising the runtime knobs — ~25 global settings were read at ~44
> call sites, each owning its own literal default, with `/config` showing a
> hand-maintained 13-key subset and `/config set` / `[CONFIG_SET]` accepting any
> key with no validation. New per-persona knobs (`vault_grounding`) had no
> discoverable home.
> **Participants:** damiro (Lead Architect), Claude (Sonnet 5) (Engineering Partner)
> **Status:** Implemented, tested (219 passing)
> **Revisits:** [ADR-071](./2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md)
> — closes its "`CONFIG_SET` has no schema, no validation" gap.

## Changes

- **`sympose/config_schema.py`** — one `Setting(key, type, default, description,
  section, choices, min, max, scope, live)` per knob: ~25 global + 6
  persona-scoped. Standalone (imports nothing from `sympose`) so `config.py` can
  import it without a cycle. Helpers: `get_setting`, `default_for`, `coerce`
  (typed cast from a CLI/tag string, raises `ValueError` with a message),
  `validate` (enum / range; unknown keys pass so the caller decides).
- **`ConfigManager.get(key)`** falls back to the schema default when the key is
  absent and no explicit default was passed. Existing `get(key, literal)` calls
  are unchanged; `get(key)` now yields the schema default instead of `None`.
- **`ConfigManager.reload()`** now `deepcopy`s `DEFAULT_CONFIG` — it is a class
  attribute of nested dicts, and the old shallow `dict(...)` let `set()` /
  `_deep_merge()` mutate the shared nested dicts and permanently corrupt the
  class-level defaults (a `test_config` case leaked `request_timeout = 77.0`
  into every later test in the process).
- **`/config`** is schema-driven: no-arg lists every global setting grouped by
  section with its value and description; `/config get <key>` shows
  default / type / scope / live / allowed values; `/config set <key> <value>`
  coerces + validates (bad enum, out-of-range, unknown key, and per-persona keys
  all rejected with a specific message) before persisting.
- **`[CONFIG_SET]`** runs the same coerce + validate for known keys; a
  persona-scoped key is refused with a pointer to the persona YAML. Unknown keys
  keep the old permissive int/float/bool coercion (backward compatible).

## Not done (Tier 2/3, deferred)

Migrating the ~44 call sites to drop their literal defaults; a generated
`docs/wiki/reference/configuration.md`; a full ADR; and a `/persona set` command
for per-persona knobs (needs comment-preserving YAML writes — a new dependency,
its own decision).
