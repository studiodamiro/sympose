# 026 — Recaps go in the system prompt, not beside the message

> **Status: Proposed.** Built. Amends ADR 023 (where the recap block sits) and the reason ADR 020 gives for putting things in the last user turn. **Scope of every model figure: Ollama and `gemma2:9b` only.** Measured on the user's own recorded conversation replayed on scratch copies (their vault read-only, nothing written to it) and on invented recaps.

## Context

ADR 023 put the recaps in the last user turn, above the notes, because the system prompt did as well on "what were we working on last time?", "where did we leave off?" and a greeting (15 of 15 each), and the last turn keeps the system prompt the same on every turn. Those were all questions about the past.

In a real conversation the user was, mid-chat, asking for a list of names, and an earlier session's recap was about the same task ("suggestions of female coders from history"). Told "ok thats 4.. one more", she answered "You got it! One more name coming right up..." and never gave one; asked "are you ok?" she asked for thoughts on names she had never finished. Replaying that turn with the user's real earlier turns (only the last reply sampled): with the recaps in the message she gave a fifth name in 1 of 8 tries, with no recaps in 6 of 8, with the recaps in the system prompt in 7 of 8, and with only the older recaps in the message 1 of 6. With a clearly worded request ("one more name please") the recaps did no harm in either place (5 of 5). The block sitting right above the user's words reads to a small model as something to react to, so she commented on the conversation ("you're really digging into these names") instead of continuing it. None of the notes were attached in those turns, so it is not the retriever.

A live case rebuilt on invented data (four composers, "5 more please", "ok thats 4.. one more", with a recap of the same task) gave, in two alternating blocks of 8 on a quiet machine, 3 of 16 with the recap in the message and 13 of 16 in the system prompt (2, 1 and 5, 8 in the blocks; an earlier single run of the new placement gave 4 of 8, so the figure is noisy but the direction held every time).

## Decision

The recaps block (label, each recap with its date, the line saying to answer from them, and the "left out to fit the window" line) is the last part of the **system prompt**, after the rules; the last user turn carries only the notes and the message. Everything else in ADR 023 stands: which recaps, how they are labelled, oldest first with the newest last, the cap per recap, the knob, and that they are the first thing dropped when the window is short (fitting still rebuilds the prompt with fewer). `HOW_YOU_WORK` now says the recaps are "given below" instead of "shown with the message".

The cost, which ADR 023 named: the system prompt is no longer the same every turn of a session that has recaps. It changes only when the recaps do (at launch or persona switch, once the background refresh has written one), not per message.

## Measured

`recap-*` in `tests/live_prompt_cases.py`, new placement, 8 replies each: "what were we working on last time?" 8/8; the same when the last conversation was small talk 7/8 (6/8 before); "where did we leave off?" 8/8; "what did I decide about the backups last time?" 3/8 (about 2/5 before, still not solved); a greeting must not mention the recap 8/8; a vault question must not be hijacked 7/8; asked whether she reviews the session logs, saying she has short summaries 7/8 (6/8 before, with the wording "given below" in place of "shown with the message"). So reading the past is no worse in the system prompt, and continuing a chat is much better.

## Consequences

- A request in the middle of a chat is continued, not commented on, when a recap is on the same topic.
- The block's position is a property of a small model; a larger or cloud model may not care, and none was measured.

## Not solved

She still asks a question first before answering (the soul, ADR 012), still miscounts a list, and still repeats an item she already gave.
