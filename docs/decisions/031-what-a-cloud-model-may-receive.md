# 031 — What a cloud model may receive: known to the user, approved by the user, one setting per category

> **Status: Accepted** (2026-09-27, the user approved the defaults). Built in two slices, both done: the engine, then the CLI. The defaults below change what a cloud model receives today. Settles issue #79.

## Context

Local models are the default and a cloud model is opt-in, by choosing one in the model picker. That choice is the only consent there is. Four paths carry content out of the machine once a model that is not local is in use (a model is local when its id starts with `ollama/` or `ollama_chat/`, as `budget.is_ollama` already decides):

1. **The chat reply.** The prompt holds the persona's soul, the conversation so far, the recaps of earlier conversations, the grounded notes (title, path, heading and text of each passage), the Sympose reference passages, and the user's message.
2. **The follow-up rewrite** (ADR 017): the recent conversation and the message, to the chat model.
3. **Recap writing** (ADR 023, and #15: recaps use the chosen model): the user's messages from earlier conversations (the assistant's replies are left out of the request), sent again to the model that writes the recap.
4. **Embedding** (ADR 027): the embedding model is local by default (`ollama/nomic-embed-text`), but `embedding_model` is a setting. If it names a cloud embedder, every passage of every note in scope, and every message, is sent to it, with no notice.

Nothing tells the user which of these carry their notes, and nothing lets them refuse one. This gets more serious as reading grows: ADR 030 adds properties (emails, phone numbers), and #78 adds a vault map and connected notes.

## Decision

**Some things leave the machine by the nature of using a cloud model, and the user is told.** The user's own messages and the conversation so far go to the model they chose, and the Sympose reference passages (public documentation shipped with the product) are not the user's data. These have no setting. They are named in the notice below.

**Everything derived from the user's vault is a category, with one setting.** `cloud_share` in the settings file is a list of the categories a cloud model may receive; it is empty by default. The categories:

- `notes`: passages of the user's notes placed in a prompt (text passages and title passages), and the notes and messages sent to a cloud embedding model.
- `properties`: a note's frontmatter properties as a passage (ADR 030, stage 2).
- `recaps`: the recaps of earlier conversations placed in a prompt, and the writing of recaps by a cloud model.

Later categories (`vault_map`, `connections`, #78) are added the same way and start out of the list. Everything is allowed for a local model, since nothing leaves the machine.

**Default: nothing is shared.** With `cloud_share` empty, a cloud model gets the conversation and the reference passages and no note, property or recap. This changes today's behaviour for a user who already chose a cloud model: their grounded chat stops using their notes until they allow it. That is on purpose (a user should approve what leaves), and it is not silent (below).

**Not silent: three places.**
- **The notice.** Choosing a cloud model in `/model` shows what will be sent, always (the conversation) and by approval (each category, with its current state), and asks, for each category, whether to share it. The answer is stored in `cloud_share`; declining is the default.
- **The prompt.** When a category is withheld from a cloud model, the model is told, so it does not claim the vault has nothing (as ADR 015 does when passages do not fit): "Notes in the vault matched this message, but the user has not allowed notes to be sent to this cloud model. Don't say the vault has nothing on it: say you cannot use the notes with this model, and tell the person you are talking to that they can allow it with /share; write "you", not "the user"." Recaps and properties have the same line, worded for them (`prompt_text`).
- **The reply header.** A cloud turn shows what was sent and what was held back: `cloud: notes, recaps` and `withheld: properties` (the CLI's header, ADR 013 and 016), and the turn record (ADR 025) gains the same two lists, still paths and ids, never text.

**Changing it later: `/share`** lists the categories with their state for cloud models and toggles one. The web app gets the same when it has a chat (#29).

**One place decides.** A module `sharing` holds the category names, `allowed(model)` (all of them for a local model; the settings list for any other) and the filter that removes withheld passages from a turn's grounding by their kind. The turn calls it once, before the prompt is built, so the prompt, the token count and the record all see the same set; recap writing and the embedder call it too. A withheld cloud embedder falls back to keyword search like an unreachable one (ADR 027), with one warning, and search for the user's own notes stays on the machine.

## Consequences

- A user can see, and refuse, what a cloud service receives; the default is that nothing of the vault does.
- A cloud model is less useful out of the box (no notes) until the user approves. The prompt line and the header say why and how.
- Properties (ADR 030) need only a new kind and a category, no separate rule; the interim rule in ADR 030 (properties never go to a non-local model) is replaced by the `properties` category, off by default.
- Compaction (#19) and the vault map (#78) get a place to declare what they send.
- The interception is at prompt assembly, so a new path that calls a model without going through it would bypass the setting: the four paths above are tested with a fake cloud model, and a new path adds a test.

## Alternatives rejected

- **Leave today's behaviour on by default and only add a notice.** Rejected: the user has said what goes to a cloud service must be approved, not announced.
- **One switch for "the vault may go to the cloud".** Rejected: properties and recaps carry different risks than note text, and a user may allow one and not another; a short list keeps the choice honest.
- **A per-model setting.** Rejected: the question is what kind of content leaves, not which provider; a per-model list multiplies the settings for no gain.
- **Filtering inside retrieval.** Rejected: retrieval runs on the machine, before the model is known to matter; the model is known where the prompt is built.
- **Warning only when a cloud embedding model is set.** Rejected as too narrow: it is the largest single exposure (the whole vault), but the same rule serves it, so it is one category with one gate.

## Built: slice 1, the engine

`sympose/engine/sharing.py` holds the categories, `allowed(model)`, `gate(model, grounding, recaps)` (called once in `run_turn`, before the prompt is built) and `embeds_notes(embedding_model)`. The setting is read fail-closed: anything that is not a list of known names shares nothing it did not name. Recap writing (`recap_refresh.refresh`) does nothing for a cloud model without `recaps`; `semantic.refine` searches the user's notes by keyword only, and the launch-time build skips them, when the embedding model is a cloud one without `notes`. The shipped library is not an exception: it is public, but the message that searches it is not, so a cloud embedder without `notes` gets no embedding at all (found in `/code-review`). A running build asks again before each batch, so turning `notes` off with `/share` stops it. `TurnResult` has `cloud` and `withheld` (empty for a local model), and a cloud turn's record has the same two lists in `sent`. The prompt builders' blocks moved to `prompt_blocks.py` and the record to `turn_record.py`, to stay under the file-size cap.

**Measured (2026-09-27, `ollama_chat/gemma2:9b`, synthetic prompts only, no vault content, a scratch settings file).** The model is told the notes matched but were withheld and does not say the vault is empty: 2/2 replies say it cannot use the notes and point to `/share`; recaps 9/10 (the miss did not name `/share`). The first wording ("the user can allow it") made the model speak of "the user" to the user itself (2 of 5 replies addressed them as "you"); "tell them they can allow it" was worse (1 of 5); adding "write "you", not "the user"" gave 5 of 5. The control (nothing withheld, nothing found) still says it could not find anything in the vault. This is one small local model; a cloud model will read the same line and is expected to follow it at least as well, but that is not measured here.

## Built: slice 2, the CLI

`sympose/cli/share.py`. `/share` opens a numbered list of the three categories with their state; choosing a row flips it, saves `cloud_share` and reopens the list (Esc closes it), so several can be changed at once. Choosing a cloud model in `/model` says what it receives ("it receives your messages and this conversation. From your vault it may receive: ...") and, when some category is not yet approved, opens that same list at once: leaving it with Esc keeps everything off, which is the default. The same sentence, without the list, is shown at start-up when the model in effect is a cloud one (from `chat_model` or the persona's own) and when a persona with a cloud model of its own is chosen. A cloud turn's header gains `cloud: <categories sent>` and `withheld: <categories held back>` before the note line, so the note line still fits the room left; a local turn shows neither. The shipped reference library (Privacy and data, Choosing a model, Settings, Chat commands, How Samantha uses your notes) says the same, since Samantha answers questions about privacy from it, and the reference eval has two cases for it.

**A consequence to know.** The conversation is not a category, so the assistant's earlier replies travel to a cloud model as history. If the user talked with a local model, whose replies quoted their notes, and then switches to a cloud model in the same conversation, those quoted notes go with the history even with `notes` not approved. Closing this needs a rule for history (drop the assistant's replies from the session when the model changes to a cloud one, or start a new session on the switch); it is not built, and needs the user's call because it changes what "this conversation" means.

## Not built yet

Stage 2 of ADR 030 (a properties passage) must gate that passage at the embedding step by its own category, not only by `notes`: `embeds_notes` checks `notes` alone, and `category_of` never returns `properties` until such a passage exists, so the `properties` switch has no effect yet.

Later: `sympose doctor` reporting which cloud model is chosen and what it may receive (ADR 029), and a web-app settings screen for the categories.
