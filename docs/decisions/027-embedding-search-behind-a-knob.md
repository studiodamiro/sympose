# 027 — Search notes by meaning as well as by keyword, behind a knob

> **Status: Proposed.** Built as opt-in: the default stays keyword search, so nothing changes until someone turns it on. Amends ADR 014 (what the retriever attaches), ADR 019 (how the library is searched) and ADR 002's "no embeddings yet". **Scope of every figure: Ollama, `gemma2:9b` for the chat model and `nomic-embed-text` for meaning-based search only.** Measured on an invented vault and invented messages, plus a read-only look at the user's own vault whose note names are not repeated here.

## Context

ADRs 014, 021 and 024 made keyword retrieval stricter, and it still cannot tell what a message is about. A message that shares two ordinary words with a note attaches it, and a wrong note derails a small model. Sympose questions are the sharpest case, because words like "profile", "vault", "model", "settings" and "session logs" are both how Sympose works and what people write notes about: "can you create a new profile for me?" attached database-schema and employee-profile notes, "how do I switch models?" a note about a model railway. The other end of the same wall: a message that shares no words with a note ("what storage engine did we pick?" for a note that says SQLite) finds nothing, and "how do I add another vault?" did not find the library note "Add or switch vaults".

Several ways to tell the sources apart were compared on the same labelled messages (below). The one that needed no extra chat call and scored best was searching by meaning: each passage is turned into a list of numbers by a small embedding model, the message is too, and a passage is attached only when the two are close enough.

## Decision

**A knob, `grounding_search`, in the settings file** (a user-facing default is a setting, not a constant):

- `keywords` (the default): today's search, exactly, and no embedding model is touched.
- `embeddings`: passages are chosen by closeness of meaning alone. The best five notes (three from the library) whose best passage reaches the threshold are attached, up to two passages each.
- `hybrid`: the keyword search runs as today, then a keyword hit is kept only if its note is reasonably close in meaning (the threshold minus 0.06), and notes that are close (the threshold minus 0.02) are added even with no shared word. Names and rare words (a person's name) still work as they do today, and the junk that shared only ordinary words goes.

Any other value, a hand-edited typo, or a missing file leaves `keywords`.

Two more knobs: `embedding_model` (default `ollama/nomic-embed-text`; any embedding model litellm can call) and `embedding_min_similarity` (default 0.68, a number between 0 and 1; the library uses that minus 0.02, as measured). The threshold belongs to the embedding model: a different model needs a different number, which is why it is a knob.

**Where the numbers live.** A small SQLite cache (`embedding_cache.sqlite`, beside the settings file, gitignored) maps a hash of the model and the passage text to its vector, so a note is embedded once and again only when its text changes. A vault of about 7,000 passages took 86 s to embed the first time; a query takes about 150 ms to compare in plain Python (no new dependency), and the embedding call is 10 to 20 ms. The embedding model and the chat model stay loaded together (measured: no reload).

**The first index is built in the background**, when the CLI starts and when the persona changes (as recaps are, ADR 023), not in a turn. Until the index for the persona's notes is complete, and whenever the embedding model is missing or Ollama is not reachable, a turn uses the keyword search and says so in the log (one warning per run): it never fails a turn or waits for the index, apart from at most 64 passages that are embedded on the spot (a note edited during the chat), and the Sympose library (about 110 passages, a second and a half, once) if its launch-time build has not finished.

**One wording change.** The notes directive (ADR 024) said the notes "were found by keywords"; with a search by meaning that would be untrue, so it says "found by a search". Measured on a quiet machine, 12 replies each, old against new: a general question with an unrelated note attached 7 and 10, asked where a fact came from 12 and 11, a topic that is not in the vault 8 and 6 (that case swings between blocks, 1 and 5 for the new, 4 and 4 for the old, and its pattern is known to be loose). An earlier run of the new wording that overlapped a heavy test run gave 4 of 10 on the first case, which the quiet run did not reproduce.

**What is unchanged.** The follow-up rewrite (ADR 017) and its weak-evidence check (ADR 021) still run: a bare "why did we pick it?" has nothing to embed either. A hit found by meaning counts as strong evidence (`matched: 2`), so it does not cost a rewrite call. Fitting the prompt to the window is unchanged.

**What is recorded.** Each note in a turn's `sent` record (ADR 025) says how it was found (`keyword` or `embedding`) when the knob is not `keywords`, so the modes can be compared on real chats.

## Measured (an invented vault of 26 notes with 9 notes that share ordinary words with Sympose topics; 59 labelled messages: how Sympose works, the user's own notes, notes that clash, general questions, chat)

A message passes when the library attaches exactly when it should, every needed note attaches, and no other note does. Thresholds were chosen on one half and the other half is reported.

| | pass, all / held-out half | messages with a junk note | model calls per turn |
|---|---|---|---|
| keyword, no rewrite check | 69% / 71% | 25% | 0 |
| keyword, as shipped (with the rewrite check) | 71% / 71% | 22% | 0.22 |
| keyword, then a stricter bar when the library matches | 73% / 75% | 22% | 0 |
| one model call to route the message | 59%, then 68% with examples | 17 to 22% | 1 |
| one model call to rerank the keyword hits | 85% / 86% | 3% | 0.7 |
| meaning-based pool, then a model rerank | 86% / 86% | 5% | 0.9 |
| keyword hit kept only if the meaning agrees (`hybrid`) | 85% / 86% | 8% | 0 |
| **meaning only (`embeddings`)** | **90% / 89%** | **0%** | **0** |

Through the built code (`tests/live_retrieval_cases.py`, the default threshold, the same 59 messages): `keywords` 41/59 (69%, held-out half 20/28), `embeddings` 53/59 (89%, 25/28), `hybrid` 48/59 (81%, 24/28). The table above is the prototype, where each threshold was tuned separately; the built `hybrid` derives its two from the one knob and scores a little lower, mostly from the library attaching on messages about the user's own notes. Choosing the threshold on the other half gave 87% and 89%; the good region is broad (83 to 90% for nearby thresholds). The weak spot of meaning only is finding the right note for names and rare words (it found the needed note for 82% of the note lookups, against 91 to 95% for the hybrid and the keyword search), which is what `hybrid` is for. On the user's own vault (679 notes, 7,048 passages) and 41 of their recorded messages, read by hand: keyword search attached a note that did not belong to about 21 messages, meaning only to about 9; "can you create a new profile for me?" and a greeting to Samantha attached nothing, one relevant note ("Agent") was missed, and vague requests that scored 0.68 to 0.72 still attached a note.

## Consequences

- A user can try it and compare with the log: nothing changes until `grounding_search` is set.
- A new optional dependency: an embedding model in Ollama (about 270 MB for the default), pulled by the user (`ollama pull nomic-embed-text`). Without it the knob quietly does nothing.
- A cache file that can be deleted at any time (it is rebuilt), and a first launch that spends a minute or two of the GPU on a big vault, in the background.
- Cloud chat models are not affected: the search stays local either way.
- Meaning-based search is a black box: "why did it attach that?" is answered by a similarity number, not by a shared word.

## Not built yet

Making it the default (waiting on a calibration on the user's real messages), a threshold that adjusts to the vault, a model reranker on top, embedding the user's messages across sessions, embedding models other than the default (the query and document prefixes are set for `nomic-embed-text` only), and showing a note's similarity in the reply header.

## Update: a notice while the index is building

While a build is running the meter line under the chat box (ADR 018) shows `indexing 40%` at its far right, in the same dim style, and it disappears when the build ends. The wording is a label and a number, not a sentence. The number is the share of the passages that build had to embed which are done, over all the builds running (the notes and the Sympose library). It is shown whether or not the meter itself is turned off (`show_context_meter`), because it says something about search, not about the conversation, and it lasts a minute or two once. It is not shown for the few passages embedded on the spot during a turn, and a build that failed shows nothing (the log has the warning). Nothing else about the fallback changes: the turns during the build are searched by keyword. Checked in the real CLI (headless, the user's vault read-only, a scratch cache): the notice appeared within three seconds of launch, climbed from 1% to 98% in about 93 seconds sampled every three, filled the line to the right edge, and was gone when the build ended.
