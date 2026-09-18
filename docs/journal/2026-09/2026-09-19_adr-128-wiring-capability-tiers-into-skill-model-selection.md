---
title: "ADR-128 — Wiring Capability Tiers Into Skill-Driven Model Selection"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-128 — Wiring Capability Tiers Into Skill-Driven Model Selection

- **Status:** Implemented — scoped down from the original plan after
  reading the second intended call site directly (see Context).
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

ADR-127 shipped the capability-tier resolver (`model_capability.py`) as a
dormant primitive with no consumer. This ADR wires it into one real call
site: `sub_agents.py:_resolve_target_model`, the function that already
picks a sub-agent's model from a skill's `recommended_models` list.

The original plan (from the founder-approved implementation plan this ADR
sequence is executing) also called for extending
`engine_grounding.py`'s `_grounding_mode` — described there as "the
existing local/cloud binary… threading `[model, local_model]` candidates
through the same resolver instead of the current binary `is_local_backend`
check." Reading `_grounding_mode` directly before touching it showed that
description doesn't hold: the function takes one already-selected
`target_model` and classifies it into an enforcement mode (`strict` = the
runtime forces vault retrieval itself; `trust` = rely on the model to
autonomously emit `[SPAWN_SUB_AGENT: vault_read]`) — it never chooses
*between* candidate models at all. There is no `[model, local_model]` list
being resolved there; `is_local_backend(target_model, …)` is answering "is
the model I already have local," not "which model should I use." Wiring
`resolve_capable` into it would mean inventing a candidate list this
function has no natural use for, just to force a fit. Recorded here
plainly rather than forced through, per this project's own standard of
noting when a plan's premise doesn't survive contact with the real code
(the same thing ADR-126 did for its file-grouping estimate).

## Decision

- **`sympose/skills.py`**: `Skill.__init__` gains an optional
  `minimum_capability_tier: str | None = None` parameter, stored as-is and
  included in `to_dict()`. `_parse_skill_file` reads it from SKILL.md
  frontmatter (`metadata.get("minimum_capability_tier")`, stringified and
  stripped, `None` if absent/falsy). Every existing skill file has no such
  key, so every existing `Skill` object gets `minimum_capability_tier =
  None` — zero behavior change for anything already shipped.
- **`sympose/sub_agents.py:_resolve_target_model`**: extended from "task
  override → first skill's `recommended_models[0]` → env default" to:
  collect *every* skill's `recommended_models` into one candidate list,
  and track the last non-empty `minimum_capability_tier` declared among
  the task's skills. If no skill declares a floor, behavior is
  byte-for-byte identical to before (first candidate wins). If one does,
  the candidate list (plus `DEFAULT_SUB_AGENT_MODEL` appended as a final
  fallback) is passed through `model_capability.resolve_capable` with the
  declared floor, using `config_manager.get("models.capability_tier_order"
  /"models.capability_tiers")` fetched at the call site (keeping
  `model_capability.py` itself config-agnostic, per ADR-127).
- **`engine_grounding.py` is untouched** — see Context. `_select_turn_model`
  (Samantha's default hot path) remains untouched as originally planned.
- 4 new unit tests in `tests/unit/test_sub_agents.py`
  (`TestResolveTargetModelCapabilityTier`): task-override precedence, the
  no-skills-recommend-anything fallback, the unchanged
  no-tier-declared-takes-first-recommendation path, and the actual
  capability-filtered resolution picking a model that clears the bar over
  one that doesn't.

## Consequences

**Positive**

- The one genuine "pick among candidate models" call site this codebase
  has for skill-driven work now honors a capability floor when a skill
  asks for one, with zero effect on any skill that doesn't (all of them,
  today — the first real consumer is `wiki_ingest`, ADR-132).
- Caught and corrected a plan inaccuracy before writing code against it,
  rather than after — cheaper to fix a paragraph in a not-yet-implemented
  ADR than to un-wire a bad integration later.

**Negative / costs**

- The founder-approved plan named `engine_grounding.py` as a second
  wiring site; that scope is now explicitly not delivered, for the reason
  stated in Context. If capability-tier-aware grounding-mode selection is
  still wanted, it needs its own design — most likely at
  `engine.py:_select_turn_model` itself, deciding between `model` and
  `local_model` as actual candidates, which is a materially bigger and
  more sensitive change (Samantha's default hot path) than this ADR's
  scope, not a thin extension of `_grounding_mode`.

## Alternatives rejected

- **Force `resolve_capable` into `_grounding_mode` by treating `[model,
  api_base-derived local_model]` as a synthetic candidate pair.**
  Rejected — `_grounding_mode` only ever has one real model in hand at
  that point in the call chain; manufacturing a second "candidate" that
  was never actually selectable there would be decorative, not a real
  routing decision, and would misrepresent what the function does to
  future readers.
- **Make `minimum_capability_tier` a first-recommendation-only filter
  (skip the skill entirely if its top recommendation doesn't clear the
  bar) instead of pooling all skills' recommendations.** Rejected —
  pooling and letting `resolve_capable` pick the first clearing candidate
  across all of a task's skills is strictly more useful when a task
  combines multiple skills with different recommended models, and costs
  nothing extra when a task has just one skill (the common case).
