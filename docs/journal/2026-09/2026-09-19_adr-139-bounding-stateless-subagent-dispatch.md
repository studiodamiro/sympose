---
title: "ADR-139 — Bounding Stateless Sub-Agent Dispatch Under a Manually-Overridden Local Driver"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-139 — Bounding Stateless Sub-Agent Dispatch Under a Manually-Overridden Local Driver

- **Status:** Partially implemented. Item (1) is accepted and shipped
  (damiro resolved it directly, tracing it to an existing, simpler
  mechanism rather than the advisory caveat first proposed here — see
  Decision). Items (2) and (3) remain Proposed, pending discussion.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect) — pending; Grace (Engineering
  Partner) — proposing

## Context

See the same-day journal entry,
`2026-09-19_samantha-roulette-transcript-review.md` §3, for the full
investigation. Summary: a real session log
(`sessions/samantha_20260919_075559_58e20a.jsonl`) shows that once
Samantha's model was manually overridden to `ollama/gemma4:e4b`
(`/model ollama/gemma4:e4b`), she repeatedly emitted her own
`SPAWN_SUB_AGENT` tag for turns that needed no new vault retrieval at
all — a bare acknowledgment ("yeah.. lol"), a request to repeat a prior
answer ("whats that again?"), and a direct question about the behavior
itself ("why are you presenting me this again?"). Three consecutive turns
each triggered a fresh, fully stateless `vault_read` sub-agent
(`SubAgentTask` carries only `task_prompt` + skill/MCP list — no
conversation history, confirmed in `actions_sub_agent.py`'s
`_handle_spawn_sub_agent`), so none of them could recognize "nothing new
is being asked" and each one re-sampled or re-dumped `Thoughts/` instead
of answering conversationally. The last sub-agent in the sequence
described its own blindness verbatim ("I don't have the prior
conversation history to know why this was brought up previously"), and
Samantha's own next reply self-diagnosed the pattern as a loop.

This is precisely the failure category `commands.py`'s manual-override
warning already names: *"this persona's vault-recall/sub-agent grounding
guard normally avoids routing that work to a local model, but this
override skips it."* The existing structural grounding guards
(`_content_unread`, `_content_unsupported` in `sub_agents.py`) never even
engage here, because they check whether a *completed* synthesis is
backed by real retrieval — they have no opinion on whether a sub-agent
dispatch should have been *initiated* in the first place. Nothing in the
current design bounds that decision when the driving model is one known
to make it badly.

Round-trip frugality (this project's founding constraint) makes this
doubly costly: each of these unnecessary dispatches is a full extra
model round-trip that actively produces a *worse* answer than the driving
model just replying from context already in hand would have.

**The proximate cause, pinned down after this ADR's first draft.**
`skills/vault_read/SKILL.md`'s own "Ground rule" gives the driving model a
single blunt trigger: *"Answer not already in your pre-turn context →
emit `[SPAWN_SUB_AGENT: vault_read | <what to find>]` and stop."*
Deciding whether a given turn counts as "already in context" is left
entirely to the driving model's own judgment. That same file's frontmatter
declares `recommended_models: gemini/gemini-3.6-flash, ollama/qwen2.5:14b,
ollama/gemma2:9b` — models this skill's instructions were actually written
and tuned against. `ollama/gemma4:e4b` is not one of them.

Checked whether `recommended_models` is enforced anywhere: it isn't.
`sub_agents.py:247` only reads it to help pick which model *executes* a
sub-agent once the tag is already emitted (`_resolve_target_model`, the
same field the Tier 1 code-review fix touched). Nothing checks it against
the *driving* model before trusting that model's judgment to correctly
apply the "not in context → spawn" rule in the first place — and a manual
`/model` override sets the driving model directly, entirely outside that
mechanism. That's the actual gap: a model the skill was never validated
against was handed a rule that assumes good judgment, applied it too
literally to plain conversational turns, and — because each resulting
spawn is stateless — had no way to recover once it did.

## Decision

Three complementary, structural changes — none a phrase list, per this
project's standing preference for structural signals over enumerating
wording. (1) is the fix for the actual proximate cause; (2) and (3) bound
the damage on any turn where a bad dispatch decision still gets made
anyway — by this driver or a future one:

1. **Implemented, 2026-09-19.** An advisory system-prompt caveat
   (checking override-vs-`recommended_models` list membership) was the
   first draft here, but damiro traced this to a simpler, already-existing
   mechanism instead: ADR-127 already built a plain capability-tier ladder
   (`basic < standard < high`, a per-model registry, and a pure
   `model_capability.clears(tier_order, tiers, model_id, minimum)`
   boolean), and ADR-128/135 already wired it into sub-agent execution-model
   selection and Samantha's own opt-in main-turn routing — but both of
   those *explicitly exclude an active manual `/model` override* from the
   check ("the existing exclusions — no local model configured, an active
   `/model` override, vault content already resolved — are unchanged and
   still apply before either path is reached," per ADR-135's own Decision).
   The real gap was that exclusion, not a missing mechanism. Fix: a new
   `_capability_gap_warning(profile, new_model)` in `commands.py`, called
   from `_model_set` (the `/model <override>` handler), combines every
   loaded skill's declared `minimum_capability_tier` via the same
   `strictest_tier` helper the Tier-1 code-review fix already uses in
   `_resolve_target_model`, and calls `clears()` against the override —
   the exact ladder ADR-128/135 already trust, just no longer skipped for
   this one case. `skills/vault_read/SKILL.md` (both the live copy and
   `sympose/builtin_skills/vault_read/SKILL.md`, the shipped template) now
   declares `minimum_capability_tier: "standard"`, and `config.yaml` gained
   real tier assignments for the models actually in play (`gemini-3.6-flash`
   → `high`; the two recommended local models → `standard`) so the check
   has real data to compare against instead of every model defaulting to
   the same floor. `ollama/gemma4:e4b` has no entry, so it conservatively
   defaults to `basic` and correctly fails the check.

   **Verified**, not just unit-tested: `.venv/bin/pytest` (1188 passed, 0
   regressions, 3 new cases in `test_commands.py`), plus a real end-to-end
   run against Samantha's actual profile/skills/config.yaml (no mocking):
   `/model ollama/gemma4:e4b` now produces both the existing generic
   override banner *and* a new, specific one — *"Model `ollama/gemma4:e4b`
   is tier `basic`; a loaded skill needs at least `standard`..."*; `/model
   gemini/gemini-3.6-flash` (already registered at `high`) produces no
   capability warning; and — confirming the fix is properly local/cloud-
   agnostic, matching ADR-127's founding principle — `/model
   openrouter/some-totally-unknown-model` (a *cloud* model with no
   registry entry) gets flagged too, on the same conservative-default
   basis, not because it's local.

2. **Proposed, not yet implemented.** Give a spawned sub-agent minimal
   continuation context instead of none. `SubAgentTask` currently carries
   only `task_prompt` +
   skills/MCP. Thread through the single most relevant piece of session
   state it's missing — the last real vault item this session actually
   served (`PersonaEngine.active_vault_ctx`, which already exists and
   already tracks exactly this) — so a dispatched sub-agent that turns out
   to be unnecessary can recognize that itself ("this is the same note
   already discussed; nothing new to fetch") instead of blindly sampling
   again. This directly targets what turn 15's sub-agent already told us
   it was missing.

3. **Proposed, not yet implemented.** A structural repeat-guard on
   sub-agent dispatch itself, scoped to
   when the driving model is a manual local override: if the immediately
   preceding turn's badges already include a `vault_read` Sub-Agent Report
   against the *same folder* with no new resolvable subject in the current
   message, suppress spawning another one and instead surface a plain,
   honest line ("We already looked at `Thoughts/` — did you want a
   specific note, or something else?") rather than dispatching again. This
   is a mechanical count-and-compare check (badges + folder name), not a
   judgment call threaded through prompt wording — consistent with this
   project's structural-detection-first house style.

All three changes are scoped to the sub-agent dispatch path
(`actions_sub_agent.py`), the skill system-prompt assembly step (wherever
a loaded skill's block is composed into the turn's system prompt), and
session-state plumbing already in `PersonaEngine`; none adds a dependency
or a background process.

## Consequences

**Positive**
- (1) closes the actual gap directly, using a mechanism that already
  existed and was already trusted for two adjacent decisions (sub-agent
  execution-model choice, opted-in main-turn routing) — a manual override
  is no longer the one path through this codebase with zero capability
  awareness. Verified live against Samantha's real profile: flags
  `ollama/gemma4:e4b` and an unregistered cloud model alike, stays silent
  for a model that actually clears the floor.
- (2) directly closes the reproduced failure on a bad dispatch that still
  happens anyway: a sub-agent that already has "we just discussed this
  note" available to it can say so instead of re-dumping a folder.
- (3) caps the actual cost of a misbehaving driver: at most one wasted
  round-trip per topic instead of an unbounded loop.
- None of the three are model-specific — a capable cloud model that
  happens to be unlisted for some other skill, or that over-dispatches for
  an unrelated reason, gets the same protection, though the transcript
  evidence for the failure itself is specific to a weak, unlisted local
  override.

**Negative / costs**
- (1) is a warning shown once at override time, not a hard gate on
  behavior — it tells the user something concrete about the gap they've
  just opened, but doesn't stop the driving model from misbehaving during
  the session that follows. It also only covers skills that have actually
  declared a `minimum_capability_tier`, and today that's only
  `vault_read` — the same gap plausibly exists for `subagent_spawn`,
  `vault_write`, `wiki_ingest`, and `wiki_lint` (all of which also carry
  `recommended_models`), but declaring a real floor for each needs its own
  judgment call about what tier that skill actually needs, not a blanket
  copy — left for a follow-up rather than guessed here.
- `models.capability_tiers` needed real entries added for this to
  distinguish anything at all — until now it was empty, so *every* model
  defaulted to the same lowest tier and the check would have flagged
  Samantha's own default model too. Populated with the four models
  actually in play; a fifth model introduced later (a new persona, a new
  override) still needs its own entry or it inherits the conservative
  `basic` default, which is safe but not informative.
- `SubAgentTask`'s construction and `_handle_spawn_sub_agent` both need a
  new, threaded piece of state for (2) (the last-served vault item) — a
  small surface-area increase in a file that currently sits comfortably
  under the 200-LOC ceiling; needs a careful pass to keep it there.
- (3)'s repeat-guard needs a decision on what counts as "the same folder"
  when the user's own phrasing shifts (e.g. "Thoughts" vs "thoughts
  folder" vs no folder name at all) — a small, bounded normalization
  problem, not a phrase list, but still needs its own test coverage.
- None of the three fully removes the underlying fact that a weak,
  unvalidated model can still choose badly on the *first* dispatch of a
  topic — (1) makes that less likely, (2) and (3) bound what happens when
  it occurs anyway. A model too weak to be trusted with this judgment at
  all under any mitigation is still better served by the existing guard's
  default (don't route this work to it) than by any of these three.

## Alternatives rejected

- **Broaden `_resolve_strict_grounding_subject`'s `affirm` regex
  (`engine_turn_grounding.py:134`) to recognize more continuation
  phrasings** ("yeah.. lol", "why are you doing this again", etc.).
  Rejected — traced against the real log first: `has_sub_agent` was
  already `True` in every failing turn (the model spawned the tag itself),
  so this function never even ran; widening its regex would fix nothing
  here. It would also be exactly the enumerable-phrase-list pattern this
  project has rejected before for adjacent problems (see the 2026-09-17
  ritual-continuation entry's own §3).
- **Disable manual local-model overrides entirely for personas with
  `vault_folders` set**, closing the loophole outright rather than
  mitigating its effects. Rejected — the override exists because damiro
  wants it for cases where it behaves fine (plain chat, no vault-adjacent
  turns), and removing user control over their own persona's model choice
  is a bigger behavior change than the bug warrants. The existing warning
  banner already discloses the tradeoff at override time.
- **Do nothing beyond the existing warning banner**, treating this as
  "the user was warned, this is what override means." Rejected because
  the transcript shows the failure isn't a single bad answer the user can
  shrug off — it's a self-perpetuating loop that burns multiple round
  trips and never recovers on its own until the user manually resets the
  model, which directly contradicts round-trip frugality even for a
  feature the user opted into.
- **An advisory system-prompt caveat keyed to `recommended_models` list
  membership**, appended to a skill's own instructions when the driving
  model isn't on that list. This was Decision (1)'s first draft, written
  before checking whether `has_sub_agent` was already `True` in the
  failing turns (it was — see Context) and before checking whether a
  simpler mechanism already existed for this. Superseded once damiro
  pointed at ADR-127/128/135's existing tier ladder: reusing an
  already-built, already-tested boolean check (`clears()`) against a
  skill-declared floor is simpler and more precise than inventing new
  prompt-text machinery keyed off a different, purely-advisory list.
- **Hard-block the override outright** (refuse to set it, or force a
  fallback model) when it fails the tier check, rather than the warning
  banner actually shipped. Rejected as disproportionate: a persona's
  manual override is explicitly meant to let damiro try models a skill
  wasn't tuned for, including ones that might turn out fine — a capability
  tier is a coarse, self-reported floor, not a proof the model will
  actually fail. The banner tells the user something concrete and true;
  refusing the override on the same evidence would be a bigger behavior
  change than this ADR's evidence supports.
- **Route sub-agent *dispatch decisions* (not just sub-agent *execution*)
  through the full capability-tier system** (ADR-127/128/135), i.e.
  require a minimum capability tier — not just skill-specific
  `recommended_models` membership — before a driving model's own
  `SPAWN_SUB_AGENT` tag is honored at all. Considered but not proposed as
  the primary fix here: capability tiers currently gate which model
  *executes* a spawned task, not whether the *driving* model's decision to
  spawn is trusted — extending it to gate dispatch-authorship itself is a
  bigger, separate change with its own tradeoffs (would need a tier
  assigned to every driver model, including manual overrides, and a
  policy for what happens when a tag is authored but not honored). Worth a
  future ADR if the lighter, skill-scoped caveat in Decision (1) proves
  insufficient in practice; not folded into this one to keep its scope
  bounded to the reproduced failure.
