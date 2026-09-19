---
title: "ADR-138 — A Structural Write Gate for Lint-Only wiki_lint Personas"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-138 — A Structural Write Gate for Lint-Only wiki_lint Personas

- **Status:** Implemented. The last open item from the same-day full
  codebase review (Tier 2's deferred finding), settled before committing
  that review's work, per damiro's "let's settle lint_auto_fix now before
  committing everything then we push."
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

ADR-134 gave `lint_auto_fix` a real prompt-level mechanism (the `Wiki Lint
Mode` block), but explicitly rejected hard-coding a check into
`WRITE_NOTE`/`APPEND_NOTE`: those tags serve many skills, and a persona
that also carries `wiki_ingest` has an entirely legitimate reason to write
into `wiki.root` — indistinguishable, at the tag-handler layer, from a
`wiki_lint` auto-fix. Building the bookkeeping to tell those apart for
every persona was judged bigger than that ADR's scope.

Revisiting it now: that ambiguity only exists for a persona that carries
*both* skills. A persona whose `skills` list has `wiki_lint` but not
`wiki_ingest` has no other sanctioned reason to touch a page under
`wiki.root` at all — every `WRITE_NOTE`/`APPEND_NOTE` such a persona could
emit there, other than an append to the log file, is by construction a
would-be lint auto-fix. For exactly that narrower case, the ambiguity ADR-134
was worried about doesn't apply, and a mechanical, code-level check is both
safe and correct — no new per-turn bookkeeping needed, no risk to
`wiki_ingest`'s normal writes.

## Decision

`sympose/wiki_lint_support.py` gains `wiki_lint_write_gate(*, skills,
lint_auto_fix, wiki_root, log_file, rel_path) -> str | None` — a pure
function, tested the same way `wiki_pages`/`orphan_pages` already are.
Returns `None` (proceed as normal) unless all of: the persona's `skills`
include `wiki_lint`, exclude `wiki_ingest`, `lint_auto_fix` is off,
`wiki.root` is set, and `rel_path` falls under it but isn't the log file —
in which case it returns an `_op_failed`-recognized `"Security Error: ..."`
string, the same denial vocabulary `write_note`/`append_note` already use
for a sandbox violation.

`sympose/actions_notes.py`'s `_handle_write_note`/`_handle_append_note`
call this gate *before* `VaultManager.write_note`/`append_note` — a real
block, not just an honest badge after the fact:

```python
result = _wiki_lint_gate(ctx, rel_path) or VaultManager.write_note(ctx.profile, filename, content)
```

`_wiki_lint_gate` (a small adapter in `actions_notes.py`) and
`_rel_note_path` (deduplicating the `vault_folder`/`.md`-suffix
computation both handlers already needed) are the only additions to that
file, which stays at 165 lines, under the 200-LOC ceiling.

A persona with both `wiki_lint` and `wiki_ingest` is left entirely to the
existing prompt-level `Wiki Lint Mode` block, unchanged from ADR-134 — the
ambiguity there is real and this ADR doesn't attempt to resolve it.

## Consequences

**Positive**
- Closes a real gap: a lint-only persona's report-only mode no longer
  depends solely on the model choosing to obey its own system prompt.
- Zero risk to `wiki_ingest`'s normal operation — the gate is inert for
  any persona that carries it, exactly the case ADR-134 was protecting.
- Reuses the existing denial vocabulary (`Security Error: ...`,
  `_op_failed`) rather than inventing a new one — the badge a user sees is
  indistinguishable in tone from any other sandbox denial.
- 16 new tests (10 pure-function cases in `test_wiki_lint_support.py`, 7
  integration cases through `ActionProcessor.execute_actions` in
  `test_actions.py`). Full suite: 1185 passed (1169 + 16), ruff clean.

**Negative / costs**
- Does not close the gap for a persona carrying both `wiki_lint` and
  `wiki_ingest` — that ambiguity is real and unchanged from ADR-134. A
  user who wants the hard guarantee for such a persona today has to split
  it into two personas (one lint-only, one ingest-only) instead.
- One more read for anyone tracing a WRITE_NOTE/APPEND_NOTE call: the gate
  check now sits ahead of the `VaultManager` call, not just the sandbox
  check already inside it.

## Alternatives rejected

- **Block every write under `wiki.root` when `lint_auto_fix` is off,
  regardless of which other skills the persona carries.** Rejected — this
  is exactly the collateral damage ADR-134 identified: it would silently
  break `wiki_ingest`'s own legitimate writes for any persona configured
  with both skills, the normal way a user would set up "one persona that
  both files sources and lints the result."
- **Build per-turn bookkeeping (e.g., a "current skill in play" field on
  `_ActionContext`) so any persona's lint-mode writes could be identified
  precisely.** Rejected as the same disproportionate machinery ADR-134
  already turned down, for a case (dual-skill personas) that a narrower,
  zero-bookkeeping fix already handles for the unambiguous majority.
- **Leave it prompt-only, matching ADR-134's original scope exactly.**
  Rejected on reflection — the `wiki_lint`-without-`wiki_ingest` case has no
  ambiguity at all, so declining a free, safe, structural fix there just
  because a harder adjacent case remains unsolved would be leaving
  low-risk debt in place for no benefit.
