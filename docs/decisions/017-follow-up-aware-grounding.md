# 017 — Follow-up-aware grounding: rewrite a search-less message from recent turns

> **Status: Accepted.** Built as `off` and `rewrite`; the other two modes below are reserved, not built. **Scope of the live measurements: Ollama and `gemma2:9b` only**, on the synthetic fixture vault (nine follow-up cases, several runs each). Cloud models and other local models are unmeasured: they may write better or worse rewrites and have different latency, so the rewrite prompt and the number of recent turns are worth re-checking per model.

## Context

The grounding retriever (ADR 014) reads only the current message. A follow-up such as "why did we pick it?" has no searchable words and no way to say what "it" is, so nothing is grounded even though the notes were found one turn earlier. The model still sees the earlier conversation (the history is in the prompt), but the note text does not carry over: a reason that lives in the vault and not in the chat is either reported as not found or guessed. The same holds for "and the budget one?", "go on", "can you expand on that?". This is a retrieval gap, not a context-window gap (ADR 015): the window has room; the search step never sees the earlier turns.

How this is commonly handled: rewrite the question into a standalone one using the chat so far before searching (accurate, costs a model call); search on the last few turns together (crude, cheap); let the model search for itself in a loop (most reliable, costs round trips and needs a model that is good with tools); summarize old chat. The first and second fit this project's cost stance; the third depends on tool-calling, which is not built.

## Decision

**Retrieve first; only on a miss, and only with history, look at the earlier turns.** The current message is searched exactly as today. If that grounds nothing and the chat has earlier turns, the follow-up step runs. Most turns pay nothing extra. The trigger is mechanical (an empty first pass and history exists), not a list of phrases: no wording of a follow-up is enumerated.

**A knob,** the `grounding_followups` setting (a user-facing default belongs in `settings_store`), settings file only for now (there is no settings screen, and no slash command per knob):
- `rewrite` (default): a model call, given the last two exchanges, returns one standalone search query, or `NONE` when the message has no topic of its own (thanks, a greeting, small talk, a change of subject). Retrieval is then run again on that query. A wrong rewrite finds nothing rather than inventing evidence, because the rewrite only feeds the search and the retriever's precision gates (ADR 014) still decide what reaches the model.
- `off`: today's behavior, no extra call. Only an explicit `off` turns it off; any other or malformed value leaves the default, the same rule as the other knobs.
- `recent-words` (**reserved, not built**): no model call; the previous exchange's search terms reused at lower weight. Free, but it attaches the old topic's notes on a topic change, and with `rewrite` measured this good there was no case for building a weaker mode yet. It stays as the option for someone who wants no extra call on a small local model.
- `model-searches` (**reserved, not built**): the model asks for notes itself. Not offered until tool-calling exists (`_CAPABILITY_LIMITS` in the prompt says the engine cannot run tools yet), and expected to suit cloud models more than small local ones.

**What the rewrite sees.** The last two exchanges (four messages), assistant replies included, each message cut to 300 characters. The reply often holds the noun a bare "it" refers to ("You decided on SQLite for the Atlas prototype…"), and the tail of a long reply is not needed to find it. The same model as the chat runs it, with the same window (`num_ctx`), so a local model is not reloaded for the extra call, and its own reply is capped at 60 tokens. There is no separate rewrite-model setting: the warm cost was measured small enough (below) that a second model would add a knob and a load without a measured need.

**When the rewrite does not happen or fails, the turn goes on as before, ungrounded by it.** No history, the knob off, a persona with no vault (nothing a query could find), the prompt not fitting the window (sized by the same budget code as the main call, ADR 015), a model error, an empty reply, a reply cut off at its 60-token limit (a query cut mid-word could ground the wrong note), or `NONE`: each means "no rewrite", never a failed turn. A rewrite is never saved as a turn and never shown to the model as something the user said; it only feeds retrieval.

**The rewrite is visible.** The rewritten query is carried on the turn result and shown at the end of the reply header, after the grounded-notes segment (ADR 016), as `searched "…"`, cut at its end to what fits the line. On a narrow line the note's path gives up room first (keeping its filename, as ADR 016 does), and the query is left out when even that leaves it no readable room; on an 80-column line it shows as `from …Atlas.md · searched "why we pick…"`. It only appears when the rewrite is what grounded the reply, so a wrong rewrite that found a wrong note can be seen and a rewrite that found nothing says nothing (an ungrounded reply already says so in its text). It follows the same `show_grounding` knob as the notes segment.

**Where it lives.** A small module, `engine/followup.py`, holds the rewrite prompt, the call and the orchestration (`ground` = first pass, then the rewrite and a second pass), reusing `grounding.ground` and `model.call_model`; `turn.py` calls it in place of `grounding.ground`. The rewriter is a parameter, so retrieval can be tested with a fake one and no model.

## Measured (Ollama, `gemma2:9b`)

Nine cases over the fixture vault: five follow-ups that need a rewrite ("why did we pick it?", "and when is the launch?", "go on", "can you expand on that?", "where are we staying?"), and four that must not attach the old topic (thanks, "how are you today?", "ok let's talk about something else", a standalone question about a note the vault does not have). Each was run several times.

- **First prompt (no way to say "no topic"): 8 of 9 classes right, one wrong every time.** "thanks, that helps!" was rewritten into "Atlas database decision" and attached the Atlas note, the stale-topic failure this ADR was worried about. An empty reply also occurred once (handled as "no rewrite").
- **Adding `NONE` for messages with no topic of their own fixed that**, but the model then dropped the project name from "why did we pick it?" ("why we picked SQLite"), which the retriever's precision gate rejects (one matching word, not in the title). Telling it to always include the specific names involved (the project, person, place or note title) plus the question's own key words fixed that: **45 of 45 runs correct** (nine cases, five runs each), all the topic changes and small talk returning `NONE` or an unchanged query that grounds nothing.
- **Latency, warm (model loaded):** about 0.4 to 0.7 s per rewrite, 1.5 to 2 s for the first one after another prompt. Cold latency (model not loaded) is the same as any first call and is not extra, since the chat model is the one that runs.
- **A reasoning model cannot do this step (`qwen3:8b`).** It spends the whole 60-token limit thinking and writes nothing: 8.7 to 11 s wasted per miss. Given 512 tokens it finished in 20 to 50 s (and failed on one of four), given 2048 in 35 to 130 s. That is far too slow to be worth it, so the limit stays small and a model that uses it up without answering is remembered for the rest of the process and not asked again (its turns go on ungrounded by a rewrite; the knob can also turn the step off). Other models were not measured.
- A standalone question the first pass misses (`NONE` returned for "how long do I bake the sourdough?" in the test that ran the rewrite on every message) never reaches the rewriter in the real flow: the first pass finds it. And when the first pass finds nothing for a question that does stand alone, `NONE` is the same as today.

## Consequences

One extra model call on a miss when the mode is `rewrite`, about half a second for the call itself on the measured local model (one to one and a half seconds on the whole turn in the live check below): the reliability-versus-cost dial ADR 014 left for this slice, with a knob to turn it off. A small local model can still write a poor rewrite, which the precision gates contain but do not fix. A rewrite grounded on the wrong note is visible in the header, not silent.

The time the user waits is the rewrite call plus the chat call, and the TTFT in the header (ADR 013) only covers the chat call, so a rewritten turn looks a little faster than it felt. Ollama also keeps one prompt's processing per slot and reuses it only while the next prompt starts the same way; the rewrite call in between is a different prompt, so a rewritten turn may also pay to process its main prompt again. Both are small on the measured setup and are only on missed turns (see the live check below).

## Live check (real engine, `gemma2:9b` through Ollama, the fixture vault)

Five turns in one chat, the knob on and then off: "what did we decide about the database for Atlas?", "why did we pick it?", "thanks, that helps!", "how are you today?", "and what's the launch target?".

- **The follow-up was grounded and the answer came from the vault.** With the knob on, "why did we pick it?" was rewritten into "why choose SQLite Atlas database", grounded on the Atlas note, and answered "It needs zero setup." (what the note says). With the knob off it grounded nothing and the model answered "because it's lightweight and self-contained", a reason that is in no note: the same gap as before, and the reason for this slice.
- **Nothing stale was attached.** "thanks, that helps!" and "how are you today?" both ran with the knob on and grounded nothing; "and what's the launch target?" grounded on its own (a first-pass hit) and did not run a rewrite.
- **Cost, wall time of the whole turn for the follow-up:** about 4.0 s, 3.5 s and 4.3 s with the rewrite against about 2.9 s and 2.7 s without in the quiet runs, so roughly one to one and a half seconds more. The machine was not quiet for all runs (the chat's own TTFT swung between 0.4 and 5.7 s in both modes), so this is an indication, not a benchmark.

## Amended by ADR 021

The rewrite step also runs when the first search is *weak* (every hit rests on one matched word), with or without earlier conversation, and a `NONE` answer then drops the weak hits. The mixed-topic risk listed below is seen in practice: a rewrite of "what did we talked about last time?" carried "our table" over from an earlier turn.

## Not built yet

- The `recent-words` and `model-searches` modes.
- A separate cheaper model for the rewrite, and any measurement on cloud or other local models.
- A settings screen and a slash command for the knob (settings file only for now).
- Showing that a rewrite ran but found nothing, and counting the rewrite call in the time the header shows.
- Skipping the call for small talk: any ungrounded message with history pays it, since the trigger is structural (a miss), not a guess about wording; a "thanks" costs one short call that answers `NONE`. A mixed query (a topic change whose rewrite drags in the old topic's name, "Atlas tax filing deadline") is possible from a small model and was not seen in the measured cases; the query is visible in the header and the retriever's gates still apply.
- Rewriting in the same call as the chat (one call, but the model would then have to write the query before the evidence exists).

## Alternatives rejected

- **Rewrite on every turn.** Costs a call per turn to fix the minority of turns that miss; retrieve-first pays only when needed.
- **Enumerating follow-up phrases** ("why did we", "what about"). Wording-dependent and brittle; the trigger is structural.
- **Only searching on the last few turns concatenated.** Kept as the free `recent-words` idea, not built, because it attaches stale notes on a topic change.
- **Model-driven search as the first step.** Needs tool-calling and round trips; reserved as the fourth mode.
- **Letting the rewrite run without a way to say "no topic".** Measured: it invents a query from the old topic for small talk.
