---
entry: 2026-09-18
created: 2026-09-18 15:40
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/grounding
  - sympose/reliability
---

# Sympose Engineering Log: A Correct "What's In This Folder?" Answer Was Being Thrown Away

> **Date:** Friday, September 18, 2026
> **Topic:** While live-verifying ADR-123's new folder-kind-signal feature
> (see [2026-09-18_adr-123-automatic-folder-kind-signals-from-digest-fields.md](./2026-09-18_adr-123-automatic-folder-kind-signals-from-digest-fields.md)),
> damiro asked `samantha` what her `Movies/` folder keeps. On the local
> model, a genuinely correct, well-grounded answer was silently discarded
> and replaced with a raw note dump, prefixed "That's not what I actually
> have." Damiro caught this immediately from the reply's own framing and
> pushed on it until the actual mechanism was found.
> **Status:** Fixed. Live-verified against both a local and a cloud model.

## 1. Root cause

`PersonaEngine._apply_grounding_and_stream_result` (`engine_turn_grounding.py`)
runs `_vault_ctx_title_missing` (`engine_grounding.py`) whenever real vault
content was handed to the model this turn under `verify_ctx`. That check's
rule: if the reply's text never contains the real note's own filename stem
anywhere, treat the reply as untrustworthy and swap it for the raw note
content instead.

That rule was built (2026-09-15 sweep, §3.34) for a real, confirmed
failure: handed one specific real note, `gemma4:e4b` would narrate a
plausible-sounding but entirely fictional title instead of referencing
what it actually had. For that shape of question - "tell me about this
note" - requiring the real title to appear somewhere in the reply is a
sound test.

ADR-123 added a second, different shape of question the check was never
updated for: "what kind of things live in this folder?" A correct answer
to that generalizes across many notes ("detailed film entries with
ratings, genres, and reflections") and has no reason to name any single
one of them. `_vault_ctx_title_missing` can't tell these two shapes
apart - it only knows "was a title mentioned or not" - so it flagged a
correct, well-grounded folder-level answer exactly the same way it would
flag a genuinely fabricated one, and the turn's own downstream code
overwrote a good answer with a raw note dump under an accusatory framing
("That's not what I actually have") that wasn't even true - the model
did have and did correctly use what it was handed.

## 2. The fix

Two changes, kept deliberately separate since they fix different things:

- **Stop the misfire.** `get_folder_digest` (`vault_folders.py`) already
  produces a structurally distinct payload for this second question shape
  - a multi-note, metadata-only digest under a unique
  `### High-Density Folder Digest` header, never an `Exact Content` single
  note. `_vault_ctx_title_missing` now returns `False` outright whenever
  that header is present, before doing any title-matching at all. This is
  a structural check (which retrieval function produced this content), not
  a guess about the question's wording, so it can't be tricked by
  phrasing the way a keyword gate could.
- **Soften the wording for when it's still legitimately needed.** For an
  actual single-note mismatch (the check's original, still-valid use
  case), the swapped-in text no longer asserts "That's not what I
  actually have" - a claim of certainty the check has never actually been
  able to back up; it only knows a title wasn't mentioned, not why. It now
  reads "I couldn't fully verify that against what's actually on file, so
  here's the exact note instead" - same swap, same zero-extra-round-trip
  behavior (this is still a single, static text substitution after the
  one model call already made, not a second inference pass or a request
  back to the model), just accurate about what was actually determined.

Discussed directly with damiro before building: he pointed out that
"there's a movie called *Dune*"-style answers (citing one example
naturally) would already read better than the discard-and-replace
behavior, and asked why not just have the model always cite something.
Rejected that specific framing as a fix on its own - forcing a citation
into a legitimately general answer optimizes for passing an internal
check rather than answering well, and it's a soft prompt instruction the
weakest model (the one already failing this check) is also the most
likely to skip. The comparison to how citation-heavy products (Perplexity,
Bing/Copilot) handle this held up on inspection: they check whether a
citation points to something real, and treat single-document Q&A and
multi-document summarization as different tasks with different
verification rules - which is exactly the structural distinction
(`High-Density Folder Digest` marker) applied here, not a novel approach.

## 3. Verification

New tests: `test_folder_digest_answer_is_exempt_even_with_no_titles_mentioned`
in `tests/unit/test_engine.py` (`TestVaultCtxTitleMissing`). Full suite:
1054 passed, `ruff check .` clean.

Live, against the real vault, both directions on both a local
(`ollama/gemma4:e4b`) and cloud (`gemini/gemini-3.6-flash`) model:

- **The bug case, now fixed:** "what does my Movies folder keep?" - local
  model now answers directly and correctly ("Your `movies/` folder seems
  to function as a logbook or review collection for films you've
  watched... combining standard metadata... with much longer, more
  reflective analysis"), no discard, no override. Cloud model was
  unaffected either way (it happened to already cite the sample note's
  title, so the old check never misfired on it) and continues to answer
  well.
- **The guard still doing its real job:** a coincidental, unrelated
  single-note match (a session-log note, not actually about `People/`)
  still correctly triggered the swap - now shown as "I couldn't fully
  verify that against what's actually on file, so here's the exact note
  instead," not an accusation.

## 4. Why this matters beyond the one bug

This is the second time in three days (after the 2026-09-17 ritual-
continuation fix) that a grounding-enforcement mechanism built for one
retrieval shape turned out to misjudge a second shape added later. The
durable lesson isn't "check title citation differently" - it's that any
future retrieval shape (ADR-123.5's referent-matching, or whatever comes
next) needs to be checked against every *existing* enforcement mechanism
that inspects `vault_ctx`/replies, not just built and tested in isolation
against its own new tests.
