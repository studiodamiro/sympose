---
title: "ADR-124 — Index-Backed Grounding Checks, With Catch-Phrase Lists Reduced to a Coarse Gate"
created: 2026-09-18
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - sympose/grounding
---

# ADR-124 — Index-Backed Grounding Checks, With Catch-Phrase Lists Reduced to a Coarse Gate

- **Status:** Accepted, implemented and verified 2026-09-18 (ADR-124.2 and
  ADR-124.3; ADR-124.1 is a standing rule for future flows, not a code
  change on its own — see Implementation notes below). Raised by damiro in
  discussion after walking through why `_VAULT_CLAIM_RE`
  ([engine.py:74-80](../../../sympose/engine.py#L74-L80)) let a round-2
  fabrication through in a live transcript ("this one is from the People
  directory" tripped nothing, because "from the ... directory" was never
  an enumerated phrase).
- **Date:** 2026-09-18
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Sympose currently has three independent places that decide "is this turn
vault-related" or "is this reply making an unbacked vault claim," and all
three are hand-enumerated phrase/keyword lists rather than checks against
real vault content:

1. **`_VAULT_CLAIM_RE`** ([engine.py:74-80](../../../sympose/engine.py#L74-L80))
   — output-side. Scans a completed reply for phrasings like "your entry,"
   "in your vault," "here's a summary of what you wrote," or a
   path-shaped string ending in `.md`. If one matches and nothing was
   retrieved this turn, the reply is treated as fabricated (engine.py:906,
   927).
2. **`has_recall_intent` / `_RECALL_LEADINS`** ([vault_recall.py:30-113](../../../sympose/vault_recall.py#L30-L113),
   [vault_recall.py:271-314](../../../sympose/vault_recall.py#L271-L314))
   — input-side. ~50 hand-listed lead-in phrases ("pull up," "tell me
   about," "do i have notes on") plus a fixed trigger-word set ("vault,"
   "note," "journal," "backlink"...) decide whether the *current* message
   is itself a fresh recall request.
3. **The continuation-affirmation check** ([engine.py:883-905](../../../sympose/engine.py#L883-L905))
   — a narrower input-side case: an affirmation regex ("yes," "sure," "go
   ahead"...) combined with a check that the *previous assistant* turn
   used retrieval-offer language ("pull|retriev|check|look up|find|fetch
   ... entry|note|vault|journal"). Meant to catch "yes, please" after
   Samantha offers to check something — but a continuation phrased any
   other way ("another one," "keep going") matches neither regex.

All three share the same structural weakness: they recognize *wording*,
not *reality*. A message or reply that means the same thing in
unanticipated words defeats all three, and this is provably unfixable by
adding more phrases — language has unbounded ways to say the same thing,
so any fixed list is always one step behind the last thing that slipped
through.

Meanwhile, Sympose already has real, structural, non-LLM ground truth
sitting mostly unused for this purpose: `vault_index.py`'s SQLite
full-text index of every real note's path, filename, title, and tags
([vault_index.py:191-230](../../../sympose/vault_index.py#L191-L230)),
built for search but equally usable as a "does this actually exist"
lookup. Separately, `VAULT_PATH_TOKEN_RE`
([vault.py:33-35](../../../sympose/vault.py#L33-L35)) already extracts
path-shaped tokens from text for a related, narrower check
(`_vault_ctx_citation_mismatch`) that compares a reply against a note it
was *actually given* that turn — proving the pattern already works at
smaller scale.

The 2026-09-17 fix
([journal entry](./2026-09-17_ritual-continuation-carries-no-grounding.md))
closed a related but different gap: it made sure a real note is *fetched
at all* on every round of a specific game ritual, which sidesteps the
detection problem entirely for that one flow by making the fetch
unconditional. It does not help any turn outside that specific ritual.

## Decision

Three layers, addressing three different situations rather than one
universal fix (see Status above and Implementation notes below for what
actually shipped):

- **ADR-124.1 — Deterministic fetch for recognized structural flows.**
  Generalize the principle behind the 2026-09-17 fix: any flow the app
  itself controls and knows to be inherently vault-grounded (a ritual, a
  "give me another" game round, a structured recap feature) fetches
  unconditionally, before generation, with no phrase detection involved
  at all. This is not new work so much as a standing rule for future
  flows of this shape — the safest of the three because nothing is being
  *detected*, only guaranteed.

- **ADR-124.2 — Index-backed structural signal added to input-side
  intent detection.** Alongside the existing phrase lists (kept as the
  fast, zero-I/O first check — most recall requests are phrased
  conventionally and don't need an index round-trip to be recognized),
  query `vault_index` for a candidate token on the *prior assistant turn*
  when the current turn is an affirmed continuation ("yes," "go ahead").
  A token that resolves to a real note, folder, or tag counts as recall
  intent there regardless of whether it also matches the offer-language
  regex. Deliberately NOT run against the current user message itself
  with no other qualifier — see Alternatives rejected below for why an
  unscoped version of this check was implemented, caught by code review,
  and removed before shipping.

- **ADR-124.3 — Index-backed structural check replacing most of
  `_VAULT_CLAIM_RE`.** Extract candidate entity/path tokens from a
  completed reply (reusing `VAULT_PATH_TOKEN_RE`'s path extraction, plus a
  lighter bare-word title/folder scan) and check each against
  `vault_index`. A hit that wasn't part of this turn's actual retrieval is
  fabrication, exactly as a regex match is treated today — except this
  catches "the People directory" the same way it catches a fully invented
  filename, because it checks the referent, not the wording. The narrow
  slice of `_VAULT_CLAIM_RE` that catches *referent-less* authority claims
  ("here's a summary of what you wrote," naming nothing specific) has no
  structural equivalent and stays as a phrase check — see Consequences.

## Consequences

**Positive** (anticipated — not yet implemented)

- Closes the demonstrated gap (an entity referenced without matching any
  enumerated phrase) using data that already exists and is already
  indexed — no new subsystem.
- Zero added round-trips: every check is a local index query, not an LLM
  call, consistent with Sympose's round-trip-frugal design.
- Generalizes to any wording for the specific-entity case, which is most
  of what `_VAULT_CLAIM_RE` and `has_recall_intent` currently miss.

**Negative / costs**

- The SQLite index must be fresh (`ensure_fresh`) at the moment these
  checks run; a stale index could miss a just-created note (false
  negative) or, less likely, still list a just-renamed one (false
  positive).
- Two cooperating detection mechanisms (phrase list + index lookup) per
  side is more moving parts than one list, even though each part is
  simple.
- The referent-less authority-claim gap in `_VAULT_CLAIM_RE` is **not**
  closed by this ADR — a known, accepted residual (see Revisit trigger),
  not an oversight.
- ADR-124.2 must stay scoped narrowly (continuation turns, explicit token
  matches) — see Alternatives rejected for why an unscoped version is
  worse than today's behavior, not better.

## Alternatives rejected

- **Fully replacing the phrase-based recall-intent gate with pure index
  matching on every message.** Rejected: an incidental word match to a
  real note title in ordinary chat (a note titled "Coffee," a user saying
  "I love coffee") would spuriously trigger a vault fetch and inject
  unrelated content into casual conversation. The phrase list's job as a
  coarse "is this vault-shaped at all" gate has real value the index
  alone doesn't provide — it stays as the primary gate, with the index
  check added only where the phrase list is known to have a specific,
  demonstrated blind spot (continuation turns).
- **A second LLM call to judge whether a reply is entailed by the real
  vault content** (the classic RAG-verification pattern used elsewhere,
  e.g. citation-checking classifiers). Rejected per Sympose's
  round-trip-frugality principle (`.agents/rules/identity.md`). Would
  close the referent-less-claim residual completely, but at a cost the
  project has consistently declined to pay elsewhere — ADR-123 rejected
  the equivalent alternative (one-time LLM classification per folder) on
  the same grounds.
- **Leaving the phrase lists as the sole mechanism and continuing to grow
  them as new gaps are found.** Rejected as the status quo failure mode
  this ADR exists to move away from — provably always one step behind,
  since it requires enumerating a specific phrasing after it has already
  slipped through once.

**Revisit trigger:** a live incident where a *referent-less* authority
claim ("here's what you wrote," "here's a summary of your journal," with
no specific title, path, or folder named) is delivered with no real
retrieval that turn. None of ADR-124's structural checks cover that case
by design; such an incident would mean the accepted residual has become
an actual live problem, at which point the second-LLM-call alternative
(rejected above on cost grounds) needs to be revisited on its merits
rather than dismissed on principle.

## Implementation notes

- New pure module `sympose/vault_grounding.py` (no I/O, no dependency on
  `vault.py`): `extract_referent_candidates` (path-shaped tokens via the
  caller's `VAULT_PATH_TOKEN_RE`, plus Title-Case runs),
  `real_vault_referents_from_snapshot` (ground truth from data already
  read for folder discovery and the snapshot cache), and
  `first_unverified_referent` (the actual check). Same split as
  `vault_recall.py` — pure logic lives outside `VaultManager`, thin
  wrappers inside it.
- `VaultManager` gained `real_vault_referents(profile)` and
  `first_unverified_referent(text, profile, extra_stop=...)`
  ([vault.py](../../../sympose/vault.py), near the existing recall-subject
  wrappers) — ADR-124.2/.3's actual entry points.
- `engine.py`'s strict-grounding block, now split into
  `_resolve_strict_grounding_subject` (see the complexity-reduction pass
  below), checks `first_unverified_referent` on the prior assistant turn
  when the current turn is an affirmation-shaped continuation (ADR-124.2),
  and on the completed reply alongside `_VAULT_CLAIM_RE` (ADR-124.3). A
  structural hit is used directly as the retrieval subject rather than
  `_entity_guess`'s blind capitalized-word guess, since it's already
  confirmed to name something real.
- `_VAULT_CLAIM_RE`'s own comment
  ([engine.py:64-80](../../../sympose/engine.py#L64-L80)) now documents its
  narrowed, residual role per this ADR.
- Tests: `tests/unit/test_vault_grounding.py` (new, pure-function
  coverage) and a new `TestRealVaultReferentsAndFirstUnverifiedReferent`
  class in `tests/unit/test_vault.py` exercising the `VaultManager` facade
  against a real temp vault, including the exact live-transcript case
  ("this one is from the People directory"). Full suite: 839 passed.
- A `code-review` pass on this change caught a real regression before it
  shipped: the input-side check had been implemented as an *unscoped* call
  on `clean_input` itself (any message, not just a continuation), which is
  precisely the false positive this ADR's own "Alternatives rejected"
  section says to avoid (a note titled "Coffee" turning "Coffee is great
  this morning" into a spurious vault fetch). Removed; the input-side
  check now only runs where the ADR always intended — a real referent on
  the *prior assistant turn* when the current turn is an affirmed
  continuation. Locked in by
  `TestResolveStrictGroundingSubject` in `tests/unit/test_engine.py`. The
  same pass also flagged that `VaultManager.real_vault_referents` rebuilt
  its frozenset from scratch on every call (up to 2-3x per turn); it now
  carries its own mtime-keyed cache, the same pattern `_get_vault_snapshot`
  already uses.
- ADR-124.1 (deterministic fetch for recognized structural flows) remains
  a standing rule rather than a code change — the 2026-09-17 ritual fix
  already implements it for the one flow that needed it; no other flow in
  the codebase currently qualifies.

### Complexity remediation (same day, follow-up)

This ADR's own diff pushed `chat_stream` from an already-flagged 39 to 42
on the project's `ruff` mccabe-complexity rule (max 10, per ADR-121) - per
damiro's request, that was resolved immediately rather than deferred:

- `chat_stream` ([engine.py](../../../sympose/engine.py)) is now a thin,
  fully-compliant orchestrator. Its former body split into
  `_maybe_persist_remembered_fact`, `_resolve_turn_vault_context`,
  `_build_turn_system_prompt`, `_call_and_stream_model`,
  `_resolve_strict_grounding_subject`, `_apply_grounding_and_stream_result`,
  `_finalize_reply_text`, `_synthesize_sub_agent_reply`,
  `_emit_badges_and_synthesis`, and `_persist_turn` - each independently
  named, each under the complexity limit, each callable (and now testable)
  on its own. `_call_and_stream_model`, `_apply_grounding_and_stream_result`
  and `_emit_badges_and_synthesis` remain generators (delegated via
  `yield from`) since they still need to stream pieces to the caller
  mid-computation; the rest are plain methods.
- damiro additionally asked for the six other pre-existing `vault.py`
  complexity violations to be resolved in the same pass, prioritizing the
  largest: `resolve_turn_context` (35 → fully resolved, split into its
  numbered cases 1b-8 as individual `_resolve_*_case` methods sharing one
  `_recall_prep` helper), `resolve_note_target` (16), `find_chronological_notes`
  (14), `get_discovered_folders` (14), `get_random_sample_notes` (13),
  `resolve_asset_path` (12), and `read_note` (11) - each split the same
  way, by its own already-numbered/tiered cases. `get_folder_digest` and
  `get_random_sample_notes` shared one exact duplicate folder-resolution
  block; consolidated into `_resolve_named_folder_dir` as a byproduct.
  Two dead imports (`pytest`, `MagicMock`) in `tests/unit/test_vault.py`
  were also removed.
- A second `code-review` pass on this remediation caught two doc-only
  issues in this ADR's own text (this section's neighbors): the header
  said "Accepted, implemented" while the Decision section still read
  "Proposed, not yet implemented," and ADR-124.2's own description still
  described the (already-removed) unscoped input check. Both corrected in
  place.
- **Flagged, not actioned:** the same review pass noted that `engine.py`
  (now ~1250 lines) and `vault.py` (now ~1830 lines) both already
  exceeded, and this remediation further grew past, the project's own
  `.agents/rules/execution_guidelines.md` guidance of keeping modules
  under ~200 LOC. Splitting either file into multiple modules (e.g. a
  dedicated turn-pipeline module, splitting `resolve_turn_context`'s cases
  and `read_note`/`resolve_asset_path`'s tiers into their own file the way
  `vault_recall.py`/`vault_grounding.py` already do for other logic) is a
  materially larger, separate architectural task and was not undertaken
  here without confirming scope first.
- Full suite after this remediation: 841 passed;
  `ruff check sympose/engine.py sympose/vault.py sympose/vault_grounding.py`
  reports zero errors.
