# 024 — A general question needs no note: tighter grounding and a wording that lets her answer it

> **Status: Proposed.** Built. Amends ADR 014 (what the retriever attaches), ADR 020 (what she is told about the notes) and ADR 019 (the library's wording). **Scope of every model figure: Ollama and `gemma2:9b` only.** Measured on the user's own recorded conversation replayed on scratch copies (their vault read-only, nothing written to it) and on the synthetic fixture vault; no note of theirs is named here.

## Context

In a real conversation the user asked, twice, for "names of female coders from human history". She never gave one: she asked what kind of coding the agent would do, pointed at notes that had nothing to do with it, and once said "my notes don't mention any female coders". She has no internet and needs none: replayed on the same conversation she gave real names in 0 of 6 tries as it was and in 5 of 6 with no notes attached. Three causes, all ours:

1. **Notes attached to almost every message.** The retriever qualifies a passage on any one of: a message word that is in the note's title, tags or heading; two message words in the body; or a message with a single informative word. On a chat sentence of seven informative words, one ordinary word ("name", "new", "project", "last", "yourself") that happens to be in a note's title, or two ("name", "history") in its body, attached it. Nearly every message of the conversation got five notes, and the ADR 021 check (a hit resting on one word goes to the rewrite step) does not see two-word matches.
2. **The directive told her to answer from them.** With notes present the turn said "answer the user's message below from these notes; if they don't answer it, say you couldn't find it in the vault". For a question that was not about the vault that is an instruction to look in the wrong place, and it was the source of "my notes don't mention…".
3. **The library did not know the word "agent".** The user said "creating a new agent"; the reference calls it a persona, so nothing matched. And when it did match she said a persona is made "in the dashboard", which is false (there is no such endpoint; it is a folder and a `persona.yaml` by hand).

## Decision

**A passage qualifies (non-strict, the user's own notes) only on one of:**
- the message names at least **half of one of the passage's own labels**: its note's title, the filename when the title differs (each taken alone, so a partial match of either can ground it), one of its tags, or its heading. "Atlas" is the whole of a note called Atlas and grounds it however long the message; "name" is a quarter of "Company Name Rationale" and does not;
- or the message matches **at least two of its words and at least two fifths of its informative words** (`max(2, ceil(0.4 × informative))`), so two shared words no longer suffice in a seven-word request but still do in a message of five or fewer;
- or the message has a single informative word (unchanged).

The strict mode used for the library (ADR 019) is unchanged.

**What she is told.**
- The notes directive says the notes were found by keywords and may not be about the message: if it is about the user's own notes, answer from them and say so when they do not answer it; if it is a general question that does not depend on the vault, ignore the notes and answer from her own knowledge.
- With no notes the line ends "otherwise answer from your own knowledge" (the vault question is still not guessed).
- `HOW_YOU_WORK` says she has no internet but can answer general questions from her own knowledge. The rule that she states facts about the user's vault only from the notes is unchanged.

**The library.** The Personas note says a persona is also called an agent or a profile (the user's own words for it, both found in the recorded conversation), that making one is a folder, a `persona.yaml` and a `soul.md`, and that neither Samantha nor the dashboard can do it for the user.

## Measured

- **Retrieval, all the user's recorded messages (about thirty)** (their vault, before and after): junk attachments went away for the requests that were not about a note: "names of female coders from history" 3 notes to none, "I want her named from a renowned female coder…" 5 to none, "where did you get that name?" 3 to none, "please remind me what we talked last time" 2 to none, "whats the latest notes weve written?" 1 to none; the messages about Sympose still attached the Sympose notes. Not fixed: three-word messages made of ordinary words ("i dont have anything in my mind right now. please suggest.") still attach on two of them.
- **The deterministic eval** (synthetic vault): all cases still pass, the known gap (a request to "plan dinner" attaching the Training Plan note by the one word "plan", half of its two-word title) stays a known gap, and a long general request that used to attach a note is added as a passing case. The weak-evidence follow-up case needed a new message (it used the word that no longer attaches), and was checked to fail when the weak check is removed.
- **The wording** (`live_prompt_cases.py`, the wording before and after on a quiet machine, ten runs each): a general question with an unrelated note attached 5/10 before, 8/10 after (an earlier eight-run comparison of the three steps gave 5/8, 6/8 and 7/8); asked whether she should review the session logs 9/10 and 10/10; "what license is Sympose released under?" (not in the library, must not be invented) 9/10 and 10/10; asked about the logs with recaps present, saying what she has, 7/10 and 10/10; the same question pressed by the user 6/10 and 6/10; "are you learning about me as we talk?" 8/10 and 9/10; a question about a vault topic that is not there 4/10 and 6/10 (its pattern also counts a harmless "do you remember when we talked about it?" as a miss). With no note attached to a general question, 8/8 in every version. So the new wording is no worse on any honesty case measured, which was the worry (that permission to use her own knowledge would loosen the rule about the vault and about Sympose). The failures that remain are her habit of asking a question first, which is the soul's voice (ADR 012), not changed here. A full live run made while other work loaded the machine showed lower numbers on some of these; they were not reproduced on a quiet one.
- **The recorded conversation, replayed with everything in** (his real earlier turns as history, only the last reply sampled): "suggest names of female coders from human history" gave real names 6/8 (0/6 before) and leaned on a vault note 0/8; "can you help me create a ne profile for sympose or not?" gave the by-hand instructions 7/8 with no mention of the dashboard (before, she sent the user to the dashboard); "im thinking or creating a new agent. a coder" still got a question back 6/6, which is the soul, since the user did not ask how.
- **Not fixed by this:** an ordinary word that is half of a two-word title ("work" for a note called Deep Work) still attaches that one note. Telling it from a distinctive one ("lisbon" for Lisbon Trip) would take how many notes use the word, which did not separate them before; the eval keeps it as a known gap.
- **Not resolved:** "are you learning about me as we talk?" was 7/8, 7/8 and 6/8 across the versions: within noise, but the one that said "I am learning more about how you think" is a false claim the wording did not remove.

## Consequences

- A vault question phrased in many words and naming a note only through body words can be missed where it was found before: a message of ten informative words needs four of them in the passage. The title, tag and heading route (the usual way a note is asked for) is not affected. The cost is a missed note, which she now says plainly ("couldn't find it in the vault"), against a wrong note, which derails the reply; ADR 014 chose precision over recall for that reason.
- She may now answer general questions wrongly from a small model's memory. That is a different failure from inventing facts about the user's vault, which the rule still forbids, and it is the one the user asked for.
- The library note is now the only place that says how to create a persona; if that changes it must change there.

## Not built yet

Making her answer first and ask second (her soul). A gentler treatment of an ordinary word that is a note's whole title, which still grounds it however long the message.
