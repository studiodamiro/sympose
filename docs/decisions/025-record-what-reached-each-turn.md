# 025 — Record which notes and recaps reached each turn

> **Status: Proposed.** Amends ADR 006 (the shape of a turn in the session log) and reverses one rejection in ADR 016 ("storing the display string in the session record"). Nothing here depends on a model, so there are no model figures.

## Context

The session log records what the user said and what she replied, but not what she was given to reply from. ADR 016 rejected storing the grounded notes because they "are recomputable from the vault". In the conversation diagnosed for ADR 024 they were not: the vault had changed since, the retriever's rules have changed since, and the recaps in front of her depended on which earlier sessions had been written up that day. The diagnosis had to be a replay against today's vault, which shows what would happen now, not what did. A wrong answer ("my notes don't mention…") could not be told apart as a bad note, a bad recap or a bad reply.

## Decision

Each turn record in the session log gains a `sent` object, written from what the model was actually sent (after the window was fitted, so a passage or recap that was left out is not in it):

- `notes`: one entry per passage, `{"path", "heading", "source"}`, where `source` is `vault` (the user's own notes) or `sympose` (the Sympose library, ADR 019). The path and heading only, never the passage text: the note is still in the vault, and the log does not become a second copy of it.
- `recaps`: the ids of the sessions whose recaps were shown, newest first. The id is the recap's file name, so the recap can be opened; the text is not copied (a recap may be edited or regenerated later, and what it said then is what the session's own turns already reflect).
- `searched`: the query a follow-up was rewritten into when that is what grounded the reply (ADR 017), otherwise `null`.
- `history_dropped`: how many earlier turns did not fit the window (ADR 015).

A turn record written before this lacks the key, and nothing that reads a session depends on it, as with `ttft_ms` and `model` (ADR 013). **Nothing reads it back into a prompt**: the history sent to the model and the transcript given to the recap writer are still built from `user` and `assistant` alone, so a stored path can never reach the model or a recap as if the user had said it.

## Consequences

- A wrong answer can now be diagnosed from the log alone: the notes and recaps she had, and whether the window pushed anything out. Retrieval changes can be judged against real turns without replaying them.
- The log grows by a few short lines per turn. It still lives only in the persona's own folder, which is gitignored (ADR 001); paths of the user's notes are now in it, beside the messages that already are.
- ADR 016's other point stands: the header line is for display and is still not stored.

## Not built yet

A command or dashboard view that reads `sent` back to the user. A record of the passage scores. Recording the notes of a turn that failed before its reply (a turn is written only once it has a reply, so a failed call leaves no record, as before).

## Note: a note can be listed twice in one turn

A turn's `notes` list has one entry per passage sent, so a long section of a note that was split into two passages (ADR 014) appears twice with the same path and heading. Checked on real turns (12 turns in which it happened, searched again, read-only): all 11 repeated sections were two different passages, not a duplicate. The reply header already shows each note once.

