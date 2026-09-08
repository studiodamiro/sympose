---
title: "ADR-077 — Declarative Configuration Schema as Single Source of Truth"
created: 2026-09-08
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - config
---

# ADR-077 — Declarative Configuration Schema as Single Source of Truth

- **Status:** Accepted — implemented 2026-09-08 (Tiers 1–3).
- **Date:** 2026-09-08
- **Deciders:** damiro (Lead Architect); Claude (Sonnet 5) (Engineering Partner)
- Closes the "`[CONFIG_SET]` has no schema, no validation" gap left open by
  [ADR-071](./2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md).
- Full working log:
  [2026-09-08 — Declarative Config Schema (Tiers 1–3)](./2026-09-08_declarative-config-schema.md).

## Context

Sympose's ~25 runtime knobs had no single definition. Each was read via
`config.get("dotted.key", <literal-default>)` at ~44 call sites, every site
owning its own copy of the default. On top of that, defaults were *also*
declared in three more places, none of them in sync:

- **`ConfigManager.DEFAULT_CONFIG`** (a nested dict in `config.py`) — ~20 of the
  keys, used as the base `config.yaml` is merged onto.
- **`bootstrap.DEFAULT_CONFIG_YAML`** — the seed `config.yaml` written into a
  fresh workspace. It had rotted: `request_timeout: 10.0` (the code used 30),
  a `sub_second_streaming` key that does not exist, and ~15 real keys missing.
- **`completer.CONFIG_KEYS`** — a hand-typed list of 14 keys for `/config set`
  Tab-completion, roughly half the real set.

`/config` rendered from a separate hand-maintained 13-key subset. `/config set`
and the model-emitted `[CONFIG_SET]` tag accepted **any** key with no type
coercion and no validation — a typo or an out-of-range value persisted silently
to disk. New per-persona knobs (`vault_grounding`, added the same week) had no
discoverable home and no write path other than hand-editing YAML.

## Decision

**One declarative list defines every knob; everything else is derived from it.**

- **ADR-077.1 — `sympose/config_schema.py` is the schema.** One frozen
  `Setting(key, type, default, description, section, choices, minimum, maximum,
  scope, live)` per knob — ~25 `global`, 6 `persona`. The module imports nothing
  from `sympose`, so `config.py` can import it at load with no cycle. It exposes
  `get_setting`, `default_for`, `global_settings`, `persona_settings`,
  `coerce` (typed cast from a CLI/tag string, raising `ValueError` with a
  human message) and `validate` (enum / range; unknown keys pass so the caller
  decides).

- **ADR-077.2 — `/config` and `[CONFIG_SET]` are schema-driven.** `/config`
  with no argument lists every global setting grouped by section with its live
  value and description; `/config get <key>` shows default / type / scope /
  live / allowed values; `/config set` and `[CONFIG_SET]` run `coerce` +
  `validate` and reject a bad enum, an out-of-range number, an unknown key, or a
  persona-scoped key (with a pointer to `/persona set`) *before* persisting.
  Unknown keys via `[CONFIG_SET]` keep the old permissive numeric/bool coercion
  for backward compatibility.

- **ADR-077.3 — Call sites carry no defaults.** All 20 `config.get("key",
  <literal>)` sites in `sympose/` dropped their literal; `get("key")` resolves
  the default through the schema. Three literals were also wrong and were
  corrected (a dead legacy `session.obsidian_subfolder` lookup removed; an
  inline `120.0` local-timeout fallback and a `"memory"` default-target that
  disagreed with their schema entries — see the Implementation Note).

- **ADR-077.4 — `config_schema.build_default_config()` is the only
  hand-maintained default source.** It materialises every global setting's
  default into the nested dict shape `ConfigManager` layers `config.yaml` onto,
  returning a fresh, independently-owned dict per call. `ConfigManager.
  DEFAULT_CONFIG` is **deleted**. `bootstrap.render_seed_config()` writes a fresh
  workspace's `config.yaml` as `yaml.safe_dump(build_default_config())` under a
  short header pointing at the reference doc. `completer.CONFIG_KEYS` /
  `PERSONA_KEYS` are list comprehensions over `global_settings()` /
  `persona_settings()`. The stale `DEFAULT_CONFIG_YAML` and the hand-typed
  completer list are gone. A `None` schema default (e.g.
  `performance.local_keep_alive`) is *omitted* from the built dict rather than
  written as an explicit null, so "unset — defer to the environment" stays
  unset.

- **ADR-077.5 — Persona-scoped knobs get a first-class write path.**
  `/persona show [@handle]` lists a persona's `scope="persona"` settings and
  current values; `/persona set @<handle> <key> <value>` writes one into
  `profiles/<handle>.yaml` via `ProfileManager.set_persona_field`, which runs the
  same `coerce` + `validate` and refuses a global key (pointing at `/config
  set`). The write is a plain `yaml.safe_load` → `data[key] = val` →
  `yaml.dump(sort_keys=False)` round-trip — identical to the existing
  `update_persona_skills`; **no new dependency**. Manifest comments are not
  preserved, matching that precedent.

- **ADR-077.6 — Generated reference doc.**
  `python -m sympose.config_reference` renders
  `docs/wiki/reference/configuration.md` (every knob: type, default, allowed
  values, live-vs-restart, description) from the schema.
  `tests/unit/test_config_schema.py` fails if the committed file drifts, so the
  page cannot silently rot.

## Consequences

- Adding a knob is one `Setting`. The reader (`get`), the editor (`/config`,
  `/persona set`), the validator (`[CONFIG_SET]`), the fresh-install seed, the
  Tab-completer and the wiki reference all follow from it.
- `get()`'s contract tightened: with every known key materialised, the `default`
  argument is consulted only for genuinely-absent keys (unknown, or `None`-
  default schema keys). No production caller relies on the old behaviour —
  ADR-077.3 removed them all.
- `config.py` lost ~40 lines (the `DEFAULT_CONFIG` dict and its deep-copy
  guard). `config_schema.py` and `config_reference.py` are separate so the
  schema module stays lean and the doc generator stays off the import path.
- Test suite 157 → 233 over the arc; the schema, its built defaults, the seed
  YAML, the reference doc, the completer lists and `set_persona_field` are all
  covered.
- Persona YAML comments are lost on a `/persona set` write. Accepted as
  consistent with `update_persona_skills`; a comment-preserving writer is a
  separate, dependency-gated decision if it ever matters.

## Implementation Note (2026-09-08 — schema ↔ `config.yaml` reconciliation)

The tracked `config.yaml` in the repo is itself a further declaration of
defaults. Two values disagreed with the schema; `config.yaml` was taken as
intent and the schema (and, while it still existed, `DEFAULT_CONFIG`) moved to
match:

| key | was (schema) | now |
| --- | --- | --- |
| `performance.local_request_timeout` | `60.0` | `120.0` |
| `session.exit_behavior.default_target` | `both` | `memory` |

## Alternatives rejected

- **Keep `DEFAULT_CONFIG` as a mirror, guarded by a drift-test** (the Tier 1–2
  state). A test caught disagreement but two hand-maintained lists still
  existed, and `DEFAULT_CONFIG_YAML` / `completer.CONFIG_KEYS` proved the
  pattern does not hold — mirrors rot the moment someone edits one side.
  Rejected for a genuine single source.
- **A settings library (`pydantic-settings`, `dynaconf`).** A runtime
  dependency, an env-var-first model that fits Sympose's "`/config set` writes
  `config.yaml`" loop poorly, and more surface than ~25 typed knobs warrant.
  The frozen-dataclass list is already declarative and yields the typed
  `coerce` / `validate` helpers for free.
- **Define the schema in a YAML/TOML data file, load it in Python.** Inverts the
  duplication — the file becomes the source and any Python-side typing
  duplicates it — and loses static importability. The dataclass list *is* the
  data file, in the language that consumes it.
- **`ruamel.yaml` for comment-preserving `/persona set` writes.** A new runtime
  dependency for a cosmetic gain. `update_persona_skills` already round-trips
  persona YAML with plain `yaml.dump`; matching it keeps one behaviour and zero
  new deps. Revisit only if manifest comments become load-bearing.
- **Rewrite the whole persona YAML from the loaded profile dict on `/persona
  set`.** The loaded dict is normalised and may omit manifest keys the loader
  does not round-trip; dumping it would drop them and reorder everything.
  The targeted `data[key] = val` on the parsed manifest touches only the one
  key.
- **Leave per-persona knobs to hand-editing.** No discoverability, no
  validation, and `[CONFIG_SET]` had no correct answer to give the model when it
  tried to set one. `/persona set` closes the loop `/config` opened.
