# 021 — Weak evidence is not enough to ground a reply: a one-word match is checked by the rewrite step, and the persona's own name is no evidence

> **Status: Accepted.** Amends ADR 014 (the retriever) and ADR 017 (the follow-up rewrite). **Scope of the model figures: Ollama and `gemma2:9b` only**, on a recorded set of twelve real messages replayed read-only against a real 679-note vault, and on the fixture vault. Another model may write different rewrites.

## Context

ADR 020 made the model obey the notes it is given, and so made a wrong note more harmful: in two real conversations, every one of twelve messages had unrelated notes attached, and the model now cites them ("It's from your ... note") or volunteers them. Reading the messages and what each attached showed four different causes:

- **The persona's own name.** "hey sam, how are you?" has one informative word, `sam`, the persona addressed by a nickname, and it matched five notes (design notes that mention her, and a film review).
- **Contractions typed without an apostrophe.** "whats", "arent", "theres" are not in the filler list (only the apostrophe forms are split into filler by the tokenizer), so "whats with our table today?" matched four daily journal entries whose heading is "Whats up", some of them private.
- **A lone ordinary word.** "where did you get this information?" (`information`), "did you read that on a note?" (`read`), "what did we talked about last time?" (`last`, a word in a note's title) each attached notes on one common word: ADR 014's rule that one informative word, or one title or heading word, is enough.
- **Meta questions about the conversation itself**, which are not lookups at all.

**A rarity threshold does not separate them** (measured on the real vault, 679 notes): `information` is in 5.7 percent of notes, `read` 7.5, `last` 8.0, and legitimate topics are no rarer, `revwr` (a project) 7.1, `obsidian` 4.3, `sympose` 2.7. The difference between a generic noun and a name is meaning, which counting cannot see. The persona's name was in 0.6 percent of notes, so rarity would have let it through too.

Privacy makes this more than a quality problem: with a cloud model, whatever is attached is sent to the provider, and a private journal passage was attached to a casual message.

## Decision

1. **The persona's own name is no evidence.** A message word that is a word of the persona's name or handle, or a prefix of one (at least three characters, so `sam` for Samantha), is probably addressing her. It is still searched (it may be a topic: "who is Sam?"), but a hit is not counted as matching that word, so a hit resting only on her name is weak (point 3). Her names are the `name`, the `handle`, and an optional `aliases` list in `persona.yaml` (a list of names, or one name; anything else is ignored), which also goes into her prompt ("The user may also call you Sam or Sammy"), since nothing else told her what else she is called. The shipped Samantha lists `Sam`. Removing the word from the search was tried first and rejected in review: for a persona named after a role ("Editor") it would drop the topic word "edit" from "how do I edit notes".
2. **Contractions typed without an apostrophe are filler**: the closed grammatical set (whats, thats, arent, theres, dont, im, ...), excluding those that are also words in their own right (id, ill, cant, wont). With the apostrophe the tokenizer already splits them into filler.
3. **Weak evidence is checked by the rewrite step.** A first search is *weak* when every hit rests on a single matched message word (not counting her name). It is then treated like an empty first search: the same small model call from ADR 017 (same model, same window) writes a standalone query or `NONE`, which now also applies with no earlier conversation (the prompt says it is the first message). If it answers `NONE`, the weak hits are dropped and nothing is grounded. If it writes a different query, that query is searched and its hits are used (and shown as `searched "..."`); if that finds nothing, nothing is grounded. If it writes the message again, ignoring case and punctuation, the weak hits stand, as the model has vouched for them. If the rewrite cannot run (knob off, model error, reply cut off, a model that cannot do the step, no vault) the weak hits stand as today: the model cannot judge, and precision is not bought by silently changing what a non-judging setup does. Strong evidence (two distinct message words in a passage) never pays the call. A message with one informative word ("tell me about Atlas") always counts as weak and pays the call: the cost of not enumerating what a topic looks like.

The trigger stays structural (the strength of the evidence), never a list of phrases. The knob `grounding_followups: "off"` turns the step off entirely, including this use.

Each hit now carries how many distinct message words it matched (`matched`, not counting her name), so the strength is read from the hits, not recomputed. The rewrite prompt's first sentence now says the message *may* refer back to the conversation (it was tuned with earlier turns always present), and shows "nothing yet: this is the first message" when there are none.

## Measured (`gemma2:9b`)

The rewrite step on the twelve real messages, three runs each, with the real history before each: a greeting gives `NONE` three times in three; the meta questions become queries built from the conversation ("where did you get this information?" becomes a query about the tables just described, which is where the answer came from); and ten of ten legitimate lone-word questions ("who is Dylan?", "tell me about Revwr", "how's the Postgres decision going?", with and without earlier conversation) came back as proper queries. Known weakness: on "what did we talked about last time?" and "arent you supposed to review our session logs?" the rewrite pulls in words from earlier turns ("our table", "remove Git commit"), the mixed-topic risk ADR 017 recorded.

## Result

What the twelve real messages attach, three runs each through the whole step with the real model (before: every one of the twelve had unrelated notes attached):

- **"hey sam, how are you?"** (asked twice): five unrelated notes, now nothing, in every run (the name filter).
- **"where did you get this information?":** unrelated marketing notes, now the technical specification and database schema notes, which are where the previous answer came from.
- **"did you read that on a note?":** a Git snippet and a quote, now the notes about the topic being discussed.
- **"whats with our table today?":** four journal entries whose heading is "Whats up", one of them private, now none; it still finds the database specification, because the model reads "table" literally. The idiom is not solved.
- **"what did we talked about last time?":** the rewrite carries "our table" over from an earlier turn, so it attaches specification notes and a journal entry: still wrong, in a different way (the mixed-topic weakness above).
- **"arent you supposed to review our session logs?" and "theres history and session logs...":** these match two real words in real notes (a code review, a functional specification), so they count as strong and are not checked; the meaning is not what the user meant, which retrieval cannot see. That is a job for the model and the reference library (ADR 019).

So of the twelve, three still attach the wrong notes, two are wrong by meaning, and the rest attach nothing or the right notes; no journal entry reached the prompt. The fixture cases with the real model showed no regression (five of seven at 5 of 5; "where did you get that?" 4 of 5 and "says so when nothing matches" 3 of 5, both within the noise of earlier runs and on a path this change does not touch). 528 tests, and 19 mutations of the new rules were each caught (one survivor, the handle being ignored, led to a test where handle and display name differ); the design then changed after review (below) and 21 mutations of the final code were each caught.

After `/code-review` the design changed as described above (the name is kept in the search but is no evidence; a narrower contraction list; a case-insensitive same-query check; the first-message prompt wording), and the twelve real messages were run again: the same picture (nothing for "hey sam", the source notes for the provenance questions, no journal entry), and 24 of 24 runs of eight legitimate lone-word questions found their notes, including "who is Sam?", while "hey sam, how are you today?" and "thanks sam!" attached nothing (3 of 3 each).

The cost is one short model call on weak or empty first searches (about half a second warm on the measured model), including on a first message with no earlier conversation, which never paid it before. `grounding_followups: "off"` removes it.


## Not built yet

- A message whose word for a topic is also her name is left to the model's judgement; there is no other way to tell them apart.
- The mixed-topic rewrite (above), and a check on models other than `gemma2:9b`.
- Logging the notes per turn is built (ADR 025). Letting the model see, next turn, what its last answer used is not (ADR 025 never reads the record back into a prompt).

## Alternatives rejected

- **A rarity threshold for a lone word.** Measured above: the junk words are no rarer than real topics.
- **Requiring more than one word whenever the message addresses the assistant ("you").** "what do you think about Atlas?" and "do you know who Priya is?" are ordinary lookups with one topic word; this would lose them.
- **Capitalization as a proper-noun signal.** People type in lower case.
- **Asking the model on every turn.** ADR 014 rejected a model as relevance judge for every turn; here it is asked only when the evidence is weak.
- **Dropping weak hits without asking.** Loses "who is Priya?", the case the one-word rule exists for.
- **Removing her name from the search.** Cleaner, but wrong for a persona whose name is a role or an ordinary word ("Editor", "Research Assistant", "Grace" as in a grace period), and "who is Sam?" would find nothing.
