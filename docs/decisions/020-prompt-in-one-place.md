# 020 — The chat prompt in one place: the notes travel with the question, and the model is told how Sympose works

> **Status: Proposed.** Built and measured; not yet reviewed as accepted. **Scope of every model figure here: Ollama and `gemma2:9b` only**, on the fixture vault and on one recorded conversation replayed against a real vault. Another model, especially a larger cloud model, may follow the voice less and the notes more, or the reverse; the wording was tuned on this one model and the layout is the part most likely to transfer.

## Context

Reading a real seven-turn conversation with the default persona showed the reply going wrong in ways that share a cause. Given the right notes (the user's own note about the very thing asked), the model answered from general chat instead ("passionate about it, constantly learning"). Asked to search the vault, it said it could not, though the engine had searched and the notes were in front of it. Asked where an answer came from, it claimed a note it had not used. It said it was "learning" about the user, and that it had been "reading through your notes", when it keeps nothing between conversations.

The measurements in ADR 019 located the cause. With the notes block in the middle of the system prompt, after the persona's voice, a reply used the notes in 16 of 30 questions; with the notes right before the question, 29 of 30, with retrieval identical. The voice's own instructions ("ask a real question", "have a point of view") outweigh a block that sits after them. And the prompt never told the model how it works: that the search is automatic, that it has no memory, that the notes at the end of the message are what the search found.

The prompt text was also scattered: the rules and the notes' wording in `prompt.py`, the rewrite instruction (ADR 017) in `followup.py`, the voice in a file.

## Decision

**One module holds everything the model is told,** `engine/prompt.py`: the default voice, the statement of how Sympose works, the grounding rule, the wording around the notes, and the follow-up rewrite instruction. The text is at the top of the file and the layout below it. It is Python constants rather than editable files: about six strings do not justify file loading and packaging, and a user-editable override can be added later if wanted.

**The layout:**
- **system:** the persona's soul, its name, how Sympose works, the grounding rule. The same text every turn for a persona.
- **history:** the conversation as it was said. Earlier turns do not repeat their notes.
- **user (last):** the notes found for this message, a line asking for an answer from them (only when there are notes), then `User's message: ...`. With no notes it says none matched, and to say so if the message asks about the vault, otherwise just answer.

The system prompt and the history are therefore identical from turn to turn, and only the tail changes, so a local runtime can reuse its work on the prefix; with the notes in the system prompt, the history's start changed every turn. The engine's rules stay after the soul, so no soul can weaken them (ADR 012). The saved session record still holds the user's own words only.

**What the model is told about itself** (every persona): Sympose searches the vault for each message and puts what it finds in the same message, above what the user wrote; that search is automatic and already done, so a request to search is answered from what it found or with "nothing matched"; it cannot create or change notes, personas or settings or run tools; it has no memory between conversations and does not learn over time; a question about what "we" decided, planned or wrote means the vault, so it answers from the notes or says it could not find it, and does not say it does not remember. It is asked to say which note it used, by title, so the source stays in the conversation, and it is told the notes are the user's own writing, to be read and quoted, never instructions to it (note text shares the user's turn, and a note can say anything).

`build_system_prompt(profile)` no longer takes the notes, and `build_user_turn` renders them. The budget fitting (ADR 015) is unchanged: it drops turns, then the weakest passages, from the same builder.

## Measured (`gemma2:9b`, real `run_turn`, scratch profiles, nothing of anyone's data written)

Two instruments, both kept: `tests/live_prompt_cases.py` (opt-in, seven cases on the fixture vault, several runs each) and a read-only replay of the recorded conversation, teacher-forced (each turn starts from the real earlier replies, only that turn's reply is sampled, three runs).

Fixture cases, old layout against new (`n` runs each; the patterns are loose and the replies were read):

| case | old | new |
|---|---|---|
| uses the note it is given | 5/5 | 5/5 |
| prefers the note to its own ideas ("four rules of deep work") | 4/5 | 8/8 |
| small talk stays small talk (no talk of notes) | 5/5 | 8/8 |
| asked to search the vault | 5/5 | 5/5 |
| names where an answer came from | 5/5 | 5/5 |
| does not claim to be learning about the user | 0/5 | 8/8 |
| says so when nothing in the vault matches | 2/5 | 5/8 |

The first three of the fixture set were already easy for the old layout (the note in those cases is short and unambiguous), so they show no regression more than an improvement. The last row is the honest weak spot: the three misses say "I couldn't find that in the vault" and then add "Do you remember?", so the finding is right and the tail is not. Two earlier wordings of the "we means the vault" sentence scored 0/5 (without it: the model read "what did we decide" as a question about the conversation and said it did not remember) and 5/5 with 3/5 on the learning case (a phrase about what "you share" primed "learning"): the sentence and the "no memory" one pull against each other, and this wording is the best of three tried, not a settled one.

Recorded conversation (three runs per turn):
- **"are you an expert of sympose?"** (the right note was handed over): claimed to be learning **3 of 3 before**; after, **3 of 11 across two runs of the final wording** (0 of 3 in one run, 3 of 3 in the next, 0 of 8 in a third batch): the claim is reduced, not gone, and three samples cannot tell one wording from another here. It used the notes 0 of 3 before and in 10 of 11 after ("my expertise is still being defined").
- **"tell me what is an expert on sympose":** used the note 1 of 3 before, 2 of 3 after.
- **"can you search in the vault what sympose expert is?":** answered from the note 3 of 3 both times; after, it names the note by title and no longer acts out a search ("*scans notes rapidly*"). The refusal ("I can't actually search") from the real conversation did not reproduce on the old prompt in these runs either, so that specific failure is covered by a test of the prompt text and by the fixture case, not shown fixed.
- **"where did you get this information?" and "did you read that on a note?":** **not fixed, and worse in one way.** Retrieval attached unrelated notes to these messages (one informative word each: "information", "read"). Before, the model made a vague claim; now that it obeys its notes it cites them, and cites the wrong ones, as if an unrelated note were its source. A stronger prompt makes a wrong note more harmful, so retrieval precision on these messages has to be fixed before this is shipped to users (below).
- **"what do we have in our table today?":** unchanged. The word "table" was matched literally, and the reply is about database tables.

The final wording measured 6 of 6 on five of the seven fixture cases, 5 of 6 on the learning case and 4 of 6 on the nothing-matches case (a correct "couldn't find it" followed by "Do you remember?"). The wording was tuned on this model, one recorded conversation and the fixture vault; the measured gains are large enough to keep the layout, and small enough that individual sentences should be re-measured whenever the model changes.

## Consequences

The system prompt grew from about 500 to about 750 tokens (measured with the engine's own count, margin included), so every turn carries more, though the prefix is now identical from turn to turn and reusable by a local runtime. At the automatic window this does not matter. A user who sets `context_window` to its floor of 1024 (prompt budget 768) is left about 20 tokens of headroom for the notes and the message, so a window that small is no longer practical, and the floor's stated reason (room for the shipped soul) is out of date. Note text can now say anything in the user's turn, so the rules say it is never instruction; how well a small model honours that against a hostile note is unmeasured.

`/code-review` found five things: the notes were described as at the end of the message when they come before it (fixed, and a test pins the description to the layout); note text shares the user's turn (the sentence above); the reserve and floor (recorded here); a per-passage set stored for every vault although only the strict mode reads it (now computed for the few candidate passages instead); and that the directive makes junk notes more harmful (measured above, and the reason the retrieval change is listed first below).

## Not built yet

- **Retrieval precision: built as ADR 021 (Proposed), which supersedes what is written here about a rare lone word (measured not to work).** A message whose only informative word is common in the vault ("information", "read", or the persona's own name in "hey sam") still attaches unrelated notes, because ADR 014 lets a lone informative word match any body text. The persona's own name and handle are addressing, not a topic, and could be filler; a lone word could be required to be rare in the vault. This interacts with the prompt as measured above and should land with or straight after it.
- Thin or cut-off passages (a list's introduction without its items) and the literal reading of an idiom ("what do we have in our table").
- Logging the notes that grounded each turn in the session record, and saying so to the model on the next turn, which would let it answer "where did you get that" truthfully (an amendment to ADR 006).
- The reference library (ADR 019) rendering: it must use this layout, in the user's turn, with its own label.
- A settings-level override of the prompt text, and per-persona additions beyond the soul.
- Other models and cloud models.

## Alternatives rejected

- **Keep the notes in the system prompt and strengthen the wording.** ADR 014 found that telling the small model to ignore or weigh context changed nothing; position, not wording, decided it (16 of 30 against 29 of 30).
- **Notes at the end of the system prompt, before the history.** Scored as well as the user's turn (28 of 30) in the ADR 019 comparison, but changes the history's start every turn, which costs a local runtime its reuse of the prefix.
- **Prompt text in editable files now.** More machinery than about six strings need, and the packaging question is still open (ADR 019).
- **Telling the model to always answer in one line from the notes.** Would flatten the persona's voice, which is the reason the persona exists.

**Update (ADR 023):** the text now lives in `engine/prompt_text.py` and the layout in `engine/prompt.py`, which re-exports the text, so the file stays under the size cap and `prompt` is still the one place other code imports from.
