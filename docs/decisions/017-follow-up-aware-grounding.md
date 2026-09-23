# 017 — Follow-up-aware grounding: rewrite a search-less message from recent turns

> **Status: Proposed, not built.** The decisions below were agreed in discussion and are recorded so they survive; they are finalized (and the open questions closed) when the slice is built. The retrieval behavior described for a small local model is unmeasured: where a number is needed it is to be measured on Ollama and `gemma2:9b` first, like the rest of the grounding work, and re-checked on other models.

## Context

The grounding retriever (ADR 014) reads only the current message. A follow-up such as "why did we pick it?" has no searchable words and no way to say what "it" is, so nothing is grounded even though the notes were found one turn earlier. The model still sees the earlier conversation (the history is in the prompt), but the note text does not carry over: a reason that lives in the vault and not in the chat is either reported as not found or guessed. The same holds for "and the budget one?", "go on", "can you expand on that?". This is a retrieval gap, not a context-window gap (ADR 015): the window has room; the search step never sees the earlier turns.

How this is commonly handled: rewrite the question into a standalone one using the chat so far before searching (accurate, costs a model call); search on the last few turns together (crude, cheap); let the model search for itself in a loop (most reliable, costs round trips and needs a model that is good with tools); summarize old chat. The first and second fit this project's cost stance; the third depends on tool-calling, which is not built.

## Decision (agreed direction)

**Retrieve first; only on a miss, and only with history, look at the earlier turns.** The current message is searched exactly as today. If that grounds nothing and the chat has earlier turns, the follow-up step runs. Most turns pay nothing extra. The trigger is mechanical (an empty first pass and history exists), not a list of phrases: no wording of a follow-up is enumerated.

**A knob with four modes,** a setting in `settings_store` (a user-facing default belongs in settings), working name `grounding_followups`:
- `off`: today's behavior.
- `recent-words`: no model call; the search terms of the previous exchange (and the notes grounded on the last turn) are reused at lower weight when the new message has none of its own. Free, less precise. The exact carry-over rule (one turn back, last grounded notes, or last message's terms) is open.
- `rewrite` (proposed default): a model call, given the last few turns, returns one standalone search sentence, or the message unchanged when it already stands alone (the model's judgment); retrieval is then run again on that sentence. A wrong or empty rewrite finds nothing rather than inventing evidence, because the rewrite only feeds the search and the retriever's precision gates (ADR 014) still decide what reaches the model.
- `model-searches`: the model asks for notes itself. Reserved, not offered until tool-calling exists (`_CAPABILITY_LIMITS` in the prompt says the engine cannot run tools yet), and expected to suit cloud models more than small local ones (gemma2 through Ollama is believed not to support native tool calling, unverified).

**The rewrite is visible.** The rewritten query is carried on the turn result and shown in the CLI reply header's grounded-notes segment (ADR 016), so a wrong rewrite can be seen. It is never presented as something the user said and is not stored as a turn.

**The extra call's prompt must also fit the window** (ADR 015): it is built from the last few turns, not the whole history, and is sized by the same budget code.

## Open questions (to close when built)

- How many recent turns the rewrite sees (two or three is the starting guess), and whether it sees the assistant's replies as well as the user's (the reply often holds the noun that "it" refers to).
- Whether the rewrite runs on the chat model or on a separate, cheaper model chosen by a setting; the extra call's latency on a local model, cold and warm, is unmeasured.
- The `recent-words` carry-over rule, and whether it should exist at all if `rewrite` is good enough.
- Where the orchestration lives (`engine/turn.py` or a small new module, to keep files under the 200-line cap), reusing `grounding.retrieve` and `model.call_model`.
- Failure classes to test with the real model: a topic change whose message has no words of its own (the old topic's notes must not be attached), and a chit-chat message that must not get an invented query ("how are you today?" after a notes discussion).
- Whether a rewrite that itself finds nothing should say so in the header.

## How it will be built and checked

Eval first, as with ADR 014: follow-up cases (a fixture history plus a bare follow-up) are added to the deterministic retrieval eval with a fake rewriter, so retrieval stays testable without a model; the rewrite quality and latency are measured separately with the real model. `code-review`, revert-and-watch-it-fail checks, and a live turn follow, and ADRs 014 and 006 get pointers.

## Consequences (expected)

One extra model call on a miss when the mode is `rewrite`, which is the reliability-versus-cost dial ADR 014 left for this slice; a knob to turn it off; a small local model may write poor rewrites, which the precision gates contain but do not fix.

## Alternatives rejected

- **Rewrite on every turn.** Costs a call per turn to fix the minority of turns that miss; retrieve-first pays only when needed.
- **Enumerating follow-up phrases** ("why did we", "what about"). Wording-dependent and brittle; the trigger is structural.
- **Only searching on the last few turns concatenated.** Kept as the free `recent-words` mode, not the default, because it attaches stale notes on a topic change.
- **Model-driven search as the first step.** Needs tool-calling and round trips; reserved as the fourth mode.
