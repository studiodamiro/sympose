---
entry: 2026-09-17
created: 2026-09-17 09:40
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/vault
  - sympose/grounding
  - sympose/sub-agents
---

# Sympose Engineering Log: Sub-Agent Guard Against Unsupported Synthesis (extends e80674b)

> **Date:** Thursday, September 17, 2026
> **Topic:** A live transcript across two backends (ollama/gemma4:e4b and
> gemini/gemini-3.6-flash) showed the e80674b sub-agent grounding fix holding for
> its own target shape (naming a specific note it never read) but not for a
> subtler one: a confident conclusion stitched from real tool calls, with no
> verbatim tie back to any of them. Built `_content_unsupported`, live-verified
> it on both backends, then live-verified a pass-through case, which surfaced a
> second real gap — a fabrication "laundered" through a self-authored shell
> command — fixed and re-verified the same session.
> **Participants:** damiro (Lead Architect), Claude (Sonnet 5) (Engineering Partner)

## Symptom

Live session, `@samantha` on `gemini/gemini-3.6-flash`: asked "dont you remember
our favorite game?", the `vault_recall` sub-agent ran several `grep`/`read_file`
calls, then answered:

> "Of course I remember—our favorite game is random note discovery ('surprise
> me')! It's where we pull up a random note or movie from your vault..."

Confident, well-formed, and unverifiable — nothing in that sentence is a
verbatim quote of anything the tool calls actually returned. `_content_unread`
(e80674b) didn't fire, because it only checks synthesis text that *names a
specific vault note path* against what was actually read. This reply names no
path at all — it's a conclusion, not a citation. Both e80674b's own docstring
and the 2026-09-07 `_vault_ctx_citation_mismatch` docstring already flagged
this "prose-only residual gap": catching an unsupported *inference* (vs. an
unsupported *citation*) looked like it would need comparing meaning, which
means a second model call, against the round-trip-frugality mandate.

## Fix (`sympose/sub_agents.py`)

Structural, not semantic: the sub-agent system prompt already requires quoting
note text verbatim, so checking for verbatim word-overlap enforces an existing
contract rather than inventing a new one — no second model call needed.

- `_content_unsupported(text, tool_outputs)`: true when `text` is substantive
  (≥15 words — short replies aren't punished for brevity) and shares not even
  one 4-word run with anything returned by a successful tool call this turn.
  Silent when no tool call succeeded (nothing to check against — a purely
  conversational reply is fine).
- `_swap_in_unsupported(tool_outputs)`: unlike `_swap_in_unread_note`, there's
  no single note to re-fetch, since the conclusion wasn't tied to one — hands
  back the raw tool output actually retrieved this turn instead, truncated at
  the same `MAX_TOOL_OUTPUT_CHARS` bound already used for outbound tool
  results.
- Both `execute_sub_agent_stream` and `execute_sub_agent_task` now accumulate
  every successful tool call's raw output this turn (`tool_outputs`) alongside
  the existing `read_paths` set, and run this check as a second, cheaper-first
  `elif` after `_content_unread` — a citation-shaped fabrication is still
  handled by the more specific, more informative swap-in.

Known tradeoff, surfaced and accepted before building: a legitimate
paraphrase-only answer with no direct quote at all can misfire and get
replaced with a raw-material dump. Traded deliberately for the grounding
guarantee actually holding on this shape too, matching the standing
"grounding is non-negotiable" rule.

## Verification

`.venv/bin/pytest` — 756 passed (up from 715 at e80674b), including new
`TestContentUnsupported`, `TestSwapInUnsupported`, and an end-to-end
`TestExecuteSubAgentTaskCatchesUnsupportedSynthesis` pair (one flags and
swaps, one — quoting the retrieval verbatim — passes through untouched).

Damiro asked directly whether this had actually been tried against real
models, not just mocked - it hadn't yet. Ran it live (real `~/.sympose`
workspace, real `~/Development/garden` vault, `parent_agent="samantha"`,
task prompt `"dont you remember our favorite game?"`, editable install so
the just-edited code ran):

- `gemini/gemini-3.6-flash`: searched `vault_search(query=Vault Roulette)`,
  got no matches, then answered anyway — guard fired correctly, swapped in
  the honest "No matches for 'Vault Roulette'." instead.
- `ollama/gemma4:e4b`, first pass (25-word gate): ran `run_command(echo
  'Damiro' > ...)` five times (never touching the vault), then answered
  *"Of course! I remember. Our favorite game is **"Vault Roulette,"** where
  a random note from your Obsidian vault is pulled and discussed."* — a
  complete, confident, specific fabrication, and the guard did **not** fire.
  Root cause: only 22 words, under the 25-word minimum meant to spare brief
  acknowledgments from being judged. Lowered `_MIN_WORDS_TO_JUDGE` to 15;
  full suite re-run (756 passed, unaffected); re-ran the same live prompt
  against `gemma4:e4b` again — same fabrication shape, guard fired
  correctly this time, swapped in the real (empty) tool output instead.

So: not a hypothetical fix. Live-verified catching the fabrication on both
backends the original transcript showed failing, after one real miss found
and corrected by actually running it rather than trusting the mocked tests
alone.

### Pass-through check: does it also leave a genuinely grounded reply alone?

Damiro's next question, and correctly so: catching the bug proves nothing
about whether the guard also breaks the happy path. Ran a second live prompt
("what have I written in my vault about getting old? summarize it for me in
your own words.") designed to produce a real, mostly-paraphrased answer —
the harder case for a verbatim-overlap check.

- `gemini/gemini-3.6-flash`: searched, then `read_file`'d the real
  `Thoughts/I on Getting Old.md`, and returned an accurate, well-organized,
  mostly-paraphrased summary. Guard correctly stayed silent.
- `ollama/gemma4:e4b`: no false positive from this guard either, but the run
  surfaced something else — see below.

## Second fix, same session: the "echo laundering" loophole

One `gemma4:e4b` pass-through run did this: `vault_search`'d for "getting
old" (real data came back), then called
`run_command(echo "I have found two mentions of 'getting old' in your
vault: 1. A philosophical note titled 'Thoughts/I on Getting Old.md'...")`
— twice — before citing that bare filename in its final answer. The citation
never having been opened was still caught correctly by the *existing*
`_content_unread`/e80674b check (real note swapped in) — a good, independent
validation of that older guard on a new failure shape (search-snippet-based
guessing, self-"confirmed" via an echoed command instead of an actual read).

But the shape underneath is worth naming on its own: a successful tool call
whose "result" is just the model's own invented text, laundered through a
real shell command. `_content_unsupported`'s `tool_outputs` accumulator, as
first built, trusted *any* successful tool call's output as grounding
evidence — so a synthesis that only "agrees with" its own echoed guess would
have satisfied the overlap check and passed through untouched, in any case
the citation-mismatch check didn't happen to also catch by naming a real
filename.

**Fix**: `_register_read`'s `tool_outputs` param is now scoped to the same
externally-sourced calls `read_paths` already trusts - `read_file`, a
`run_command` that names a real vault file, `vault_sample`, and (newly)
`vault_search`'s ranked snippets (real index data, just not a full body).
An arbitrary `run_command` whose text doesn't name a real file no longer
counts, regardless of which tool carried it.

That surfaced a second-order bug immediately, caught by my own new unit
test before it shipped: excluding the laundered echo left `tool_outputs`
empty, and `_content_unsupported`'s original gate — `if not tool_outputs:
return False` — meant "nothing retrieved, stay silent," conflating "never
tried" with "tried and got nothing real." Added a `retrieval_attempted`
flag, tracked independently of `tool_outputs`, set whenever a
retrieval-shaped tool (`read_file`/`run_command`/`vault_sample`/
`vault_search`) is called at all, success or not. `_content_unsupported` now
gates on `retrieval_attempted`, not on `tool_outputs` being non-empty — so
"attempted and came back with nothing externally sourced" is judged (and,
correctly, fails), while "never attempted, purely conversational" still
stays silent. `_swap_in_unsupported` got an explicit empty-evidence branch
for this case too, since there's no material left to hand back.

New tests: `TestRegisterReadToolOutputsLaundering` (unit-level: an echoed
guess is excluded, a real `cat`/`read_file`/`vault_search` result isn't),
`TestExecuteSubAgentTaskCatchesEchoLaunderedFabrication` (end to end), plus
a `retrieval_attempted`-specific case in `TestContentUnsupported`. Full
suite: 763 passed (up from 756).

**Re-verified live** against the exact prompt that produced the original
echo-laundering run, three times on `gemma4:e4b`:
- Runs 1 & 2: same `assistant()` hallucinated-tool pattern (a tool name that
  was never offered to it), followed by an ungrounded conclusion — guard now
  fires correctly both times, swapping in the real `vault_search` results.
- Run 3: same hallucinated `assistant()` call, but the model derailed
  entirely into self-identification (`{"name": "Gemma 4", "developer":
  "Google DeepMind", ...}`) instead of answering at all — 13 words, under
  the 15-word floor, so nothing fired. Not a grounding-claim failure at all
  (there's no claim about vault content to check the words of) — see "Open
  follow-up" below.

## Third pass: `/code-review` on the pushed commit, and what it caught

Damiro asked for a final error check on the pushed commit. Ran `/code-review`
(medium effort), which forked into 8 parallel angles (line-by-line diff,
removed-behavior audit, reuse, efficiency, architecture/altitude,
simplification, `CLAUDE.md` convention compliance, cross-file tracing) — all
converging independently on the same handful of real issues, a strong signal
they were genuine rather than review noise. Reported via `ReportFindings`,
then fixed the confirmed correctness and convention issues in a second
commit, same day:

1. **The echo-laundering fix had its own loophole.** Round one (above) only
   blocked a *bare* `echo` with no filename in it; `echo "According to
   notes/foo.md, our favorite game is X"` still matched
   `_COMMAND_FILENAME_RE` on the filename mentioned *inside the fabricated
   text itself* and got trusted again. Fixed by checking the command's
   *leading word* against `_TEXT_GENERATING_COMMANDS` (`echo`/`printf`/
   `print`) instead of scanning the whole string for a filename - structural
   (what the command does), not a phrase list (what it says).
2. **`web_search` was invisible to both checks.** A real, default-enabled
   tool returning genuine external content, but absent from the "does this
   count as retrieval" logic entirely — a fabrication after a real web
   search would never have been caught. Added alongside `vault_search`
   (ranked results count as evidence, don't count toward `read_paths` since
   they're not a full body).
3. **A failed tool call could override an honest answer.** `retrieval_attempted`
   was being set from the tool name alone, before checking whether the call
   actually succeeded — so a `read_file` on a path that doesn't exist could
   cause an already-honest "I couldn't find that" explanation to get
   replaced by the generic fallback message. Fixed by making
   `_register_read` itself the single source of truth: it now returns
   whether a call counts as an attempt, True only when the call *succeeded*
   and was retrieval-shaped by name — a failed call returns False (honest
   failure isn't second-guessed), but a call that succeeded and got excluded
   as self-authored (echo laundering) still returns True, since that
   *is* the case this whole guard exists to catch. Conflating "attempted"
   with "trusted" was itself a bug introduced mid-fix today — caught by my
   own new unit test before it shipped, not by review.
4. **Short retrieved content made the overlap check unwinnable.** A fixed
   4-word shingle meant any source under 4 words (a short note title, a
   brief snippet) produced an empty shingle set, and `isdisjoint` against
   an empty set is always `True` — so a reply correctly quoting a *short*
   source verbatim still got flagged unsupported. Shingle size now adapts
   down to `min(4, shorter side's word count)`. Surfaced its own tokenizer
   bug while writing the test for this: `_WORD_RE` let a leading apostrophe
   from single-quote-style quoting attach to the next word (`'favorite`
   instead of `favorite`), breaking an otherwise-exact match — tightened to
   require an alnum start, contractions like "don't" still match correctly.
5. **Ordering: a weaker recovery could pre-empt a better one.** When
   `_content_unread` fires on a citation that doesn't resolve to a real
   note, *and* real `tool_outputs` material exists from the same turn (e.g.
   a genuine `vault_search` result, alongside a separately invented
   citation), the old `if/elif` let the content-free "I never opened it,
   ask again" win even though the real material would have been a
   materially better answer. Consolidated both checks into one
   `_finalize_synthesis` helper (also fixing the streaming/non-streaming
   duplication multiple review angles flagged) that prefers real
   `tool_outputs` over a bare apology when both exist.
6. **New thresholds were hardcoded instead of declared settings.** Against
   the project's own ADR-077 rule ("every runtime setting is declared once
   in `config_schema.py`"). Added `sub_agent.unsupported_synthesis_min_words`
   as a proper `Setting` (default 15, `minimum=1`), matching the existing
   `sub_agent.*` section; regenerated `docs/wiki/reference/configuration.md`
   (test-enforced to stay in sync).

Consciously left open: the truncation-before-shingling edge case (needs
>20000 chars of retrieved content to trigger — rare, and fixing it well
means restructuring the truncation flow, not a quick patch) and the file's
LOC count (already flagged after round one, a deliberate deferral, not an
oversight — splitting `sub_agents.py` is its own scoped task).

Full suite: 775 passed (was 763). Re-verified live after this pass too:
gemini answered the original "favorite game" prompt correctly *without*
calling any tool at all (the fact is already in persona working memory, so
no retrieval happened — confirming the guard doesn't punish an already-
grounded, tool-free reply); `gemma4:e4b`'s repeat echo-spam run now gets the
clean "I didn't manage to retrieve anything real" honest fallback instead of
either a fabrication or a confusing dump; the "getting old" pass-through
case still produced an accurate, verbatim-quoting summary, untouched.

## No ADR

A second, narrower instance of the same structural swap-in pattern e80674b
already established (itself not an ADR) — no new dependency, no new
round trip, no policy decision beyond what round-trip-frugality already
settled. Elevate to an ADR only if this class of guard grows a third,
meaningfully different shape.

## Open follow-up

- Noted, not built: `_vault_ctx_title_missing` (the primary-persona-path
  sibling check — a real note handed over and never referenced at all)
  still has no sub-agent equivalent. Different shape again (sub-agents
  fetch their own content via tools rather than being handed a pre-fetched
  `vault_ctx`), and no live failure has shown this specific gap on the
  sub-agent path yet — left for whenever one does.
- Run 3 above is out of scope for this guard by design (no vault-content
  claim exists to check) and is the same failure class already catalogued
  in [`docs/wiki/reference/vault-agent-capabilities.md`](../../wiki/reference/vault-agent-capabilities.md)
  ("Unrelated tangents mid-task... identifying itself as 'Gemma 4, developed
  by Google DeepMind'"). No amount of grounding-check tuning fixes a model
  that invents a tool name and abandons the task — that needs a narrower
  tool surface per model tier, which is exactly what ADR-122 (Local/Cloud
  Model Routing by Message Complexity, accepted, implementation pending)
  already proposes. Today's three live runs are concrete evidence for
  prioritizing that build, not a new proposal.
