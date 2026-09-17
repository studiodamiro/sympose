---
entry: 2026-09-18
created: 2026-09-18 23:00
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - code-quality
  - testing
---

# Sympose Engineering Log: Closing Every mccabe Complexity (C901) Finding in sympose/

> **Date:** Thursday, September 18, 2026
> **Topic:** Following on from ADR-125's file-size split, a full sweep of
> `ruff check sympose/`'s remaining `C901` findings (`[tool.ruff.lint.mccabe]
> max-complexity = 10`, the rule ADR-121 put in place) — 27 functions across
> 16 files, ranging from complexity 11 to 151.
> **Status:** All 27 closed. `ruff check sympose/` reports zero `C901`
> findings. 1013 tests pass, up from 902 at the start of this sweep.

## 1. Why now, and why all of them

ADR-125 fixed `vault.py`/`engine.py`'s *size*; it didn't touch the
complexity findings sitting in the other 25 modules, most predating this
week's work entirely. Started with the two functions damiro asked about
directly (`extract_recall_subject`, then `vault_folders.py`/
`engine_turn_pipeline.py`'s own further splits), then the worst 4 of the
remaining 27 by raw complexity score, then — on explicit instruction
("lets close all these lower-risks once and for all") — every finding
left standing, not just the worst offenders.

Two extraction patterns did almost all of the work:

- **Tiered-case extraction** — a function with sequential distinct cases
  (a long `if`/`elif` ladder, or several unrelated concerns bolted into
  one body) becomes a thin orchestrator calling one small, independently
  named helper per case.
- **Data-driven dispatch tables** — a function branching on a string key
  (a slash command, an action tag, a completion command word) becomes a
  `dict[str, Callable]` built once at module load from top-level handler
  functions, so the dispatcher itself is a `.get()` plus one `if`, and
  each handler's own complexity is scored independently rather than
  rolled into the dispatcher's total.

## 2. The four worst offenders

**`commands.py`'s `intercept` (complexity 151).** The single largest
finding in the codebase, by a wide margin — one function handling every
slash command via ~22 nested closures. Confirmed empirically (a
throwaway `/tmp/mccabe_test.py` with five trivial nested `def`s, each
just `return 1`, checked against `max-complexity=1`) that mccabe adds at
least +1 per nested function definition to the *enclosing* function's
score, regardless of how trivial that nested function's body is — so no
amount of shrinking each closure's body would have fixed this alone; the
closures themselves had to stop being nested. Rewritten as ~30 top-level
`_cmd_*(engine, handle, clean_input, profile)` handlers (uniform
signature), sub-case helpers for the five most complex commands
(history, config, model, vault ops, skills), and a `_ROUTES: list[tuple[
Callable[[str], bool], Callable]]` built once at module load.
`CommandInterceptor.intercept` is now just a loop over `_ROUTES`, then an
`@mention` check, then the unknown-command fallback. `test_commands.py`
had thin prior coverage; rewritten with 67 tests giving every route real
assertion coverage, including one documenting a genuine pre-existing
quirk (`/model find` with no query string falls through to the
model-*override* branch rather than the `find` subcommand's own usage
message, because the dispatch only recognizes `sub_lower.startswith(
"find ")` — with a trailing space).

**`actions.py`'s `execute_actions` (66) and `parse_action_tags` (12).**
Same dispatch-table shape, applied to action-tag handling instead of
slash commands: a new `_ActionContext` dataclass bundles the per-call
state every `_handle_*` tag handler needs (profile, vault folder,
sub-agent depth, accumulated badges, …) so each handler can share one
`(ctx, inner) -> str` signature, looked up via `_tag_routes()` against a
`(gate_fn, handler_fn)` pair per tag. All 52 pre-existing
`test_actions.py` tests passed unchanged — the extraction was
byte-for-byte behavior-preserving.

**`server.py`'s `create_app` (58).** The one genuinely structural puzzle
of the sweep. An initial pass tried the obvious FastAPI idiom —
`APIRouter()` per route group, `app.include_router(...)` — and broke
`test_server.py` outright: this install's FastAPI (0.141.1) wraps an
included router's routes in an internal `_IncludedRouter` object instead
of flattening them into `app.routes` as plain `APIRoute`s, and several
existing tests iterate `app.routes` expecting flat `.path`/`.methods`
attributes. Reverted to registering routes directly on `app` from four
smaller top-level functions (`_register_system_routes`,
`_register_vault_read_routes`, `_register_vault_write_routes`,
`_register_vault_trash_routes`) instead — which also turned out to be
the actual fix for the complexity finding itself, since mccabe's
per-nested-def rollup (see above) meant `create_app`'s complexity came
from the sheer *count* of route handlers defined inside it, not their
individual logic; splitting the count across four functions was the
only fix that could work, independent of the FastAPI-version surprise.

**`cli.py`'s `run` (52).** The interactive REPL's main loop, tiered-case
extraction into `_resolve_active_model`, `_read_user_input`,
`_maybe_switch_persona`, `_run_command_turn`, `_stream_chat_reply`,
`_run_chat_turn`, and several smaller rendering helpers — `run()` itself
reduced to the loop skeleton calling each in sequence. Had zero prior
test coverage; added 37 new tests in a new `test_cli.py`, including a
scripted end-to-end test that drives `run()` to completion via a
sequence of `_read_user_input` mock responses. Needed a
`TerminalInterface.__new__(TerminalInterface)` construction (bypassing
`__init__`, which needs a live config/engine) to test methods in
isolation — the same pattern already used for `SlackDaemon` in
`test_slack.py`.

## 3. Everything else

The remaining 23 findings, in descending complexity order, all followed
the same two patterns with no further surprises:

- `completer_rules.py`'s `command_completions` (34) — dispatch table,
  had zero prior coverage; `test_completer.py` grew from 6 to 38 tests.
- `native_tools.py`'s `execute` (28) — dispatch by tool name.
- `vault_search.py`'s `search_structured` (23).
- `ui.py`'s five worst functions (23, 14, 13, 12, 12) —
  `interactive_vault_browser`'s main loop became a state machine
  returning `(view_mode, current_index, should_stop)` tuples from two
  extracted turn-handlers; `MultiSectionPanel.__rich_console__`'s four
  sub-generators use `yield from`. `test_ui.py` grew from 8 to 29 tests.
- `slack.py`'s `_process_message` (20) — tiered-case extraction;
  `test_slack.py` grew from 6 to 29 tests.
- `sub_agents.py`'s `_build_sub_agent_context` (19).
- `vault_write.py`'s `delete_folder`, `rename_note`, and
  `resolve_existing_note` (14, 14, 12).
- `vault_tree.py`'s `build_tree` (13).
- `vault_links.py`'s `build_backlink_index` (13).
- `bootstrap.py`'s `ensure_workspace` (13).
- `vault_manifest.py`'s `ensure_fresh` (12).
- `config_schema.py`'s `coerce` (11).

`vault_recall.py`'s `extract_recall_subject` (13, the item damiro asked
about first) and the `vault_folders.py`/`engine_turn_pipeline.py` splits
that followed are covered under ADR-125's own log, since they doubled as
that ADR's phase-5/phase-2 file-size work.

## 4. The standing test-coverage rule this sweep set

Partway through, offered to add tests as a follow-up versus moving
straight to the next item; damiro's answer — "it should be our
standard" — means every future large refactor in this project ships
with real, permanent pytest coverage for its newly-extracted paths, not
a throwaway manual smoke test. Applied for the rest of this sweep
wherever prior coverage was thin or absent (`cli.py`, `commands.py`,
`slack.py`, `completer_rules.py`, `ui.py`), not only where it happened
to be pointed out.

## 5. Verification

```
.venv/bin/ruff check sympose/   # All checks passed! (zero C901 findings)
.venv/bin/pytest -q             # 1013 passed, 1 warning (up from 902)
```

No behavior changes were intended or found anywhere in this sweep —
every extraction preserved exact original logic; the diffs are pure
reorganization plus new test files.

## 6. Disclosed, not fixed: pre-existing E741 findings

A full-repo `ruff check .` (broader than this sweep's `sympose/` scope)
surfaces 32 pre-existing `E741` ("ambiguous variable name `l`") findings
across 12 test files (`tests/conftest.py`, `test_actions.py`,
`test_auth.py`, `test_bootstrap.py`, `test_config.py`,
`test_native_tools.py`, `test_profiles.py`, `test_server.py`,
`test_sessions.py`, `test_tls.py`, `test_vault_links.py`,
`test_vault_manifest.py`) — none touched this sweep, and never part of
the 27-item `C901` punch list. Left alone rather than folded in
silently; a candidate for its own small follow-up pass if damiro wants
it.
