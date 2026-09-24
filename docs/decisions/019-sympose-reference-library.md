# 019 — A Sympose reference library: read-only notes about Sympose itself, searched by the same retriever

> **Status: Proposed.** The library and its retrieval are built and measured, and a first real-model check was made. The wiring into the engine and the packaging are not built; see "Not built yet". **Scope: Ollama and `gemma2:9b` only for everything a model did** (the live check below); the retrieval numbers are deterministic and model-independent. Cloud models and other local models are unmeasured.

## Context

A persona that can answer questions about Sympose itself (how to add a vault, what a setting does, who made it, what is not built yet) needs that knowledge from somewhere it can be trusted. Today Samantha's soul is voice only (ADR 012) and the engine's prompt states no product facts, so a question about Sympose gets a guess, which is the failure this project treats as a bug (vault grounding is non-negotiable). The retriever was built source-agnostic for this (ADR 014): it takes a list of notes and knows nothing about vaults.

## Decision

**A library of plain markdown notes shipped inside the package** (`sympose/reference/`), so it changes when Sympose changes and always describes the installed version. It is a separate, read-only source: never inside the user's vault, never in the vault's search, tree or graph, and not subject to a persona's `vault_folders`.

**Content: everything about Sympose a user may ask.** What it is and why it is cheap, who made it and when, its history, how it relates to Obsidian, setup, vaults, personas, models, commands, settings, how notes are used, the context meter, privacy and where data lives, the dashboard, troubleshooting, and an explicit list of what is not built yet. The "not built yet" note matters as much as the rest: it is what keeps the persona from claiming capabilities it lacks. Facts in the library are written only from what the repository can show (the code, the ADRs, the git history); a fact that cannot be checked is left out for a person to write.

**Only Samantha reads it.** It is switched on by her profile. Any other persona does not search it, and when asked about Sympose itself it points the user to Samantha (an engine-level rule in the prompt, applying to every persona but her).

**The form the library must have, found by measuring (below):**
- **One question, one short paragraph.** Notes are written FAQ-style: headings are the questions a person asks ("How do I add a second vault?"), each followed by one paragraph that answers it and names its subject. The retriever hands the model at most two passages of about 400 characters per note, so an answer that runs longer is cut in two and can lose half. A test enforces the size.
- **Headings and titles are the strongest signal, so they use the words people use** (add, not adding; stored, not saved; a setting's exact key as its own heading).
- **Titles are specific nouns**, and the product's own name appears in only one title (the overview). One ordinary word in a title is enough to attach a note, so a title such as "The context meter and long chats" attached itself to a question about baking.
- **Examples use neutral words.** An example header naming `Projects/Atlas.md` attached the note to any vault question about an Atlas project; an example question quoting a known weak case matched that very case.
- A note's first line is `# ` plus its own title (enforced).

**Retrieval: the same retriever with a `strict` mode for this kind of source.** The vault rules do not suit a small library written as questions and answers, for two measured reasons:
1. *A word most notes share is ignored* (a word in more than a quarter of the notes says nothing about which note is meant, ADR 014). In a library about one subject, "model", "persona", "settings" and "Sympose" itself are in half the notes, so the questions that use them found nothing. In `strict` mode common words are kept, and the rarity weighting still ranks them low.
2. *One heading word is enough to attach a note* (ADR 014's rule that a title, tag or heading match qualifies alone, and that a message with one informative word qualifies on any match). With headings made of ordinary verbs, "thanks, that helps!" attached `/help`, "rough day" attached a heading about the first days, and "let's talk about something else" attached "What else is missing?". In `strict` mode a passage qualifies only with **two distinct words of the message in the passage's own text or heading**, or when **every informative word of the message is a word of the note's title** (asking for a note by name: "what is Sympose?", "getting started"). A title word does not count towards the two, because the index adds a note's title words to every one of its passages: without this, "I'm getting started on my taxes" attached the Getting started note through its two title words (found by `/code-review`). Likewise a heading that only repeats the note's title, which is what each note's first line does, is not counted as the passage's own heading. The index keeps a passage's title words and its own words separately for this.

Vault retrieval is unchanged: `strict` defaults to off, and the existing 433 tests and the vault eval pass untouched.

## Measured (retrieval only, deterministic, no model)

An eval of 59 cases. 39 are questions written before the notes, worded as a person asks: 33 about Sympose (each must bring a named fact, and the right note first) and 6 ordinary chat messages that must attach nothing. The other 20 are the vault eval's messages (21, less the one that really is about Sympose), which must attach nothing from the library.

- **First run, vault rules, 15 notes as first written: 31 of 58** (the eval was one case smaller then). The 20 misses were the two causes above plus notes not using the asked words and answers longer than a passage.
- **Common words kept: 38. Also no one-word rule: 41.** Ordinary chat still attached notes through headings.
- **Notes rewritten FAQ-style with the strict rule: 56 of 58.** `/code-review` then found the title-word hole, and closing it with the own-words rule left **58 of 59**, the last a documented gap kept as a strict expected failure so it is noticed when it starts passing: for "how do I make a different persona the default?" the right passage is returned but a model note ranks first, because "different" and "default" sit under a model heading. It is a ranking weakness, not a missing answer. (A second ranking gap, "when was Sympose started?", stopped failing once title words no longer counted.)
- 16 mutations of the new rules and the notes, each against a green baseline, were caught; the format guards were checked by breaking a note on purpose.

Expectations changed after seeing results, so the measurement is honest about them: the note file names (titles made more specific), the author question's expected top note (the overview, since "who made Sympose?" has one informative word, the product's name), and the follow-up-search question's top note (the how-to note, which holds the answer, rather than the settings list). Each settings paragraph was reworded to name its subject ("The `context_window` setting is..."), which the form rules require.

## Live check (`gemma2:9b` through Ollama, scratch script, nothing wired)

The engine is not wired to the library, so the prompt was built the way the wiring would, with Samantha's real soul file and the retrieved passages, ten questions the library answers, three runs each.

- **Where the reference sits in the prompt decides whether the model uses it.** With the reference in the middle of the system prompt, after the voice and identity (how the vault block sits today): **16 of 30 answers used it**; the rest were friendly, generic replies ("Okay, I'm ready, what's on your mind?") that ignored the question, an effect of the voice's instructions to be curious and ask questions. With the reference placed after the voice and rules and the instruction "answer the user's question directly from the reference, in your own voice": **29 of 30** (one answer that a pattern check scored as a miss was correct: "Nope, Obsidian doesn't have to be open"). With the reference in the user's turn, right before the question: **29 of 30**. The retrieval was identical in all three. This is a fact about the prompt layout and this model, and it likely applies to the vault block too (unchecked).
- **Questions the library cannot answer** (licence, Windows, PDF export, Notion, monthly cost, writing a note), three runs each, two layouts: most replies said they did not know ("I don't know that about Sympose"), and none invented a licence, platform or feature. Small inventions did appear: pointing the user to "Sympose's website or documentation", "designed to work with lots of different kinds of notes and documents", a guess that Sympose probably runs on Windows because it needs Python, "See that 62%?" after an example figure in a passage, and "a little symbol that looks like a house" for the workspace switcher. The zero-hallucination guarantee is therefore not met by retrieval alone for this source, the same as for the vault (ADR 014).
- **A question about an absent fact still pulls in loosely related passages**: "does Sympose run on Windows?" returned five (cost, setup, settings, model) because "run" and "Sympose" both occur in them. Two ordinary words that a passage also happens to contain is the limit ADR 014 lists, and the strict rule narrows it without removing it ("my kitchen build is not built yet" also attaches the not-built notes).

## Not built yet

- Wiring: a second index built from the package directory, searched for Samantha's turns, with its passages rendered in the prompt as Sympose reference (not as the user's notes), **placed after the voice and rules with a direct instruction to answer from it, or in the user's turn (the live check above; not in the middle of the system prompt)**, and shown in the header as such (`from Sympose: Personas`, distinct from the vault segment, ADR 016), and how the two sources share the passage budget (ADR 015). Whether the vault block should move the same way is a separate, unmeasured question.
- Packaging: the notes ship only if the build includes them as package data (`pyproject.toml` declares no package data today).
- The engine rule for every other persona: for a question about Sympose, point to Samantha. Open question: name Samantha or the default persona, since the default can be changed to another persona that has no library.
- A real-model check of the wired flow, and of a turn that has both vault passages and library passages. Not checked at all: cloud models and other local models, and whether the library passages attach to real vault questions in a real vault (only the fixture vault's messages were tried).
- Keeping the library true as the code changes. Only one fact is guarded (a version named in the notes must equal the package's version). The rest is not: settings, commands and paths named in the notes, the dated history, and facts stated in more than one note (who made Sympose is in two) can go stale unnoticed; a test that fails when a note names a setting or command that no longer exists is the next guard. Until then a change to a setting, command or feature needs its note edited in the same commit.
- `/help` browsing the same notes, and a user-facing documentation build from them (deferred by choice).
- Known limit, carried from ADR 014: retrieval is by literal words, so a question that shares no word with the answer misses it; the library is written to use the words people use, which narrows this and does not remove it. The repository's own `README.md` still describes an earlier state and is not part of this.

## Alternatives rejected

- **Copy the ADRs and the vision document into the library.** They hold rejected options and measurements; a passage saying "we rejected X" is indistinguishable, to a keyword retriever and a small model, from "X is how it works".
- **Put the knowledge in the soul or the system prompt.** Costs prompt space on every turn for a topic asked about rarely, and the soul is voice only (ADR 012).
- **Put the notes in the user's vault.** Mixes shipped text with private notes, appears in their search and graph, is editable by them, and would not update with the package.
- **Vault rules for the library.** Measured above: 31 of 58.
- **Phrase lists** ("if the message contains 'sympose'…). Rejected as in ADR 014 and 017: the trigger is structural (the two-word rule and the note-name rule), and no wording is enumerated in code. The FAQ headings are content, not code.
