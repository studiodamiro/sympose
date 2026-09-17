---
entry: 2026-09-17
created: 2026-09-17 23:45
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/grounding
  - sympose/persona-memory
  - reliability
---

# Sympose Engineering Log: The Random-Pull Ritual Didn't Carry Across Turns

> **Date:** Thursday, September 17, 2026
> **Topic:** Damiro flagged a live Samantha transcript (on a manual
> `ollama/gemma4:e4b` override) where the first round of "let's play our
> favorite game" (a random-note-pull ritual, per §3.31 of the
> [2026-09-15 sweep](./2026-09-15_samantha-live-testing-bug-sweep.md)) was
> correctly grounded, but the very next "let's do another one" produced a
> vague fabricated reflection and then a fully invented title ("Echoes of
> August") for a note it was never given.
> **Status:** Fixed. Live-verified against the real local model, not just
> unit tests.

## 1. Root cause

`chat_stream` fetches a real note for the ritual only when
`ProfileManager.find_relevant_memory_fact` finds a memory-fact bullet whose
words closely overlap the *current* message (`overlap >= 2` tokens, per
§3.30 of the same sweep). "Let's play our favorite game, let's do Movies"
overlaps a fact like "Damiro's favorite game is pulling a random note..."
on "favorite"/"game" and fires correctly. "Let's do another one" shares
zero tokens with that fact - no keyword overlap, so `mem_hit` is `None`,
`resolve_ritual_random_pull` never runs, and nothing real gets injected
for that turn. Two things happen next, both with no real content in play:

- The existing anti-fabrication net (`_VAULT_CLAIM_RE`) only fires on
  specific phrasings ("your entry", "in your vault", a `.md` path). Samantha's
  actual wording ("this one is from the People directory") never matches
  any of them, so it sails through unchecked.
- The model free-associates a plausible-sounding reflection, then a fully
  invented title once asked for specifics.

The session's own carried-over vault context
(`PersonaEngine.active_vault_ctx`) doesn't help either: it exists but only
re-serves the *same* single note from a prior turn, refreshed from disk -
useful for "tell me more about that one," useless for "give me a
different one," which a ritual round explicitly wants.

## 2. The fix: remember the ritual is active, not just the last note

A new per-handle `PersonaEngine.active_ritual: dict[str, bool]`, following
the exact lifecycle of `active_vault_ctx` (set on a successful pull,
cleared on a distinct fresh vault ask via `has_recall_intent`, cleared on
`/reset`). A new static, independently-testable
`PersonaEngine._ritual_pull_due(mem_hit, ritual_active, clean_input)`
decides whether this turn should (re)fetch a real note: a fresh `mem_hit`
that itself describes the ritual is sufficient on its own (unchanged
behavior); otherwise, an already-active ritual is sufficient too, *unless*
this message is itself a distinct, explicit vault ask (`has_recall_intent`)
- a genuine topic change ends the ritual rather than continuing to hijack
unrelated turns. The two paths are deliberately independent, not
either/or: a coincidental, unrelated `mem_hit` on a continuation turn must
not cancel an already-active ritual.

When `_ritual_pull_due` is true and this turn doesn't already have its own
full-body context, `VaultManager.resolve_ritual_random_pull` runs again,
so a genuinely random note gets picked every round - the existing
`_vault_ctx_title_missing` / `_vault_ctx_citation_mismatch` checks (already
proven against this exact model's exact failure mode) then apply
automatically, with no new phrase list anywhere.

One ordering bug caught only by testing live end-to-end, not unit tests:
the pre-existing single-note carry-over (`active_vault_ctx.get(h_key)` →
`refresh_note_context`) ran *before* the new ritual check and already
satisfied its "is this turn's context full-body" guard by re-serving the
*same* stale note - so the ritual block never got a chance to run at all.
Fixed by skipping that carry-over specifically while a ritual is active,
so the ritual block is the one that decides what this turn gets.

## 3. What was rejected

Two adjacent ideas came up in discussion and were deliberately not built:

- **A per-folder "definition" prompt** (e.g. telling the model up front
  that `People/` holds real contact records, not narrative). This would
  help *interpretation* of content the model actually has, but the bug
  here was that no content was fetched at all on the continuation turn -
  a folder description doesn't cause a fetch to happen, and it would need
  hand-written upkeep per vault, working against Sympose shipping useful
  out of the box on any vault.
- **Widening `_VAULT_CLAIM_RE`** to catch more of Samantha's own phrasing
  ("this one is from the ... directory"). Rejected as more of the same
  enumerable-phrase-list pattern; the fix above makes the phrase-list catch
  unnecessary for this case by ensuring real content is present to check
  against in the first place, rather than trying to guess every way a
  model might describe an invented one.

## 4. Live verification

Built a temporary throwaway vault (`Movies/` with three notes,
`resolve_ritual_random_pull` call-tracked via a thin wrapper) and ran two
real turns against `ollama/gemma4:e4b` end-to-end through
`PersonaEngine.chat_stream` - no mocked `litellm.completion`.

- Turn 1 ("let's play our favorite game...Movies...") pulled `Paddington.md`
  and reflected on it correctly.
- Turn 2 ("let's do another one" - zero keyword overlap with the memory
  fact) pulled a genuinely different note (`Amelie.md`), confirmed via the
  call tracker rather than luck of the random draw. The model then
  independently spawned its own sub-agent to double check via
  `run_command`/`read_file`, and its final reply quoted the real note
  verbatim.

Before the ordering fix, the same test showed turn 2 silently re-serving
turn 1's note (`Paddington.md` again) instead of a fresh pull - the exact
regression the ordering fix above closes.

## 5. Verification

818 backend tests pass (`.venv/bin/pytest`), up from 810 - 8 new unit
tests for `_ritual_pull_due` (fresh match, unrelated match, carry-over
continuation, no active ritual, coincidental unrelated `mem_hit` not
suppressing an active ritual, a distinct vault ask ending one) and 2 for
`active_ritual` following `active_vault_ctx`'s reset lifecycle - plus the
live end-to-end run above, which no unit test substitutes for on a change
like this. No `ui/` changes.
