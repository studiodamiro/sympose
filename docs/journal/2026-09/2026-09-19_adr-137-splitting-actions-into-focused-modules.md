---
title: "ADR-137 — Splitting actions.py Into Focused, Under-200-LOC Modules"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-137 — Splitting actions.py Into Focused, Under-200-LOC Modules

- **Status:** Implemented. Same `code-review` pass that flagged
  `vault_write.py` (ADR-136) also flagged `sympose/actions.py` at 807
  lines (~4x the 200-LOC ceiling). Addressed immediately after ADR-136
  landed, same session, per damiro's explicit "let's do this once and for
  all" — both files named in the original review closed out together.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`actions.py` holds one class, `ActionProcessor`, dispatching autonomic
model action tags (`[WRITE_NOTE]`, `[SPAWN_SUB_AGENT]`, `[CONFIG_SET]`,
…) through a `(gate, handler) `table (`_tag_routes`) keyed by tag name.
Each tag's `_handle_*` method is already independently named and mostly
self-contained, clustering naturally by theme: vault/canvas writes,
sub-agent spawning, persona lifecycle, and a handful of standalone tags
(REMEMBER, SEARCH, CONFIG_SET). The class-level tag-parsing engine
(`parse_action_tags`, `strip_action_tags`, the bracket-matching helpers)
is independent of what any handler does with a parsed tag.

Unlike `vault_write.py` (ADR-136, plain functions) but like `vault.py`/
`engine.py` (ADR-125), this *is* a class, and several `@classmethod`
handlers call sibling methods via `cls.` (`_handle_spawn_sub_agent` calls
`cls.execute_actions`/`cls.strip_action_tags`; `_tag_routes` itself
returns a dict of `cls._handle_*` references) — the same mixin-class shape
ADR-125 used for `PersonaEngine`/`VaultManager`.

One real constraint the split had to respect: `_PSEUDO_TAG_RE`'s own
construction is `"|".join(TAG_NAMES)`, evaluated at *class-body-execution
time*, not inside a method. That only resolves against names already
bound in the same class body's local namespace — inheritance doesn't help
there the way it does for a name looked up inside a method body (e.g.
`cls.TAG_NAMES`, which works fine through the MRO). So `TAG_NAMES` and
`_PSEUDO_TAG_RE` had to stay together in whichever file defines the final
`ActionProcessor` class, not move into a mixin.

## Decision

Five handler mixins plus a tiny shared context module, assembled into
`ActionProcessor` in a slimmed-down `actions.py`:

- **`actions_context.py`** (46 lines) — `_ActionContext`, moved to its own
  module so every mixin below can type-hint it (`ctx: "_ActionContext"`,
  under `TYPE_CHECKING`) without importing `actions.py` itself, which
  would cycle back (`actions.py` assembles `ActionProcessor` from these
  same mixins).
- **`actions_parsing.py`** (126 lines) — `ParsingMixin`: `_op_failed`, the
  bracket/prefix-matching helpers, `parse_action_tags`, `strip_action_tags`,
  and the four tag-shape gates (`_has_pipe`, `_non_empty`, …).
- **`actions_notes.py`** (147 lines) — `NotesActionMixin`: WRITE_NOTE,
  APPEND_NOTE, DAILY_NOTE, READ_NOTE/VIEW_NOTE, WRITE_CANVAS.
- **`actions_sub_agent.py`** (125 lines) — `SubAgentActionMixin`:
  SPAWN_SUB_AGENT and its loadout/constraint/report helpers.
- **`actions_persona.py`** (145 lines) — `PersonaActionMixin`:
  CREATE_PERSONA, DELETE_PERSONA, and their manifest-parsing helpers.
- **`actions_misc.py`** (108 lines) — `MiscActionMixin`: REMEMBER,
  SEARCH/WEB_SEARCH, CONFIG_SET.
- **`actions.py`** (227 lines, from 807) —
  `ActionProcessor(ParsingMixin, NotesActionMixin, SubAgentActionMixin,
  PersonaActionMixin, MiscActionMixin)`, holding `TAG_NAMES`,
  `MAX_ACTION_DEPTH`, `_LEGACY_TAG_RE`, `_PSEUDO_TAG_RE`, `_tag_routes`,
  and `execute_actions` itself. The one file that didn't clear 200 lines
  — see Consequences.

Three `NotesActionMixin` handlers (`_handle_write_note`,
`_handle_append_note`, `_handle_daily_note`, `_handle_write_canvas`) were
converted from `@staticmethod` to `@classmethod` so `cls._op_failed(...)`
can reach `ParsingMixin`'s method through `ActionProcessor`'s MRO — the
original code called `ActionProcessor._op_failed(...)` directly by class
name, which only worked because everything lived in one file; the same
cross-mixin pattern `_handle_spawn_sub_agent` already used for
`cls.execute_actions` generalizes cleanly here.

## Consequences

**Positive**

- `actions.py` dropped from 807 to 227 lines; five of the six new modules
  cleared the 200-LOC ceiling.
- Zero external API change — every dependent file (`engine_grounding.py`,
  `engine_turn_grounding.py`, `engine_turn_finalize.py`, `slack.py`,
  `sympose/__init__.py`, `tests/unit/test_actions.py`) imports only
  `ActionProcessor`, unchanged.
- Full test suite passes (1169 tests) after one necessary, deliberate
  fix: `test_actions.py` monkeypatches several dependencies by string
  path (e.g. `"sympose.actions.VaultManager.write_note"`) — these patch a
  *method* on a shared class/singleton object, so any valid import path
  to that same object works identically. `actions.py` now re-exports
  `VaultManager`/`SubAgentEngine`/`SubAgentTask`/`NativeTools`/
  `config_manager` (documented inline as intentionally-unused,
  monkeypatch-compatibility-only imports) rather than requiring 26 test
  call sites to be rewritten to the new per-mixin import paths — verified
  safe first by confirming every one of those patches targets a method,
  never a full top-level name replacement (which *would* have required
  the per-mixin path instead).

**Negative / costs**

- `actions.py` (227 lines) still exceeds the 200-LOC guidance by a modest
  margin. `TAG_NAMES`/`_PSEUDO_TAG_RE`'s class-body-time coupling (see
  Context) means they, `_tag_routes`, and `execute_actions` all have to
  stay in the file defining the concrete `ActionProcessor` class; the
  file's own docstring documenting that constraint was judged worth
  keeping in full rather than trimmed to force the count down.
- Total line count across all `actions*.py` files grew from 807 to 924 —
  expected, the same per-file docstring/import overhead ADR-125/ADR-136
  both observed.
- The re-exported-for-monkeypatch-compatibility imports in `actions.py`
  look unused to a casual reader (and to `ruff` without the inline
  `# noqa: F401` markers) — mitigated with an explicit comment explaining
  why, so a future cleanup pass doesn't remove them and silently break
  `test_actions.py`.

## Alternatives rejected

- **Leave `actions.py` at 807 lines as accepted debt.** Rejected for the
  same reason as ADR-136 — explicitly flagged by the review that
  surfaced it, and damiro's stated preference this round was closing both
  flagged files out together, not deferring either.
- **Rewrite `test_actions.py`'s ~26 monkeypatch call sites to the new
  per-mixin import paths instead of re-exporting in `actions.py`.**
  Considered — arguably more "honest" about where each dependency now
  lives, but touches far more surface area (26 call sites across one
  test file) for no behavioral difference, since every one of those
  patches targets a shared object's method, not a rebound name. Re-exporting
  costs five lines and a comment; rejected the larger diff for equivalent
  safety.
- **Move `TAG_NAMES`/`_PSEUDO_TAG_RE` into `actions_parsing.py` anyway,
  accepting that `ActionProcessor`'s own class body would need to
  re-derive `_PSEUDO_TAG_RE` from `cls.TAG_NAMES` in `__init_subclass__`
  or similar.** Rejected — solving a class-body-timing constraint with
  metaclass-adjacent machinery is exactly the kind of complexity this
  refactor exists to reduce, not add, for a saving of roughly 10 lines.
