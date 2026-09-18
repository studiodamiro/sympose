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

- **Status:** Fully implemented (123.1-123.5). ADR-123.1-123.3 (the folder-kind
  signal itself, its cache reuse, and surfacing it on both
  `get_folder_digest` and `get_random_sample_notes`) shipped 2026-09-18,
  then verified live against a real ~800-note vault and fixed twice more
  based on what that surfaced (case-insensitive key matching; weighing a
  field against its vault-wide baseline, not just local presence) - see
  `sympose/vault_folders.py`'s `_folder_kind_signal` and 20 tests in
  `tests/unit/test_vault_folders.py`, and **Implementation notes** below.
  ADR-123.4 (the write-path gate) also shipped 2026-09-18 - see
  `vault_turn_context.py`'s `_resolve_folder_scope_case`, now gated on a
  real folder name alone, and verified live against the same real vault
  with two keyword-free write-shaped messages. ADR-123.5's *finding* half
  (generalizing the real-name gate from folders to any real note/title)
  also shipped 2026-09-18 - see `_resolve_real_referent_case`, verified
  live against the same real vault and fixed once based on what that
  surfaced (a ranked-search substitute for a confirmed-real but
  near-empty stub note - see **Implementation notes** below). ADR-123.5's
  *miss-surfacing* half also shipped 2026-09-18, scoped to possessive
  mentions only (`_resolve_possessive_miss_case`) after damiro pointed
  out that capitalization can't be assumed at all for his own casual,
  mostly-lowercase chat - both that scoping decision and the false
  positives it surfaced (English contractions are syntactically
  identical to a genuine possessive) are covered in **Implementation
  notes** below. Raised by damiro in discussion after the
  [2026-09-17 ritual-continuation fix](./2026-09-17_ritual-continuation-carries-no-grounding.md):
  "defining each folder in the vault will make the agents' decisions more
  reliable." Originally documented ahead of any build decision; a same-day
  follow-up discussion refined it twice more — first to also cover
  write-shaped turns (**ADR-123.4**), then to a broader underlying
  principle damiro named directly: "every thing on the vault [is] already
  defined... it's the agent's job to find, confirm, and if it's not there,
  tell the user - not everything needs an action" (**ADR-123.5**). No live
  incident yet demonstrates the specific failure mode this would close (see
  **Revisit trigger** below) — this ADR documents where the design has
  landed, ahead of building any of it.
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
- **ADR-123.5 — The underlying principle: the vault is ground truth; find,
  confirm, then judge.** Talking this through surfaced something bigger
  than folder signals on their own. Every real thing in a Sympose vault -
  every person, project, note, folder - already exists as a fact on disk.
  Whatever the user says is just their own wording of something that
  either maps onto one of those facts or doesn't; it's the agent's job to
  check which, not the user's job to phrase things in a way that trips the
  right trigger. That reframes ADR-123.4 from a narrow fix (loosen one
  gate for folder names) into a general instance of a wider mechanism
  that's mostly already built:

  - **Finding and confirming is mechanical, so it should stay
    mechanical.** `vault_grounding.py`'s `real_vault_referents_from_snapshot()`
    already builds a cached, cheap, vault-wide set of every real note
    stem, title, and folder name - built for ADR-124, but only ever run
    on the *model's own reply*, to catch it naming something that doesn't
    exist. The exact same check, run on the *user's incoming message*
    instead, answers "does this text refer to something real?" with no
    wording assumptions at all - a plain mention of "Dylan" matches if
    and only if something real named Dylan actually exists, independent
    of recall keywords, folder names, or any phrase list. This is the
    natural generalization of ADR-123.4's folder-name gate: the real
    referent set already includes folder names as a subset, so the same
    mechanism that fixes the write-path gap for folders extends to
    people, projects, and individual notes for free.
  - **Deciding what a hit or a miss *means* is not mechanical, so it
    shouldn't be forced into one.** A confirmed hit grounds the reply
    (with its folder's kind-signal from ADR-123.1-123.3 attached). A
    miss is handed to the model as a plain fact - "no vault entry found
    for 'Dylan'" - and nothing more is decided in code. Whether that fact
    is worth surfacing to the user at all depends on whether the
    conversation actually implied wanting something done about it, which
    is a judgment call about the whole shape of what was said, not
    something a keyword or a rule can reliably make. Most mentions need
    no action; forcing every miss into an "offer to create an entry"
    response would be exactly the kind of guessed, unwanted proactivity
    this project's zero-bloat instincts already push against. The
    system's job stops at supplying the fact; the model's job is
    deciding what, if anything, follows from it.

  Put together, ADR-124 and ADR-123 turn out to be the same idea applied
  in two directions: ADR-124 checks the model's *outbound* claims against
  what's real; ADR-123.5 checks the user's *inbound* mentions against the
  same ground truth. Neither needs an enumerated phrase list, because
  neither is asking "does this sound like a request" - both are asking
  "does this refer to something that demonstrably exists."

## Implementation notes (123.5, shipped 2026-09-18)

`vault_turn_context.py`'s `_resolve_real_referent_case` (case 7.5) runs
`VaultManager.first_unverified_referent` on the inbound message once cases
1-7 have already tried and case 7 hasn't already matched a folder name.
On a confirmed real referent, it reads that exact note directly via
`read_note` - the same resolution case 3 (quoted title) already trusts -
rather than handing the confirmed name to a ranked, vault-wide search.

That distinction turned out to matter immediately against the real
vault: `Limbo/Life.md` and `Limbo/Time.md` are genuine notes (a 0-byte
placeholder and a near-empty stub, respectively - exactly what a "Limbo"
catch-all is for), so "life" and "time" are real referents. An ordinary,
unrelated sentence that happens to start with either word ("Life is good
today.", capitalized only because it opens the sentence) confirmed as
real and then - in the first version of this fix, which called
`_recall_hit` the same way case 7's folder search does - fell through to
a *ranked* vault-wide text search for the bare word, which surfaced a
wholly unrelated `Quotes/` note that merely contained "life" in its own
filename. A confident-looking wrong substitute, not a wrong referent
check: the referent match itself was correct, but resolving it via search
instead of a direct read handed back the wrong note entirely. Reading the
confirmed name directly fixed this outright: `Limbo/Life.md` (genuinely
empty) now correctly yields nothing, and `Limbo/Time.md` (near-empty but
real) now correctly surfaces its own actual content instead of someone
else's. Verified with a new regression test
(`test_real_referent_that_is_an_empty_stub_yields_no_hit`) and against
three live model replies (local `ollama`) on "I ran into Dylan today,"
"Time flies when you're having fun," and "Life is good today" - all
three came back natural and un-confused, with no visible mishandling of
the near-empty `Time` content that was now correctly in context.

**Capitalization can't be assumed on the way in.** damiro pointed out
directly that he doesn't capitalize proper nouns in his own casual chat
("i ran into dylan today"), which the finding-side fix above didn't yet
account for - `first_unverified_referent`'s candidate extraction only
ever matches Title-Case runs, so it silently missed most of damiro's own
messages naming something real. Rather than making that shared function
capitalization-agnostic (and risking the outbound fabrication check's
already-verified behavior along with it), a separate function -
`real_referent_mentioned` - does the same real-referents lookup with a
case-insensitive scan instead. It also fixes a subtler problem a naive
case-insensitive regex would have reintroduced: a single greedy 1-3-word
window, tried once per position, can *swallow* a real name into a larger
window that matches nothing ("ran into dylan" as one 3-word candidate
never tries "dylan" alone) - the fix tries every window size at every
position, longest first, so an embedded name is never skipped over.

**The miss-surfacing half, scoped to possessive mentions.** Once
capitalization is off the table as a filter, the earlier plan to
distinguish "sentence-initial capital" from "an intentional name" no
longer applies either. The one signal that survives without
capitalization: a possessive ("marco's birthday," "dylan's school") is a
strong, wording-independent indicator that the speaker is treating a word
as a specific named thing. `_resolve_possessive_miss_case` (case 9, the
final fallback) extracts every possessive-shaped mention and, if none of
them resolve to a real vault referent, hands the model one plain fact -
`"### Vault Check: no real vault entry found for 'X'."` - and decides
nothing further.

That scoping needed one more fix once tested against real sentences:
English contracts plenty of pronouns and adverbs with `'s` too - "let's"
("let us"), "it's"/"that's"/"who's"/"here's" ("it is," etc.) - which are
syntactically identical to a genuine possessive and were all initially
flagged as misses ("I'm bored, let's play a game" reported "no entry
found for 'let'"). Fixed with `_CONTRACTION_ONLY_WORDS`, a closed set of
English function words (demonstratives, wh-words, personal and
indefinite pronouns, temporal deictic nouns like "today's") that
contract but never possess a specific real thing. This is a bounded
grammatical category, not an enumerable list of phrasings someone might
use - nobody will ever name a vault entry "It," "Let," or "Today" for
this to wrongly suppress, which is the same reasoning that already
justifies stopword-style filtering elsewhere in this project without
reopening the enumerable-phrase problem it otherwise avoids.

Verified with 29 new pure-function tests in `test_vault_grounding.py`
(case-insensitive matching, window-swallowing, contraction/pronoun/
temporal exclusions) and new `resolve_turn_context` integration tests in
`test_vault.py` against a sandboxed `tmp_vault_dir`, plus targeted,
read-only checks (`VaultManager.resolve_turn_context` directly, no
write-capable persona involved) against the real vault for lowercase
mentions, possessive misses, and ordinary contractions - all behaved as
designed.

## Implementation notes (123.1-123.3, shipped 2026-09-18)

Two things surfaced only by testing against a real ~800-note vault
(`~/Development/garden`), not the synthetic fixtures written alongside the
code - worth recording since both were real bugs/gaps, not edge cases:

- **Case-insensitive key matching.** Real notes had accumulated
  `title`/`Title`, `created`/`Created`, `up`/`Up` as inconsistently-cased
  YAML keys (different tools/eras of editing the same note) - the
  presence tally originally matched keys case-sensitively, so a field on
  ~98% of a folder's notes silently split into two ~50% halves, neither
  clearing the threshold. Fixed by lowercasing keys before tallying, with
  a per-note dedupe so a note carrying both casings doesn't double-count
  its own presence.
- **Vault-wide distinctiveness weighting (123.1 extended).** The
  Consequences section below originally anticipated this only as a
  possible future problem ("worth a look only if the structural signal
  proves too coarse in practice" - see the LLM-classification entry under
  Alternatives). Testing against the real vault confirmed it immediately:
  `created`/`title` are common enough vault-wide that they surfaced as
  "the signal" for `Code/`, `Limbo/`, and `Projects/` alike, distinguishing
  none of them. Fixed by comparing a field's local presence against its
  own vault-wide presence (`cls._get_vault_snapshot(mv, [mv])`, itself
  cached the same way as the folder-scoped call - one extra cached read,
  not a new disk-walk pattern) and requiring at least a 25-point margin
  before calling it distinctive. After the fix: `created` dropped out of
  every folder's signal, `Limbo/` moved from a misleading "created" line
  to honest silence, and the genuinely distinctive folders (`People/`,
  `Movies/`, `Quotes/`, `Thoughts/`, `General/`) kept accurate,
  human-legible signals straight from real tagging habits.

## Consequences

**Positive**

- Zero configuration: no user ever writes a folder description, and the
  signal is correct for any vault's own naming and organizing habits, not
  just conventional folder names.
- Zero round-trip: purely a statistic over data already read off disk for
  the digest (plus, after the fix above, one additional cached vault-wide
  read for the distinctiveness baseline); no added LLM call, consistent
  with Sympose's round-trip-frugal design (the same principle behind
  rejecting ADR-070.4 above it in the index).
- Degrades safely: a folder with no recognizable fields simply gets no
  signal, rather than a wrong one - confirmed live against a real vault
  (`Recipes/`, `Reading/` had 0 matching notes; `Writing/` had 1 - all
  correctly silent).

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
- ADR-123.5's finding half runs the referent check on every incoming
  message not already resolved by an earlier case - a wider surface than
  123.4 alone. Still hot-path safe on the same terms
  `first_unverified_referent` already established for the outbound
  direction: one cached frozenset build per vault-freshness-window, one
  regex scan over the (short) incoming message per turn, one direct
  single-note read on a confirmed hit - no unbounded work, no added LLM
  call, consistent with the sub-1s TTFT SLA.
- A confirmed real referent can still be a near-empty stub note (see
  **Implementation notes**), so a coincidental match on an ordinary
  common word can inject thin, marginally relevant content on an
  otherwise unrelated remark. Verified live that this degrades safely -
  the model handles it as ordinary optional context and doesn't force it
  into the reply - but it is a real, observed cost, not a hypothetical
  one, and is the direct trade for not enumerating which words are
  "common enough" to distrust.
- ADR-123.5's miss-surfacing half only fires on a possessive-shaped
  mention, by design - it will not report a miss for every other way of
  naming something new ("my friend Marco just moved" has no possessive,
  so it stays silent even though "Marco" isn't in the vault either). That
  narrowness is deliberate (see **Implementation notes** for why an
  unscoped version reopens the same noise problem the capitalization-only
  version had), but it does mean this half of ADR-123.5 catches a real
  subset of mentions, not every one.
- ADR-123.5's miss-surfacing half deliberately leaves "was an action
  implied?" undecided in code - once a miss is confirmed, the plain fact
  is handed to the model and nothing more is decided. Verified live on
  both a local and a cloud model with names confirmed absent from the
  vault beforehand: the local model (`ollama/gemma4:e4b`) answered
  plainly - "I don't have any information on Zephyr's birthday... there
  isn't an entry for them in the vault" - while the cloud model
  (`gemini/gemini-3.6-flash`) stated the same absence and then also
  offered to log a note ("If you'd like me to log details... just let me
  know!"). Both are correct: no fabrication either way, and the
  plain-statement-vs-proactive-offer difference is exactly the kind of
  per-model, per-turn judgment call this ADR deliberately leaves
  undecided rather than forcing one way or the other. A real cost is that
  this ADR cannot promise consistent
  behavior here the way a hard rule could; it depends on the model's own
  judgment per turn, same as any other conversational nuance. That's an
  accepted tradeoff, not an oversight: a wrong hard-coded rule (offering
  to create an entry on every passing mention, or never offering at all)
  would be worse than variance driven by actual conversational judgment.

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
  structural statistic may already deliver. The coarseness concern this
  was hedging against did show up in practice (see **Implementation
  notes**), but the fix that closed it - weighing a field against its
  own vault-wide baseline - stayed structural and zero-round-trip, so
  this alternative remains unneeded rather than newly justified.
- **A hard-coded rule for when a miss should offer to create an entry**
  (e.g. "always offer" or a heuristic guessing whether the mention was a
  request). Rejected per ADR-123.5's own reasoning: judging whether an
  action was implied depends on the whole shape of the conversation, not
  a pattern that can be enumerated correctly in either direction - always
  offering is noisy proactivity nobody asked for, never offering wastes
  the fact that was already found. Left to the model, informed by the
  plain fact of a confirmed miss.
- **Guessing which folder a brand-new, not-yet-existing subject belongs
  in** (e.g. inferring "Dylan" is person-shaped from message wording
  alone, to pre-select a folder before any note exists). Rejected: the
  folder-kind signal (123.1) only describes folders that already contain
  notes of that kind, so there is no structural fact to check a guess
  against for something that doesn't exist yet - guessing here would be
  exactly the kind of invented certainty this whole ADR exists to avoid.
  If the model raises the idea of creating an entry, which folder it goes
  in stays a question for the user to answer, not a classification the
  system performs on their behalf.

**Revisit trigger:** a live incident where the model has genuine, real
content in hand (i.e. the 2026-09-17 fix already did its job) but visibly
mishandles it *because* it doesn't understand the folder's purpose - e.g.
narrativizing a contact record instead of relaying its fields plainly.
No such incident has been observed yet; the transcript that prompted this
discussion was a missing-content bug, not a misread-content one.
