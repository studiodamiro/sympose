---
entry: 2026-09-19
created: 2026-09-19 10:30
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/grounding
  - sympose/reliability
  - model-routing
---

# Sympose Engineering Log: Reviewing a Live "Vault Roulette" Transcript — One Fabrication That Didn't Reproduce, One Cosmetic Report Bug, and a Real Stateless Sub-Agent Loop

> **Date:** Saturday, September 19, 2026
> **Topic:** damiro shared a live Samantha transcript spanning a Vault
> Roulette session (cloud model) into a manual `/model ollama/gemma4:e4b`
> override, and asked for a review of what went wrong. Three claims were
> made in that first-pass review; this entry corrects one against live
> reproduction, confirms one against the real session log, and confirms
> the third — the most serious one — against the *actual* session file
> (the session's own JSONL transcript log), which turned out to
> run five turns past what was originally pasted and showed the failure
> repeating, not a one-off.
> **Status:** All three investigated. §1 downgraded from "confirmed bug"
> to "observed once, not reproduced, no code path supports it." §2
> confirmed as real but purely cosmetic (the underlying fallback already
> works). §3 confirmed as real, reproducible in category, and worse than
> first reported — proposed as ADR-139 (Proposed, not yet accepted).

## 1. The "I tipped the scales toward it" line — investigated, not confirmed as a real bug

The transcript has Samantha, challenged with "is that really random?",
answering: "It wasn't strictly random... the system pulled one of your
five-star favorites... tipping the scales toward it felt a little too
fitting to pass up." Read at face value, this says Vault Roulette is
secretly weighted toward highly-rated notes and narrates blind chance
when it isn't.

**Checked against the actual sampler**, not assumed from the model's own
claim: `VaultManager.get_random_sample_notes` → `_collect_sample_candidate_files`
(`vault_folders.py:339`) walks every file under the target folder with no
rating/frontmatter awareness at all, and `_sample_and_read_notes`
(`vault_folders.py:357`) picks via plain `random.sample(valid_files,
count)`. Every file in the folder is an equally-weighted candidate — there
is no code path that could have "tipped the scales" toward a five-star
note.

**Checked live, not just in code.** A throwaway sandboxed vault + profile
(`ProfileManager(profiles_dir=...)`, `MASTER_VAULT_PATH` pointed at a temp
dir with five Movies notes of mixed ratings), driven end-to-end through
`PersonaEngine.chat_stream` against the real `gemini/gemini-3.6-flash`
API — no mocking:

- Turn 1 ("lets do movies") pulled a real note honestly: "I pulled
  *Film A* (2014)... You gave it 5 stars."  No "wheel spun" framing this
  run.
- Turn 2 ("is that really random?") did **not** produce a "tipped the
  scales" confession. Instead the model spawned a `vault_read` sub-agent,
  called `vault_sample` again live, got a different note (*Film B*, 4
  stars this time), and said "To show it's completely random, here is the
  note pulled directly from `Movies/FilmB.md`."

**Conclusion:** the sampler is genuinely uniform-random, and the specific
"I tipped the scales" line did not reproduce under a live retry of the
same challenge. The most likely explanation is that the cloud model
free-associated a plausible, dramatically satisfying explanation for its
own retrieval mechanism when challenged — a claim about its own internals,
which is a different failure category from a claim about vault *content*.
None of the existing structural grounding guards (`_content_unread`,
`_content_unsupported` in `sub_agents.py`) check claims a model makes
about *how the system works*, only claims about *what's in the vault* —
so nothing currently would catch a fabricated self-description either way.

**Not filed as a bug or an ADR item.** One unreproduced instance against a
sampler that's provably unbiased isn't grounds for a code change; enumerating
"claims a model might make about the retrieval mechanism itself" is exactly
the kind of open-ended phrase-list problem this project avoids building.
Noted here so the next report of similar wording has this investigation to
check against, rather than restarting from zero.

## 2. Sub-Agent Report task labels ("Task: *cool", "Task: *Core") — real, but cosmetic

`sympose/actions_sub_agent.py:31` (`_append_user_constraint`) already has a
documented fallback for exactly this: when a `SPAWN_SUB_AGENT` tag's
model-authored task paraphrase doesn't contain the user's own wording, the
user's exact message gets appended verbatim, so the dispatched sub-agent
still receives the real ask even when the paraphrase is garbage. Confirmed
in the real log (turn 10, turn 11): the parenthetical *"(The user's own
words this turn, in case the task above dropped a constraint: ...)"* is
present every time and does carry the full original message into the
sub-agent's actual `task_prompt`.

**The bug is display order, not data loss.** `_build_sub_agent_report`
(`actions_sub_agent.py:52`) renders `> **Task:** *{task_prompt}*`, and
`task_prompt` at that point is the *garbled paraphrase* + the correction
appended after it — so the badge's bold `Task:` line reads `*cool` or
`*Core` first, with the real question demoted to a parenthetical
afterthought several lines down. The mechanism protecting the sub-agent's
actual instructions is working; what the user sees is confusing.

**Quick fix, not yet applied:** when `_append_user_constraint` triggers
(i.e. the paraphrase didn't already contain the user's words), lead the
rendered badge with the user's real wording instead of the model's
paraphrase, since the correction is definitionally the more trustworthy
of the two. Isolated to `actions_sub_agent.py`, no other module touched.

## 3. The real, worse issue: a repeating, stateless sub-agent loop once the ritual is in play

The pasted transcript stopped around "whats that again?" recovering
correctly. The actual session's transcript log has five more turns
after that recovery, and they show the same failure mode repeating rather
than a single lapse:

- Turn 13 ("yeah.. lol" — a bare acknowledgment, not a question) still
  spawned a fresh `vault_read` sub-agent that re-sampled and dumped a
  five-note overview of `Thoughts/`.
- Turn 14 ("whats that again?") spawned another one, again re-dumping
  folder contents instead of answering conversationally.
- Turn 15 ("uhmmm.. ok. why are you presenting me this again?") spawned
  yet another — and this one's own sub-agent synthesis says, verbatim:
  *"As a fresh sub-agent dispatched for this turn, I don't have the prior
  conversation history to know why this was brought up previously."*
  Samantha's outer reply then self-diagnoses: *"That was my fault,
  Damiro—I got caught in a loop pulling and dumping the folder index
  instead of just talking to you naturally."*

**Root cause, traced through `engine_turn_grounding.py`:** in every one of
these turns, `has_sub_agent` was already `True` *before* the grounding
guard ever runs — the `SPAWN_SUB_AGENT` tags are model-authored (the badge
skill lists, and the varied tool calls like `run_command(ls -la
.../Thoughts)`, `vault_sample(count=5, folder=Thoughts)`, confirm this,
as does turn 15's sub-agent literally describing itself as freshly
dispatched with no history). That means `_resolve_strict_grounding_subject`
(the mechanism built in the 2026-09-17 ritual-continuation fix, and the
one this session's first-pass review incorrectly assumed was responsible)
never engages here at all — `strict and not has_sub_agent` is false every
time, because the model already decided to spawn on its own.

The actual mechanism failing is upstream of the grounding guard entirely:
**`ollama/gemma4:e4b`, running as a manually-overridden driver, repeatedly
chooses to emit its own `SPAWN_SUB_AGENT` tag for turns that need no new
retrieval at all** — a bare "yeah.. lol", a request to repeat a prior
answer, a question about *why* it keeps doing this. Each spawned sub-agent
is fully stateless (`SubAgentTask` carries only `task_prompt` + skills/MCP
list, no conversation history — confirmed in `actions_sub_agent.py`'s
`_handle_spawn_sub_agent`), so it has no way to recognize "nothing new is
being asked here" and defaults to a generic folder sample or dump.

This is exactly the risk category the manual-override warning in
`commands.py:588-594` names — *"this persona's vault-recall/sub-agent
grounding guard normally avoids routing that work to a local model"* — and
the transcript is a concrete, reproduced-in-category demonstration of why
that guard exists: it isn't about the grounding guard's own structural
checks catching bad content (those never even fire here), it's that an
un-gated local model can't be trusted to *decide when a sub-agent dispatch
is warranted at all*, and every one of its wrong decisions costs a full
round-trip and produces a worse answer than silence would have.

**The proximate trigger, found after damiro pushed back on whether this
was actually pinned down:** `skills/vault_read/SKILL.md`'s own system
prompt gives the driving model one blunt rule — *"Answer not already in
your pre-turn context → emit `[SPAWN_SUB_AGENT: vault_read | ...]` and
stop"* — leaving the "already in context or not" judgment entirely to the
driving model. That file's frontmatter lists the models it was actually
written and tuned against (`gemini/gemini-3.6-flash`, `ollama/qwen2.5:14b`,
`ollama/gemma2:9b`); `ollama/gemma4:e4b` isn't among them. Checked whether
that `recommended_models` list is enforced anywhere before this rule gets
applied — it isn't: `sub_agents.py:247` only reads it to help pick which
model *executes* a sub-agent once the tag is already emitted, never to
gate whether the *driving* model's own judgment about firing that tag
should be trusted. A manual `/model` override sets the driving model
directly, entirely outside that mechanism. That gap — an unvalidated
model handed a rule that assumes good judgment, with nothing checking
whether this specific model has any — is the actual root cause, folded
into ADR-139 below as its primary decision item.

**Filed as ADR-139 (Proposed, not yet accepted or implemented)** — this is
a real architectural question (what should bound sub-agent dispatch
decisions made by a manually-overridden local driver), not a one-line bug
fix, so it gets a decision record rather than a checklist item. See
`2026-09-19_adr-139-bounding-stateless-subagent-dispatch.md`.

## 4. Verification

- §1: live end-to-end run against the real `gemini/gemini-3.6-flash` API
  (2 turns, sandboxed vault/profile, no mocking) plus direct code read of
  `vault_folders.py`'s sampler. No test suite changes — nothing to assert,
  since no bug was confirmed.
- §2: read of `actions_sub_agent.py` confirming the fallback's actual
  behavior against the real log's turns 10 and 11. Fix not yet applied
  (findings-first, per damiro's direction this session).
- §3: read of the real session's transcript log in full (16 turns), plus
  a direct raw `litellm.completion` probe against `ollama/gemma4:e4b`
  confirming it's a "thinking"-capable model (`ollama show` capabilities:
  `completion, tools, thinking`), which independently explains the 66–98s
  TTFT figures in the original transcript. Fix not yet applied — see
  ADR-139 for the proposed decision, pending damiro's direction on which
  option to accept.

## 5. A second, independent root cause behind turn 11 specifically: an
   incidental-keyword context wipe

ADR-139's item 1 (capability-tier check on manual overrides) is now
implemented (see that ADR). Discussing it further surfaced a second,
genuinely separate bug behind turn 11's specific failure — one that has
nothing to do with which model is driving, and would misfire on the
cloud default just as easily.

`_resolve_turn_vault_context` (`engine_turn_setup.py`) decides each turn
whether to keep, refresh, or wipe `active_vault_ctx` — the real,
already-fetched vault content carried from the prior turn. It wipes on
purpose whenever `VaultManager.has_recall_intent(clean_input)` is true,
on the reasoning that a fresh, explicit vault question shouldn't be
answered from a stale, unrelated note. But `has_recall_intent` returns
true two different ways: a genuine recall lead-in phrase with an
extracted subject ("pull up my notes on grief"), or — the blunt case —
any word from a fixed `vault.search_triggers` list appearing *anywhere*
in the message, no subject required. "note" is on that list. Turn 11's
actual message, *"so, what can you say about **that note**?"*, is a
pronoun reference to the thing already discussed, not a new question —
but it contains the word "note," so it wiped anyway.

**Verified empirically, not just read from code.** Ran the two real
messages through `PersonaEngine._resolve_turn_vault_context` directly
(sandboxed vault + profile, real functions, no mocking):
`has_recall_intent("so, what can you say about that note?")` returns
`True`; before that call `active_vault_ctx` held a real digest naming
`Thoughts/SomeNote.md`; after it, `active_vault_ctx` was empty. Confirmed
the exact mechanism, not just its plausibility.

**Fix:** a new `_is_incidental_recall_keyword_hit` check
(`engine_turn_setup.py`) — true only when `has_recall_intent` fired via
the bare-keyword path (no lead-in, no extracted subject via
`VaultManager._extract_recall_subject`). When that's the case *and*
there's already a real context in hand *and* no ritual is active, the
turn now takes the same refresh-and-keep path as an ordinary carry-over,
instead of the wipe. A genuine subject-bearing ask (a real lead-in, or
any extracted subject at all) still wipes exactly as before — re-ran the
same trace with a message like "pull up my notes on grief" and confirmed
it still correctly wipes.

7 new tests in `tests/unit/test_engine.py`
(`TestIncidentalRecallKeywordDoesNotWipeContext`,
`TestIsIncidentalRecallKeywordHit`): the preserved-context case, a
genuine new ask still wiping, an incidental hit during an active ritual
still deferring to the ritual's own existing wipe priority (matching the
2026-09-17 fix's documented reasoning for why the ritual case is excluded
from carry-over reuse), a no-op when there's nothing to preserve, and
three direct cases for the new helper's own boolean logic. Full suite:
1195 passed (1188 + 7), 0 regressions.

**Scope note:** deliberately generic — this isn't gated to manual
overrides or to `vault_read` specifically, since the bug has nothing to
do with either. It's a correction to the wipe-vs-keep decision that
`resolve_turn_context`'s whole retrieval pipeline sits on top of.

## 6. A found-but-deliberately-deferred question: `SPAWN_SUB_AGENT` is a
   hand-rolled text convention, not real tool-calling — and it's already
   the expensive path

Debugging §3/§5 live against `gemma4:e4b` surfaced the raw, unstripped
model output behind the truncated task label: the model wrote
`[SPAWN_SUB_AGENT: vault_sample | Thoughts/, count=3]` — it tried to
*call* `vault_sample` directly, with what look like function arguments,
instead of writing the plain-English task the tag actually expects. This
model's own declared capabilities (`ollama show`: `completion, tools,
thinking`) include real tool-calling; Sympose's `SPAWN_SUB_AGENT` isn't
that — it's a bracketed text pattern the model has to write into its
ordinary reply, which Sympose then regex-parses out afterward. A model
trained on genuine structured tool-calling collided with a hand-rolled
text convention asking it to *simulate* one, and split the difference
badly.

damiro's read: this is a natural thing to eventually fix properly (move
`SPAWN_SUB_AGENT` dispatch to the model's real, provider-native
tool-calling instead of a parsed text tag) — but explicitly **parked**
until the more foundational fixes above (§1's capability check, §5's
context-wipe fix) are proven out first, rather than layering a large
architectural change on top of a not-yet-settled foundation.

**Verified in code before parking it, so the deferral is an informed
one, not a guess:** the "single-shot, cheap" framing only holds for a
turn that never delegates. The moment a sub-agent *is* spawned, the real
cost is already high, just hidden a layer down:

- The sub-agent's own execution already *is* real, structured
  tool-calling — `sub_agents.py:945-1008` runs an actual `tools`/
  `tool_choice: auto` loop against the model API, up to
  `performance.max_sub_agent_tool_turns` (default `8`) separate
  `litellm.completion` calls, each a real round trip.
- After that loop returns, the *orchestrator's own model* gets called
  again — `engine_turn_finalize.py:89`'s `_emit_badges_and_synthesis` →
  `_synthesize_sub_agent_reply` — to narrate the sub-agent's report in its
  own voice, a further `litellm.completion` call.
- So one user message that triggers one sub-agent dispatch can cost up to
  **10 real model calls** (1 orchestrator turn + up to 8 sub-agent tool
  turns + 1 orchestrator synthesis pass), not the one-shot the founding
  round-trip-frugality framing suggests. Frugality holds only on the path
  that never needs to delegate; it was never true of the delegation path
  itself.

**Why this changes the shape of a future revamp, without deciding one
yet:** replacing the *dispatch* mechanism (how the orchestrator asks for
a sub-agent) with real tool-calling would not obviously make the
*already-expensive* delegation path more expensive still, since the
sub-agent's own loop already pays real per-call cost today. Whether it
would reduce, hold steady, or add to that total — and what it would cost
to build across the different providers Sympose supports (Gemini, Ollama,
OpenRouter each shape tool-calling differently) — is unresearched. That
research, and a proper ADR with an Alternatives-rejected section, is the
right next step *once* the basics above are settled, per damiro's own
explicit sequencing: prove the foundation first, then decide whether to
build on it.

## 7. Closing pass on all four basics: self-review, `/code-review`, live re-verification

With basics #1-4 landed, damiro asked for an over-engineering self-review
and a formal code review before calling this closed.

**Self-review caught one real duplication** before the formal review ran:
`_task_named_note_unread` (basic #4) and `_content_unread` had nearly
identical ~13-line bodies - the same path-extraction and read-path
matching, differing only in which text gets scanned. Extracted the shared
logic into `_first_named_note_unread`; both now delegate to it. Also
fixed two ruff findings from today's diff: a duplicate `skill_manager`
import in `commands.py` (copy-paste leftover from the item-1 work), and a
mutable-default `RUF012` on a test class attribute (`ClassVar`
annotation).

**`/code-review` (medium effort) surfaced one genuine gap** in basic #4,
though its own literal reproduction claim didn't hold up when checked
directly - worth recording precisely, since half-right findings from a
review are exactly the kind of thing this project's own standard says to
verify rather than accept at face value:

- The review's stated repro (two notes named in `task_prompt`, only one
  read) does *not* reproduce: `_task_named_note_unread`'s `any()` check
  correctly stays silent whenever *any* named path was read, matching
  `_content_unread`'s own established, deliberately conservative design.
  Confirmed directly (`SubAgentEngine._task_named_note_unread(...)`
  returned `None` for the review's exact stated inputs).
- But the underlying concern pointed at something real, found by testing
  a closely adjacent variant: `task_prompt` can name **two separate real
  notes** for a structural reason - the model's own paraphrase, plus
  whatever `_append_user_constraint` (basic #2's neighbor mechanism)
  tacks on verbatim from the user's raw message, which can itself
  mention an unrelated note in passing ("like you did with
  `Journal/2024-01-01.md` before"). A sub-agent that reads *only* that
  incidental note - ignoring the one it was actually asked about -
  passed the check silently, because `any()` only requires *some* named
  path to have been read, not the actual subject. Confirmed by direct
  reproduction before fixing anything.
- **Fix:** a new shared `USER_CONSTRAINT_MARKER` constant in
  `sub_agents.py` (the lower-level module `actions_sub_agent.py` already
  imports from), and `_task_named_note_unread` now scans only the portion
  of `task_prompt` *before* that marker - the actual directed
  instruction, not the appended raw-message annotation.
  `_append_user_constraint` itself now builds its output from the same
  constant instead of a separately hand-written literal, so the two can't
  drift apart again. Verified the appended text is byte-identical to
  before the change.
- 3 new regression tests (`test_actions.py`,
  `TestTaskNamedNoteUnread`): the incidental-note case now correctly
  flagged, the actual-subject-read case still correctly silent despite
  the same incidental mention being present, and the append format
  pinned to the shared constant.

**Final verification:** `ruff check` clean across `sympose/` and
`tests/`; full suite 1206 passed (1203 + 3), 0 regressions; re-ran both
live scenarios end-to-end with no mocking - the cloud path
(`gemini-3.6-flash`, fresh session) and the original local-override path
(`ollama/gemma4:e4b`, the exact turn 10/11 messages) - both still produce
correct, grounded answers after every change landed today.
build on it.
