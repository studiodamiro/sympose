---
entry: 2026-09-17
created: 2026-09-17 23:15
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/sub-agents
  - sympose/grounding
  - reliability
  - code-review
---

# Sympose Engineering Log: Code-Audit Tier 4 — Patch the Heuristics, Then Fix the Root Cause

> **Date:** Thursday, September 17, 2026
> **Topic:** Closing Tier 4 of the fact-checked 34-finding code audit (see
> the [Tier 1](./2026-09-17_code-audit-tier1-quick-fixes.md),
> [Tier 2](./2026-09-17_code-audit-tier2-moderate-fixes.md), and
> [Tier 3](./2026-09-17_code-audit-tier3-structural-fixes.md) entries for
> the earlier fixes) — S2 and C6, the two "needs a rethink" findings.
> Explicitly done in two deliberate passes at the user's direction: patch
> both heuristics first and keep that patch as a standing defense-in-depth
> layer, then do the root-cause redesign underneath it.
> **Status:** Both done. Live-verified against a real local model
> end-to-end, not just unit tests.

## 1. The two findings

- **S2** — the "echo laundering" guard (`sub_agents.py`'s
  `_TEXT_GENERATING_COMMANDS` check) decides whether a `run_command`
  result counts as real grounding evidence by looking at the command's
  *leading word*. It only ever checked the whole command string's first
  word, so `ls; echo "fabricated citation"` sailed through — the echo is
  real, it's just chained behind an allowlisted no-op.
- **C6** — the "unsupported synthesis" overlap check
  (`_content_unsupported`) clamps its word-cluster ("shingle") size to
  `min(_SHINGLE_SIZE, len(source_words))`, ignoring the reply's own word
  count entirely, contradicting its own docstring's claimed "whichever
  side has fewer words" contract. Unreachable today only because the
  default `min_words` (15) already exceeds `_SHINGLE_SIZE` (4) — a
  lowered `min_words` would reproduce the exact empty-shingle false
  positive this function's docstring already documents as a *previously
  fixed* bug.

## 2. Pass one — patch both, kept as a standing layer

- **S2**: `NativeTools._segment_commands` (already ADR-073's own
  quote-aware splitter, used for the shell allowlist) gives every
  top-level command's own leading word. `_register_read`'s `run_command`
  branch now checks whether *any* segment is text-generating, not just
  the whole string's first word.
- **C6**: `n = min(cls._SHINGLE_SIZE, len(source_words), len(reply_words))`
  — the missing clamp, matching what the docstring already claimed.

Both regressions caught concretely: a Python one-liner reproducing the old
formula against the new test inputs confirmed the old code really would
have gotten each one wrong (`ls; echo ...` treated as safe; a genuine
3-word verbatim reply flagged as unsupported) before trusting the new
tests as meaningful. 2 new tests.

## 3. Pass two — the root-cause redesign

The instruction from here: don't just patch symptom by symptom — for
`run_command` specifically, stop inferring "was this real" from the
command's *text* at all, and check whether the output is *actually* real
instead. New `_grounded_command_files(named_files, tool_res, profile)`:
for each file the command named, fetch its real, current content via
`VaultManager.read_note` and confirm the command's reported output is
actually contained in it. Only the confirmed subset of named files ever
reaches `read_paths`/`tool_outputs` — not every file merely mentioned in
the command line, the same tightening `_content_unread`'s C7 fix already
made to path matching.

This closes the whole *class* of "fabricate `run_command`'s output" tricks
that a leading-word blocklist can only ever chase one instance at a time:
piping invented text through `base64 -d`, an inline `python3 -c
"print(...)"`, `awk 'BEGIN{...}'`, or anything else that isn't literally
`echo`/`printf`/`print` gains nothing now, since the output still has to
match something real. The blocklist from pass one stays in place as a
cheap, zero-I/O pre-filter — not because it's still the source of truth,
but because it's free and catches the common case before the (still
cheap, but non-zero) file-read verification runs.

`_register_read` gained a `profile` parameter, threaded through from both
call sites in the tool-calling loop (`parent_prof`, already in scope
there). 3 existing tests that called `_register_read` without a profile
needed a stubbed `VaultManager.read_note` and a profile argument added -
legitimate maintenance for an intentional signature change, not fallout.
4 new tests specifically target what pass one's fix alone couldn't catch:
a `python3 -c "print(...)"` fabrication (rejected, since the printed text
doesn't match the real file), the same command trusted when its output
*does* match real content, no-profile-means-nothing-can-be-verified, and a
named file that doesn't actually resolve isn't mistaken for a real match.

## 4. Live verification, not just mocks

Per standing practice for anything touching LLM-facing grounding
behavior: ran a real sub-agent task against `ollama/gemma4:e4b` (the same
model that originally surfaced this bug class, still installed locally)
against a real temporary vault on disk - not a mocked `_dispatch_tool_call`
this time.

Two real runs, both instructive:

- Asked it to read a note by a relative path it couldn't resolve. It
  genuinely reached for `run_command(echo '...')` on its own, unprompted,
  to explain it couldn't find the file — a live, naturally-occurring
  instance of exactly the pattern this whole tier defends against (not a
  contrived test case). Confirmed via logging around the real dispatch
  call that this got correctly excluded from grounding evidence.
- Asked it to run `cat` on the real note's absolute path directly. Logged
  every real tool call: `ok=True`, and the returned content was the exact,
  real file body every single time. After enough turns for the (known
  locally-flaky, per earlier journal entries) model to stop re-issuing the
  same command and actually answer, its final synthesis genuinely quoted
  the real note verbatim - and passed through both fixed grounding checks
  with no false positive, confirming the fix doesn't just catch
  fabrication, it correctly leaves a legitimately grounded answer alone.

(Aside, not part of this fix: chasing down why the first attempt's `cat`
calls seemed to fail turned up that macOS's `/tmp` → `/private/tmp`
symlink was silently defeating the run_command sandbox's directory-name
matching in my own test harness, and separately that this machine's
project-root `.env` sets a real `MASTER_VAULT_PATH` that a bare `python3
-c` one-liner picks up via dotenv if the env var isn't set explicitly
first. Neither is a sympose bug; both cost real debugging time before
being traced to the test setup rather than the fix, so noted here for
whoever next reaches for a quick one-liner against this codebase.)

## 5. Verification

810 backend tests pass (`.venv/bin/pytest`), up from 806 after pass one
and 802 before this tier — plus the live model run above, which no unit
test suite can substitute for on a change like this. No `ui/` changes.

## 6. What's left

E1 (`chat-panel.tsx`'s hand-rolled composer) remains deferred until the
chat feature itself is wired up, per the original report's own framing —
it's dead code today, and fixing it now wouldn't unblock anything. That
closes every other finding from the original 34-item report across all
four tiers.
