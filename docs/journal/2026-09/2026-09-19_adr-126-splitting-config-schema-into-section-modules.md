---
title: "ADR-126 — Splitting config_schema.py's SETTINGS Into Section Modules"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-126 — Splitting config_schema.py's SETTINGS Into Section Modules

- **Status:** Implemented.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

This is the first step of a larger effort (capability-tier model routing,
a vault-write concurrency guard, an external ingress endpoint, and an
opt-in LLM-Wiki layer — each its own following ADR) that needs to add
several new `Setting` declarations to `sympose/config_schema.py`. That file
was already 529 lines — 2.6x this project's own 200-LOC-per-file ceiling
(`.agents/rules/execution_guidelines.md`) — entirely because `SETTINGS`, a
single flat tuple of every runtime knob across six display sections
(`Performance & Streaming`, `Session & Memory`, `Runtime`, `Vault`,
`Sub-Agent Sandbox`, `Persona`), lived inline in the same file as the
lookup/validation logic (`get_setting`, `build_default_config`, `coerce`,
`validate`, …). Adding to it directly, as planned work already requires,
would compound an already-flagged violation rather than fix it — the same
"debt actively grows on every touch" problem ADR-125 addressed for
`vault.py`/`engine.py`, encountered here on first contact with this file
for unrelated new work.

## Decision

A pure, behavior-preserving mechanical split, following ADR-125's own
precedent (pure logic stays in the facade file; declarations move to
sibling modules; every external caller's import path is unchanged):

- **`sympose/config_setting.py`** (27 lines) — the `Setting` dataclass
  itself, moved to its own leaf module. This was necessary, not
  cosmetic: the per-section modules below need to construct `Setting(...)`
  instances, and `config_schema.py` needs to import their tuples back —
  leaving `Setting` in `config_schema.py` would have created an import
  cycle. Splitting the dataclass out first breaks that cycle.
- **`sympose/config_settings_performance.py`** (135 lines) — the
  `Performance & Streaming` section's 15 settings.
- **`sympose/config_settings_runtime.py`** (109 lines) — `Session & Memory`
  and `Runtime`'s combined 13 settings. (Originally planned as one file
  covering Performance + Session + Runtime together; that combination
  measured at 231 lines, over the ceiling this ADR exists to enforce, so
  Performance was split out into its own module instead — see
  Consequences.)
- **`sympose/config_settings_vault.py`** (137 lines) — `Vault`'s 9 settings
  and `Sub-Agent Sandbox`'s 4 settings.
- **`sympose/config_settings_persona.py`** (79 lines) — the 7
  persona-scoped (`scope="persona"`) settings.
- **`sympose/config_schema.py`** (127 lines, from 529) — keeps every piece
  of logic (`get_setting`, `default_for`, `global_settings`,
  `persona_settings`, `build_default_config`, `coerce`, `validate`,
  `_BY_KEY`), imports `Setting` and each section's tuple, and concatenates
  them into `SETTINGS` exactly as before. `Setting`, `SETTINGS`, and
  `SECTIONS` are re-exported unchanged from this file, so every existing
  caller (`config.py`, `bootstrap.py`, `profiles.py`, `commands.py`,
  `completer.py`, `actions.py`, `config_reference.py`, and
  `tests/unit/test_config_schema.py`) needed zero changes.

Each section module's own docstring states it "imports nothing from
`sympose` except the `Setting` dataclass itself" — preserving the original
file's no-cycle guarantee for `config.py`, which imports `config_schema` at
module load.

## Consequences

**Positive**

- `config_schema.py` dropped from 529 to 127 lines; all four new modules
  are under the 200-LOC ceiling (27/135/109/137/79).
- Zero external API change — `SETTINGS`, `SECTIONS`, `Setting`,
  `get_setting`, `default_for`, `global_settings`, `persona_settings`,
  `build_default_config`, `coerce`, `validate` all still importable from
  `sympose.config_schema` exactly as before.
- Full test suite (1059 tests, including `test_config_schema.py`'s
  `test_keys_unique`, `test_committed_doc_is_current`, and
  `test_completer_lists_track_the_schema`) passes unchanged — confirms the
  split really is behavior-preserving, not just structurally plausible.
- Clears the way for ADR-127 (capability-tier settings) and ADR-131 (LLM
  Wiki settings) to each add their own small section module instead of
  growing an already-oversized file further.

**Negative / costs**

- One more file to open when auditing "every setting in one place" — a
  developer now reads `config_schema.py`'s imports to find where a given
  section's declarations physically live, rather than scrolling one file.
  Mitigated the same way ADR-125 mitigated it for `vault.py`: the facade
  file (`config_schema.py`) remains the one stable import path every
  caller already uses; nothing about `from sympose.config_schema import
  SETTINGS` changed.
- The plan going into this (grouping Performance + Session + Runtime in
  one file) didn't survive contact with the actual line count — worth
  recording plainly rather than silently reshaping without a note, per
  this project's own documentation standard.

## Alternatives rejected

- **Leave `config_schema.py` at 529 lines and add the new capability-tier
  and wiki settings directly.** Rejected — this is precisely the
  "compounds an already-flagged violation while touching the file anyway"
  problem; deferring the split further only grows it.
- **A directory of YAML data files instead of Python `Setting` tuples.**
  Rejected — loses static typing and the `dataclass`'s field validation at
  import time, and the module's own docstring's "standalone, no cycle"
  guarantee is easiest to preserve with plain Python imports; a YAML
  loader would need its own cycle-free bootstrapping story for no real
  benefit over what dataclasses already give for free.
- **Group all six sections into two files by rough size instead of by
  display-section identity.** Rejected — section identity (`Performance`,
  `Vault`, `Persona`, …) is also the `/config` display grouping and the
  conceptual unit a future ADR will extend (e.g. ADR-127 adds a `Models`
  section, ADR-131 adds a `Wiki` section); splitting along that same seam
  keeps "add a new section" and "add a setting to an existing section"
  both obvious operations, at the minor cost of one extra file
  (`config_settings_performance.py`) once Performance alone proved too
  large to share a file with Session+Runtime.
