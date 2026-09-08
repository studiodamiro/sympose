---
entry: 2026-09-08
created: 2026-09-08 19:40
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/config
---

# Sympose Engineering Log: Declarative Config Schema (Tiers 1–3)

> **Date:** Monday, September 8, 2026
> **Topic:** Formalising the runtime knobs — ~25 global settings were read at ~44
> call sites, each owning its own literal default, with `/config` showing a
> hand-maintained 13-key subset and `/config set` / `[CONFIG_SET]` accepting any
> key with no validation. New per-persona knobs (`vault_grounding`) had no
> discoverable home.
> **Participants:** damiro (Lead Architect), Claude (Sonnet 5) (Engineering Partner)
> **Status:** Implemented, tested (233 passing)
> **Revisits:** [ADR-071](./2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md)
> — closes its "`CONFIG_SET` has no schema, no validation" gap.

## Changes

*This section records the initial Tier 1 landing; the Tier 2 and Tier 3 sections
below supersede parts of it (call-site literals removed, `DEFAULT_CONFIG`
deleted). The accepted end state is [ADR-077](./2026-09-08_adr-077-declarative-configuration-schema.md).*

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

## Tier 2 — call-site migration + generated reference (same day)

- **Call sites** — all 20 `config.get("<key>", <literal>)` in `sympose/` dropped
  their literal; `get("<key>")` now resolves the default through `DEFAULT_CONFIG`
  (where the key is mirrored) or `config_schema`. Runtime behaviour is unchanged
  — the tracked `config.yaml` supplies every value that matters, and 221 tests
  plus a boot smoke-check confirm identical resolved values. Three literals were
  more than redundant:
  - `cli.py` defaulted `session.exit_behavior.default_target` to `"memory"` while
    `commands.py`, `DEFAULT_CONFIG` and the schema said `"both"`. The tracked
    `config.yaml` also says `"memory"`, so the effective value never moved; the
    literal was removed and the schema realigned to `"memory"` (see below).
  - `memory.py` read a legacy two-level `session.obsidian_subfolder` key that is
    written nowhere — dead lookup removed.
  - `engine.py`'s per-model timeout carried an inline `120.0` local fallback that
    disagreed with the schema's `performance.local_request_timeout` (`60.0`),
    though not with `config.yaml` (`120.0`). Literal removed and the schema
    realigned to `120.0` (see below).
- **`sympose/config_reference.py`** (`python -m sympose.config_reference`)
  emits **`docs/wiki/reference/configuration.md`** (every knob: type, default,
  allowed values, live-vs-restart, description), grouped by the display sections.
  `test_config_schema.py` fails if the committed file drifts from the schema, so
  the doc cannot silently rot. Linked from `docs/wiki/index.md`.
- Tests: 219 → 221 (two new: doc-currency, every-global-key-documented).

## Reconciled — schema, `DEFAULT_CONFIG`, and tracked `config.yaml`

The repo ships a `config.yaml` that is itself a further declaration of defaults
(alongside `DEFAULT_CONFIG` and `config_schema`). Two values disagreed with the
schema; `config.yaml` was taken as intent and the other two sources moved to
match it:

| key | was (schema / `DEFAULT_CONFIG`) | now (all three) |
| --- | --- | --- |
| `performance.local_request_timeout` | `60.0` | `120.0` |
| `session.exit_behavior.default_target` | `both` | `memory` |

## Tier 3, piece 1 — one source of defaults (same day)

Before this, four places declared defaults: call-site literals (gone in Tier 2),
`ConfigManager.DEFAULT_CONFIG`, `config_schema.SETTINGS`, and
`bootstrap.DEFAULT_CONFIG_YAML` — the last of which had drifted badly
(`request_timeout: 10.0`, a phantom `sub_second_streaming` key, ~15 real keys
missing).

- **`config_schema.build_default_config()`** materialises every global setting's
  default into the nested dict `ConfigManager` layers `config.yaml` onto. A
  `None` schema default (now `performance.local_keep_alive`, was a `""`/`None`
  split between the two mirrors) is *omitted* rather than written as an explicit
  key, so "unset, defer to the environment" stays unset.
- **`ConfigManager.DEFAULT_CONFIG` deleted.** `reload()` calls
  `build_default_config()` — a fresh, independently-owned dict each call, so the
  old deep-copy dance is gone too.
- **`bootstrap.render_seed_config()`** replaces the stale literal: a fresh
  workspace's `config.yaml` is now `yaml.safe_dump(build_default_config())` under
  a short header pointing at the reference doc — complete and correct by
  construction.
- **`get()` contract tightened**: with every known key materialised, the `default`
  argument now only applies to genuinely absent keys (unknown, or `None`-default
  schema keys). Docstring updated; no production caller relies on the old
  behaviour (Tier 2 removed them all).
- Tests: 221 → 227. Dropped the schema↔`DEFAULT_CONFIG` agreement test (now
  vacuous); added coverage for `build_default_config()`, `None`-default omission,
  per-call independence, and that the seed `config.yaml` parses to exactly the
  built defaults with no unknown keys.

## Tier 3, piece 2 — persona write path + ADR (same day)

- **`/persona show [@handle]`** lists a persona's `scope="persona"` knobs and
  values; **`/persona set @<handle> <key> <value>`** writes one into
  `profiles/<handle>.yaml` through `ProfileManager.set_persona_field` — same
  `coerce` + `validate` as `/config set`, global keys refused with a pointer
  back to `/config`. The write turned out **not** to need a new dependency:
  `update_persona_skills` already round-trips persona YAML with plain
  `yaml.dump`, so `set_persona_field` matches it (manifest comments not
  preserved). `/config set` and `[CONFIG_SET]` now point a rejected persona key
  at `/persona set` instead of "edit the YAML".
- **`completer.CONFIG_KEYS`** was a hand-typed 14-key list (of ~30) — a fifth
  stale mirror. Replaced with a comprehension over `config_schema.
  global_settings()`; `PERSONA_KEYS` added the same way, and `/persona` gets
  sub-command / handle / key completion.
- **[ADR-077](./2026-09-08_adr-077-declarative-configuration-schema.md)** promotes
  this whole arc (Tiers 1–3) to a numbered decision; `PROJECT_JOURNAL.md` and
  `docs/wiki/index.md` ADR tables updated in the same change.
- Tests: 227 → 233 (`set_persona_field` coerce / range / enum / global-key /
  unknown-persona; completer lists track the schema).
