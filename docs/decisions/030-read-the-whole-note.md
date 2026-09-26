# 030 — Read the whole note: a note with no body text is still a note, and its aliases and properties are read

> **Status: Accepted.** Not built yet; this record comes first, as the standards ask. Reverses "Not indexed, by choice" in ADR 014 and settles the design points of issue #1. It changes only what is indexed and how it is shown; retrieval, the thresholds of ADR 027 and the weak-evidence check of ADR 021 are unchanged until a measurement says otherwise.

## Context

The grounding index is built from body paragraphs only (ADR 014). A note with no body text has no paragraph, so neither the keyword search nor the search by meaning can return it, whatever its title says. That covers notes that are only properties (a card with a role and an email), outlines (headings with nothing under them) and notes that are only a title, which in some vaults is the whole content (a collection of quotes, each titled by the quote; a daily note titled by its date). Measured on a personal vault of 619 notes: about 156 (25%) have no indexable body, and 7 of the 14 needed notes that the search by meaning missed were of that kind; the two public and synthetic sets used to tune the search (176 and 26 notes) have none, so no earlier measurement showed it. A title-match rescue on top of the meaning search was measured and is not worth it (it fixed 1 of 76 messages), because the notes were not indexed at all.

Two more facts. `aliases` (Obsidian's property for other names of a note) is not read anywhere in the index, so a note is not found by an alias even when it has body text. And a note's other properties are never indexed: ADR 014 left them out because a value such as `status: draft` would surface as prose the user never wrote. That reason stands, and it decides how they are shown (below) and not whether. The vault owner's position is that every property should be read, since properties define a note and link it to other notes.

## Decision

**Every note is indexed, whatever it holds.** A note gets up to two passages beyond its body paragraphs:

- **A title passage, for a note with no body text.** Its text is the note's title (`title:` or `name:`, else the file name) and its aliases. The title is the content of such a note when the title is the content (a quote), and is a label when it is not; the index cannot tell which, and does not need to. The prompt shows it as a note that exists with nothing else in it (`- Title (path): no text besides the title`), so the model is never handed an empty note as if it had content. This is what the issue called "exists, but empty", and it applies to a note with a title and nothing else, which is true of a quote and of an empty stub alike.
- **A properties passage, for a note with frontmatter.** Its text is one `key: value` line for every key with a value. A list is joined with commas; a link is written as the name of the note it points to, so `author: [[Anna Ruiz]]` reads `author: Anna Ruiz`, whether the link is quoted or not (an unquoted `[[Anna Ruiz]]` is read by the YAML parser as a nested list, and is flattened back to the name); a date is written as the date. The passage has the heading `Properties` and the prompt labels it as properties, so a value is shown as what it is and not as prose. It is cut to the size the embedding model takes whole.

**Aliases count as the title.** A note's aliases are added to the term set of its title and to its labels, for every one of its passages, so a message that names an alias is about that note in the same way a message naming its title is (ADR 019, ADR 024).

**What reaches a cloud model.** Properties often hold emails and phone numbers. Until the settings of issue #79 exist, a properties passage is dropped from a turn's grounding when the model is not local, and a title passage is not (a title already travels with every passage of its note). The rule sits where the prompt is put together, since that is where the model is known, and #79 replaces it with a per-category setting.

**Two stages, each kept only if it measures well.** The properties of a note that has a body could pull wrong notes in, since they now compete with the body for the same message. So the work is done in two steps, and the second is not kept unless it passes:

1. Title passages for notes with no body text, and aliases as part of the title. This is the measured gap.
2. Properties passages for every note that has frontmatter.

**How it is measured.** A labelled set of messages about notes of these kinds is built: one in this repository from the synthetic fixture vault (cards with properties, title-only quote notes, outlines, empty notes, notes with aliases, date-titled notes), and one from a real vault that stays private, as before (ADR 027). Each stage is run with the real embedding model on the existing sets and the new one. A stage is kept when the pass rate on the existing sets does not drop (today: 73% and 78% on two real vaults, 89% on the synthetic one, in the default mode) and the new set improves. The real chat model is then asked about a properties fact (an email), a quote by its title, and an empty note, and the replies are read: the fact is given from the note, and an empty note is described as having no text, not filled in.

## Consequences

- A quarter of one real vault becomes findable; a note is found by an alias; a fact that lives only in properties can be answered from the note.
- The index grows by up to two passages per note. New passages are embedded in the background the first time; the vectors of existing body passages are kept, since their text does not change.
- A note with no body is counted as a note in the term statistics, which changes the scores a little everywhere: the existing sets are the check.
- The risk ADR 014 named is real: a passage with almost no words can outscore real text. A title passage starts with the same rules as any passage, and if the measurement shows it over-scoring, it is limited to the label match of ADR 024 (a message that names half of the title) instead of the general score.
- Properties are shown to a local model only at first, so a cloud model answers less than a local one about facts in properties until #79.

## Alternatives rejected

- **A title-match rescue after the search by meaning.** Measured: 1 of 76 messages, and looser rules added more wrong notes than they fixed. The notes were missing from the index, and a rescue cannot return what is not there.
- **Merging properties into the body paragraphs.** A value would read as prose the user wrote and would lengthen every paragraph of the note; a separate, labelled passage keeps them apart and lets the measurement switch them off without touching the body.
- **Title and headings only, without properties.** Simpler and more private, and it finds a card by name but cannot answer from it; the stated position is that every property is read, with what leaves the machine decided by #79.
- **Sending properties to every model from the start.** Rejected: what goes to a cloud service must be known and approved by the user (#79).

## Not built yet

Everything above. Later, and each with its own record: a message about a date ("yesterday") does not match a note titled by that date by meaning, so date-titled notes may need their own handling; links between notes as connections the persona can follow (#78); folder definitions (#23); reports on notes missing a title or properties (#77).
