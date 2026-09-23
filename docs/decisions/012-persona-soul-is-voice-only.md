# 012 — A persona's soul is voice only; engine rules stay in the engine

## Context

Every turn's system prompt opens with `PLACEHOLDER_SOUL`, one hardcoded sentence shared by every persona (ADR 006 deferred the real thing as "its own later piece of product writing"). ADR 011 gave each persona a directory with room for `soul.md`. Legacy's `samantha_soul.md` is the obvious starting point, but at 5.9KB it mixes four different things: voice and temperament; grounding and anti-hallucination rules; a syntax of action tags (`[CREATE_PERSONA]`, `[REMEMBER]`, `[WRITE_NOTE]`...) for features this rewrite has not built, along with a claim of "absolute mastery" of Sympose; and the maintainer's own first name hard-coded into the text. Only the first belongs in a shipped soul. It is also roughly 1,500 tokens on every turn, which costs speed on a small local model and gives a long instruction list more chances to be followed unevenly.

## Decision

**Soul is voice and temperament, nothing else.** `profiles/<handle>/soul.md` describes how the persona talks and what it is like to talk to. It never contains rules every persona must obey regardless of voice (those are engine rules), never describes capabilities, tools, or a domain of expertise (`expertise.md`, and MCP tool-calling, when they exist), and never contains anything specific to one user. It is kept short, on the order of 1.5KB, so it stays cheap on every turn and easy for a small model to hold.

**Engine rules stay in the engine.** The grounding instruction stays in `engine/prompt.py`, appended after the soul, for every persona, so a user-written persona with a two-line soul still gets zero-hallucination grounding and no soul can weaken it, because it comes last. Testing on the real model (below) showed the soul's warmth makes a small model improvise, so the engine's rules were extended, still engine-level and still after the soul: do not claim to know things about the user that are not in the conversation or the vault context; if the user refers to something not visible ("that layout"), ask what they mean; say "couldn't find it in the vault" rather than a false "I don't have access to your notes"; and a short, explicit statement of what the engine cannot do yet (create or change notes, personas, or settings; run tools), so a warm voice never plays along with an action that will not happen. That last statement is temporary by design and is removed or narrowed when tool-calling (MCP) lands.

**Loading.** `profile.load_soul(handle)` reads `profiles/<handle>/soul.md` and returns its text, or `None` when the file is missing, empty, or unreadable. The prompt builder uses it, and falls back to a generic companion soul (the old placeholder, renamed `DEFAULT_SOUL` since it is now the real fallback, not a stand-in) for any persona without one, so a persona created with only a `persona.yaml` still works. The soul is read at prompt-build time, per turn, not inside `get_profile`: `get_profile` runs on every vault route, none of which need a soul, and reading per turn means an edit to `soul.md` takes effect on the next message with no restart. A read failure other than "file not found" is logged and degrades to the fallback rather than failing the turn.

**Samantha's soul ships.** `profiles/samantha/soul.md` is one of the two files `.gitignore` already allows to be committed for her. It is written from legacy's voice sections only, generalized to any user, and does not name the film it draws on (naming it invites a small model to role-play the film's character instead of being warm and natural). Personalization stays as VISION.md describes: the user edits their local copy, and the drift is theirs.

**Verified against real model calls, not by reading.** On `gemma2:9b`, the project's default local model, over a small scratch vault with real grounding, six prompts (casual talk, an ambiguous reference, a grounded question, a request for an opinion, a request for something the engine cannot do, a question the vault does not answer) plus a request for a numbered plan, comparing the generic fallback soul with Samantha's. What it found, in order:

- The first draft changed the voice clearly (warm, prose, real questions) but the model improvised: it described a "layout" it could not see, claimed to know the user had been "giving Atlas a lot of thought", and played along with creating a persona. A prompt that reads well does not guarantee any of that, which is why these were measured, not assumed.
- The engine-level additions above fixed those: on repeated runs the ambiguous prompt asked what was meant 2/2, the persona request was declined honestly 2/2, and the no-match question said it could not find a note 2/2, while the grounded question was still answered correctly 2/2.
- A remaining flaw was the soul's own curiosity line nudging the model to read into people ("that walk you took yesterday", "weighing on your mind" from one journal line). It was reworded to ask rather than assume, and the invented dates and feelings stopped in the follow-up runs.
- Prose-first did not cost the ability to list: asked for a numbered plan, Samantha produced one in 2 of 4 runs where the generic fallback produced one in 0 of 4.
- Model output varies run to run; these are small samples on one small model, enough to catch the failures above and not a benchmark. A different model is a separate check.

Two findings surfaced that are not soul problems and are left for their own work: a title-only search hit gives the model just the note's title as its snippet, so the note's actual content never reaches the prompt for that hit; and content matching is a plain substring test, so "day" matches "today" and attaches an unrelated note to a casual message.

## Consequences

Every persona without a `soul.md` sounds like the generic companion, as today. A soul file is trusted text: a very long one costs prompt space on every turn and nothing caps it, which is acceptable for a single-user local tool. The soul cannot describe what the persona can do, so a persona will not claim capabilities from its voice file; the model did over-claim in testing, which is why the engine-level statement of current limits now exists and applies to every persona; it is removed when the capability arrives. Legacy's Sympose-mastery and action-tag material is deferred, not lost: it is expertise and tool-calling content for their own milestones.

## Alternatives rejected

- **Porting legacy's soul verbatim.** Rejected for the four-way mixture above, chiefly because it would instruct the model to emit action tags for features that do not exist and to know a specific person by name.
- **A `soul:` field inside `persona.yaml`.** Rejected: a paragraph of prose is awkward in YAML, and ADR 011 already gave each persona a file for it.
- **Loading the soul inside `get_profile`.** Rejected: file I/O on every vault route for a value only the chat engine uses.
- **Requiring a soul for every persona.** Rejected: a persona defined by only its config must still work.
- **Putting the grounding rules in Samantha's soul.** Rejected: they would then apply to Samantha alone, and a custom persona's soul could omit or contradict them.
- **Testing on the qwen2.5-14b model that happened to be handy.** Rejected: the default model is what users run, and small-model instruction-following is precisely what a soul depends on.
