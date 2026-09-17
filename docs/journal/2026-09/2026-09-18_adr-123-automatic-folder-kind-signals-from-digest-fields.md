---
title: "ADR-123 — Automatic Folder-Kind Signals, Derived From Existing Digest Fields"
created: 2026-09-18
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - sympose/grounding
---

# ADR-123 — Automatic Folder-Kind Signals, Derived From Existing Digest Fields

- **Status:** Accepted (design; implementation pending). Raised by damiro in
  discussion after the
  [2026-09-17 ritual-continuation fix](./2026-09-17_ritual-continuation-carries-no-grounding.md):
  "defining each folder in the vault will make the agents' decisions more
  reliable." Originally documented ahead of any build decision; a follow-up
  discussion the same day (see **ADR-123.4** below) refined the design to
  also cover write-shaped turns, explicitly framed as raising response
  reliability rather than as a wholesale replacement for the recall-intent
  keyword check it sits behind — no live incident yet demonstrates the
  specific failure mode this would close (see **Revisit trigger** below).
- **Date:** 2026-09-18
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

No folder in a Sympose-managed vault has a declared "kind" anywhere. An
agent only ever sees a folder's bare name (from directory discovery), or
whatever `VaultManager.get_folder_digest`
([vault.py:187](../../../sympose/vault.py#L187)) extracts per note - a
fixed set of frontmatter fields (`name`, `title`, `aka`, `tags`,
`birthday`, `created`, `up`, `author`) when present. Nothing tells the
model up front that `People/` holds contact records rather than journal
entries, or that `Movies/` holds media reflections rather than personal
history; it infers that, if at all, from whatever fields happen to show up
in whatever content actually gets retrieved that turn.

The 2026-09-17 fix closed a *different* gap in the same live transcript
that prompted this discussion: a random-note-pull ritual ("let's do
another one") wasn't carrying its grounding across turns, so no real
content reached the model at all on some turns, and it fabricated a
reflection and a fictional title. That fix ensures real content is always
present once a ritual is engaged. It does not, and was not meant to, give
the model any sense of what *kind* of folder that content came from -
Samantha already named the folder correctly (`People/`) in the transcript;
the failure was inventing content, not misreading real content she had.

damiro's proposal is a related but distinct idea: declare each folder's
purpose up front so agent decisions (how to phrase a reflection, what tone
to take, whether to treat a field literally) are more reliable once real
content *is* in hand. This ADR documents that idea and a concrete,
zero-configuration way to build it, without committing to build it yet.

## Decision

Proposed, not yet implemented:

- **ADR-123.1 — Structural signal, not hand-authored text.** Do not ask
  users to write a description per folder (rejected below - see
  Alternatives). Instead, derive a folder's structural signature from
  data `get_folder_digest` already extracts: the fraction of a folder's
  notes carrying each known frontmatter field. A folder where most notes
  have `birthday`/`aka` reads structurally as a contact/people folder; one
  where most notes carry `tags: [movie, ...]`-shaped values reads as a
  media-reflection folder. This needs no new field list beyond the one
  `get_folder_digest` already scans for, no LLM call, and no per-vault
  configuration - it self-derives from whatever the user's own notes
  actually contain, so it works identically on a vault it has never seen
  before.
- **ADR-123.2 — Cache it the same way ADR-070.3 already caches folder
  walks.** Compute the field-presence statistic alongside
  `get_folder_digest`'s existing `_get_vault_snapshot` mtime cache
  ([vault.py](../../../sympose/vault.py)) rather than re-scanning per
  turn - it is a byproduct of a walk that already happens, not a new one.
- **ADR-123.3 — Surface as one line, not a paragraph.** Whenever a folder's
  digest, a full-body note from that folder, or a random sample from it is
  injected as ground-truth context — on a read turn *or* immediately before
  a write action targets that folder — prepend a single structural line
  (e.g. "This folder's notes mostly carry: birthday, aka - likely
  personal/contact records.") derived from the cached statistic. Silent (no
  line at all) when no recognizable field clears a presence threshold - a
  folder of free-form prose gets no signal, rather than a guessed one.
- **ADR-123.4 — The write-path gap, and narrowing the keyword gate rather
  than widening it.** `resolve_turn_context`'s folder-scope case
  (`vault_turn_context.py`'s `_resolve_folder_scope_case`) already matches
  a message against real, discovered folder names — a structural check, not
  an enumerated one. But it only runs when `has_intent` is true, and
  `has_intent` (`vault_recall.py`'s `search_triggers()`) is itself a fixed
  list of recall keywords ("remember," "recall," "what do I know about," …).
  A write-shaped message ("add Dylan's birthday to People/") rarely trips
  it, so today writes mostly get no folder context — digest signal or
  otherwise — at all. The fix is not to add write-shaped phrases to that
  list (more of the same enumerable pattern this project keeps moving away
  from); it's to make the real-folder-name match the primary gate on its
  own, independent of `has_intent`, and demote the keyword list to
  disambiguating *what kind* of content to pull once a folder is already
  matched (digest vs. a random sample vs. a targeted search) rather than
  deciding whether folder-context fires at all. Framed deliberately as a
  reliability improvement, not a claim that this replaces catch-phrase
  gating everywhere in the codebase — ADR-124 already narrowed a different
  catch-phrase list to a coarse gate elsewhere, and this is the same
  direction applied to `has_intent`'s specific role here, not a general
  mandate to remove it.

## Consequences

**Positive** (anticipated - not yet implemented)

- Zero configuration: no user ever writes a folder description, and the
  signal is correct for any vault's own naming and organizing habits, not
  just conventional folder names.
- Zero round-trip: purely a statistic over data already read off disk for
  the digest; no added LLM call, consistent with Sympose's round-trip-frugal
  design (the same principle behind rejecting ADR-070.4 above it in the
  index).
- Degrades safely: a folder with no recognizable fields simply gets no
  signal, rather than a wrong one.

**Negative / costs**

- A presence statistic is coarse - correlation, not semantic
  understanding. A `People/` folder that mixes real contacts with a few
  narrative essays about people would get a signal that's right on
  average but wrong for the minority notes.
- Needs a place to live in the existing mtime-cache structure; a small,
  bounded addition, not a new subsystem.
- Does not, on its own, fix any failure observed so far - see **Revisit
  trigger**.
- ADR-123.4 means more turns pull a folder digest than do today - any
  message naming a real folder, not just ones phrased as a recall
  request. That's the intended effect (writes stop being blind to folder
  context), but it does raise how often `get_folder_digest`/
  `get_random_sample_notes` run per session versus today's narrower gate.
  Still zero-round-trip (no LLM call added), just more frequent disk-cache
  reads against an already-cheap, already-cached statistic.

## Alternatives rejected

- **Hand-authored per-folder definition prompts.** Discussed directly with
  damiro and rejected: requires the user to write and maintain a
  description for every folder in every vault, which cuts against Sympose
  working usefully on any vault out of the box, and is exactly the kind of
  manual-labeling upkeep this project generally avoids in favor of
  structural signals.
- **Widening the existing fabrication-catch phrase lists (`_VAULT_CLAIM_RE`
  and friends in `engine.py`) to reference folder purpose.** Rejected as
  more of the same enumerable-phrase-list pattern that the 2026-09-17 fix
  deliberately moved away from; it doesn't generalize to wording nobody
  has enumerated yet.
- **Adding write-shaped phrases ("add," "create," "new entry for," …) to
  `vault_recall.search_triggers()` so writes trip `has_intent` too.**
  Considered as the obvious minimal patch for ADR-123.4's gap and
  rejected: it's the same enumerable-list pattern applied to a new set of
  words, and just as brittle against phrasing nobody thought to list. The
  real-folder-name match already sitting in `_resolve_folder_scope_case`
  is the structural signal that should gate this, not a second keyword
  list running in parallel with the first.
- **One-time LLM classification per folder, cached.** Not rejected
  outright, but not proposed here: it would add real round-trip cost
  (even if amortized/cached) for a benefit that ADR-123.1's zero-cost
  structural statistic may already deliver. Worth a look only if the
  structural signal proves too coarse in practice.

**Revisit trigger:** a live incident where the model has genuine, real
content in hand (i.e. the 2026-09-17 fix already did its job) but visibly
mishandles it *because* it doesn't understand the folder's purpose - e.g.
narrativizing a contact record instead of relaying its fields plainly.
No such incident has been observed yet; the transcript that prompted this
discussion was a missing-content bug, not a misread-content one.
