---
title: "ADR-121 — ruff as a Standing Dev Dependency, With a Narrow, Audited Rule Set"
created: 2026-09-14
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - tooling
  - code-quality
  - dependency
---

# ADR-121 — ruff as a Standing Dev Dependency, With a Narrow, Audited Rule Set

- **Status:** Accepted, implemented and verified 2026-09-14.
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering
  Partner)

## Context

A full manual + tooling audit of the Python backend (this same session) ran
`ruff` ad hoc — installed by hand into `.venv`, invoked with one-off
`--select` flags per category being investigated — across `sympose/` and
`app.py`. That pass, on top of `ruff format`, found and fixed:

- 3 real, previously-unnoticed bugs: duplicate execution of a repeated model
  action tag (`actions.py`), a shell-allowlist quote-parsing gap that could
  misclassify a disallowed command as safe (`native_tools.py`), and a
  rename-note self-link that never got updated (`vault.py`).
- A genuine shared-mutable-state bug in `SlackDaemon` — three per-instance
  caches were declared at class level, so every persona's `SlackDaemon`
  shared one dict/set instead of having its own.
- 35 exception handlers that silently discarded a real failure (bare
  `except: pass`/`continue`, no logging).
- 26 single-letter variable names (`l`) easily misread as `1`/`I`.
- 12 naive `datetime.now()` calls in daily-note/session-timestamp code,
  fixed with `.astimezone()`.

That's a strong case that this tooling is worth keeping, not a one-off. But
as of that pass, none of it was durable: `ruff` wasn't a declared dependency,
and the specific rule categories that produced the findings above existed
only as flags typed into a terminal. A fresh clone and a bare `ruff check`
would fall back to ruff's own bare-minimum default selection and reproduce
none of this.

## Decision

1. Add `ruff>=0.16.0` to `pyproject.toml`'s `[project.optional-dependencies]
   dev` extra, alongside `pytest`/`pytest-mock`.
2. Persist the exact rule categories that paid off this session in
   `[tool.ruff.lint]`, rather than a broad preset:
   - `E4`, `E7`, `E9` — pycodestyle import/statement issues (including
     `E741` ambiguous single-letter names) and syntax errors.
   - `F` — pyflakes (unused imports/variables, undefined names).
   - `C90` (`max-complexity = 10`) — mccabe complexity, the signal that
     scoped the 36-function manual correctness review this pass.
   - `S110`, `S112` — flake8-bandit's silent `except: pass`/`continue`.
   - `DTZ005` — flake8-datetimez's naive `datetime.now()`.
   - `RUF012` — ruff's own mutable-class-attribute-should-be-`ClassVar`
     check, which is what caught the `SlackDaemon` bug.
3. Ignore `E402` (module import not at top of file). This codebase
   deliberately uses `try: from x import y \n except ImportError: y = None`
   fallback blocks at the top of several files, followed by more real
   imports — a legitimate pattern this rule can't distinguish from a style
   lapse, not something worth flagging.
4. Fixed the 3 small pre-existing findings this narrower-but-real rule set
   surfaced on the current tree (two unused local variables in
   `sessions.py`/`vault.py`, one unused `Table` import in `ui.py`), so the
   standard starts from a clean baseline rather than shipping with an
   immediate backlog.

Deliberately **not** adopted in this decision, left for a future one if
warranted:

- `E501` (line length) — 328 hits on the current tree; this codebase has no
  established line-length convention and imposing ruff's default (88) now
  would be a large, unrelated reformatting decision bundled into a tooling
  ADR.
- The rest of `S` (flake8-bandit) beyond `S110`/`S112` — `S607`, `S605`,
  `S603`, `S311`, `S324`, `S104`, `S606`, `S602`, `S310` together add ~19
  more findings on the current tree that this session did not review one by
  one. `S110`/`S112` are in because they were reviewed and fixed; the rest
  would need the same treatment before being made a standing gate.
- The rest of `RUF` beyond `RUF012` — `RUF001`, `RUF005`, `RUF059` add ~17
  more unreviewed findings.
- `BLE001` (flake8-blind-except, "except Exception is too broad") — the
  audit specifically checked this category by hand and found the true
  positive rate low (~110 already-correct broad catches vs. a handful worth
  fixing); enabling it wholesale would flag mostly-correct code.
- Import sorting (`I`), docstring rules (`D`), and `ruff format` as a CI gate
  — none evaluated this session.

## Consequences

- `pip install -e .[dev]` (or equivalent) now gets `ruff` for anyone working
  on the codebase, with the same rule set that produced this session's
  findings — a fresh contributor reproduces the audit, not a diluted
  default.
- `.venv/bin/ruff check` on a clean tree reports exactly 36 errors, all
  `C901` — the already-reviewed complexity list from this session (3 fixed,
  33 confirmed sound). This is expected, known, accepted residual, not a
  regression; a new function crossing the same complexity threshold will
  show up alongside them.
- `ruff` is not wired into a pre-commit hook or CI gate by this decision —
  `.venv/bin/pytest` remains the one command this project's conventions
  require to pass before declaring work complete. Whether to make `ruff
  check`/`ruff format --check` a hard gate is a separate, future decision.
- Widening the rule set (the "deliberately not adopted" list above) is
  future work, gated on actually reviewing what it flags first — not
  something this ADR pre-authorizes.

## Alternatives rejected

- **Don't keep ruff at all; treat this session's audit as a one-off.**
  Rejected — the findings (3 real bugs, a real shared-state bug, 35 silenced
  failures) are exactly the kind of thing that creeps back in without a
  standing check, and the tool that found them costs nothing to keep (a
  single dev-only binary, no runtime footprint).
- **Enable ruff's full default rule set, or a popular broad preset.**
  Rejected for this decision — would introduce ~370 additional findings
  (mostly `E501` line-length) this session never evaluated, none of them
  tied to a verified problem. Zero-bloat applies to tooling adoption the
  same way it applies to dependencies: earn the rule, don't default to it.
- **Pin an exact ruff version instead of `>=0.16.0`.** Rejected — ruff's
  rule set is stable within a minor series and ADR-077-style config capture
  (the explicit `select`/`ignore` list above) is what actually needs to be
  pinned, not the binary; an exact pin would just mean manually bumping it
  for no benefit.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
