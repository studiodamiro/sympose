---
title: "ADR-135 — Opt-In Capability-Tier Routing for the Main Persona Turn"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-135 — Opt-In Capability-Tier Routing for the Main Persona Turn

- **Status:** Implemented.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

ADR-127/128 shipped capability-tier routing, but its only consumer was
`sub_agents.py:_resolve_target_model` — sub-agent tasks and skill-declared
floors. Samantha's actual main conversation turn (`engine.py:
_select_turn_model`) was explicitly left untouched in both of those ADRs,
on the reasoning that it's the default, most-used, most latency-sensitive
path and shouldn't be risked while landing a new mechanism. Once that
mechanism was proven out (127/128 shipped, tested, in production use
across 130's action-event work too), damiro asked for the natural
follow-on: let a persona opt *its own* main turn into capability-tier
routing too, so "frugality is tunable" applies to the everyday chat path,
not just sub-agent delegation.

## Decision

- **`sympose/config_settings_persona.py`**: new persona-scoped
  `capability_min_tier` (str, default `""`). Empty is the off-switch, the
  same pattern `local_model` itself already uses ("empty = routing
  disabled"). A non-empty value (e.g. `"standard"`) is the floor this
  persona's local model must clear on *every* message, not just
  short/simple ones.
- **`sympose/model_router.py`**: `resolve_turn_model`'s warm-check/
  fail-open tail (checking Ollama's `/api/ps`, firing a background
  warm-up if cold) was extracted into a shared `_resolve_if_warm` helper.
  `resolve_turn_model` itself is byte-for-byte unchanged — same gate,
  same behavior, same signature. A new `resolve_turn_model_by_capability`
  function reuses that tail but replaces the `is_simple_message` gate with
  a direct `model_capability.clears(tier_order, tiers, local_model,
  minimum)` check.
- **`sympose/engine.py`**: `_select_turn_model` reads the persona's
  `capability_min_tier`; if set, calls `resolve_turn_model_by_capability`
  instead of `resolve_turn_model`. The existing exclusions (no
  `local_model` configured, an active `/model` override, vault content
  already resolved or clearly wanted) are unchanged and still apply
  *before* either path is reached — this only replaces which of the two
  gating strategies decides the remaining cases. Empty `capability_min_tier`
  (every persona today) reaches the exact same `resolve_turn_model` call
  as before this ADR.
- **A bug my own tests caught before it shipped**: the first draft had
  `resolve_turn_model_by_capability` call `model_capability.resolve_capable`
  (the same function ADR-128 uses) rather than checking `clears` directly.
  `resolve_capable`'s fail-open behavior — pick the highest-tier candidate
  when none clears the bar — is correct for a sub-agent task (which always
  needs *some* model to run) but wrong here: when neither `local_model` nor
  `base_model` has an assigned tier, both default to the lowest tier and
  tie; `resolve_capable`'s tie-break picks whichever candidate is listed
  first, which was `local_model` — silently routing every message locally
  the moment a user turned this knob on without populating
  `models.capability_tiers`, the exact opposite of ADR-122's "any doubt
  routes to cloud" philosophy this ADR is extending. Fixed to check
  `clears` directly: there's always an unambiguous safe fallback here
  (`base_model`), so there was never anything to fail open *to*.
  `test_local_model_below_the_bar_stays_on_base_even_for_a_complex_message`
  pins this down.
- 12 new tests: 5 for `resolve_turn_model_by_capability` (no local model,
  clears-and-warm, below-bar-stays-on-base, clears-but-cold-warms-and-falls-
  back, and a signature check confirming the function takes no `message`
  parameter at all — content-independence isn't just untested, it's
  structurally impossible to violate by accident), 3 for `_select_turn_model`'s
  new branch (empty knob unchanged, set knob calls the capability path with
  the right config values, the override/vault-ctx exclusions still apply
  first).

## Consequences

**Positive**
- Every persona today has `capability_min_tier` unset, so this is
  byte-for-byte inert until a user opts in — confirmed by
  `test_empty_capability_min_tier_calls_the_simple_message_path` and the
  full suite staying green (1129 passed, 0 regressions).
- A user who populates `models.capability_tiers` with real assessments of
  their own models now has a lever over the *entire* conversation, not
  just delegated sub-agent work — the actual ask behind "frugality is
  tunable."
- Caught a real correctness bug (the fail-open tie-break) before it could
  ship as a silent, undocumented behavior surprise.

**Negative / costs**
- `engine.py` grew by ~15 lines (already over the 200-LOC guidance,
  pre-existing debt this ADR didn't set out to fix — thin wiring only, per
  the established strategy for already-oversized files).
- A user who enables this without ever touching `models.capability_tiers`
  gets no benefit and no harm (everything stays on `base_model`, since an
  unassigned local model never clears any real floor) — the knob is
  inert until deliberately configured, which is the safe failure mode but
  also means it does nothing by default, unlike ADR-122's `local_model`
  which works immediately with zero extra config. Acceptable: this knob is
  explicitly for users willing to make an informed capability assessment,
  not a drop-in replacement for the simpler default.

## Alternatives rejected

- **Layering capability-tier as an *additional* filter on top of the
  existing SIMPLE-message gate**, rather than replacing it. Rejected —
  this is what damiro actually asked for ("make _select_turn_model also
  run model, local_model through model_capability.resolve_capable instead
  of just the ADR-122 SIMPLE-message check"): a user who opts in wants
  every message judged by their own declared capability assessment, not
  just simple ones filtered further. Layering would silently limit the
  feature to a subset of messages the user didn't ask to restrict it to.
- **`resolve_capable`'s fail-open path for the "neither clears" case.**
  Rejected — see Decision; there's always a safe fallback (`base_model`)
  here, unlike the sub-agent case `resolve_capable` was designed for.
- **A separate boolean `capability_tier_routing` knob alongside a
  `min_tier` value.** Rejected in favor of one string setting whose
  emptiness is the off-switch — matches `local_model`'s own existing
  pattern exactly, and avoids a combination where the boolean is on but
  the tier is unset (or vice versa) meaning something ambiguous.
