---
title: "ADR-127 — Capability-Tier Model Routing Axis"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-127 — Capability-Tier Model Routing Axis

- **Status:** Implemented — dormant primitive, consumed by nothing yet
  (wiring it into an actual routing decision is ADR-128).
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Comparing Sympose against other Obsidian+AI patterns (Tina Huang's "AI
second brain / AI database / LLM wiki" tiers; Andrej Karpathy's LLM Wiki
pattern) surfaced a real gap in Sympose's founding round-trip-frugality
stance: it excludes users who value reliability/capability over token
cost. damiro decided frugality should become a tunable spectrum rather
than an absolute constraint, with one explicit correction to how that
spectrum should work: **it is not "local = cheap/dumb vs. cloud =
reliable/smart."** His words: "local model use can be used too with
higher more capable models I think. we just need to find our minimum and
design from there." A sufficiently capable local model should be able to
satisfy a reliability requirement, and a weak or misconfigured cloud model
should not get a free pass just for being cloud-hosted. The existing
ADR-122 axis (`is_local_backend`, `is_simple_message`/`resolve_turn_model`)
is exactly a local-vs-cloud binary and is the right mechanism for its own
job (routing genuinely trivial messages to a cheap local model on
Samantha's default hot path) — but it is the wrong mechanism to extend for
"does this model clear a capability floor for this operation," and
conflating the two would reintroduce the local=dumb assumption damiro
explicitly rejected.

He was equally explicit that the reliability path must still be the
**least expensive design that clears the bar**, not "spend more for
reliability": "the design should be the least cost possible for it to be
conversational and grounded and reliable."

## Decision

A new, deliberately separate config axis and a small pure-function module,
consumed by nothing yet — this ADR ships the mechanism only, mirroring how
ADR-122 itself first shipped as a dormant primitive before being wired
into `engine.py`.

- **`sympose/config_settings_models.py`** (40 lines), a new `Model
  Capability Tiers` section (`_MODELS`), inserted into `config_schema.py`'s
  `SECTIONS` between `Sub-Agent Sandbox` and `Persona`:
  - `models.capability_tier_order` (`list`, default `["basic", "standard",
    "high"]`) — an ordered, least-to-most-capable name list. Position in
    the list is what's compared; the label text is cosmetic.
  - `models.capability_tiers` (`dict`, default `{}`) — an explicit
    model-id → tier-name registry, edited directly in `config.yaml` (same
    `dict`-typed, not-`/config set`-able pattern as
    `performance.local_model_keep_alive`). A model with no entry defaults
    to the lowest tier — conservative by default, the same bias ADR-122's
    `is_simple_message` already uses.
- **`sympose/model_capability.py`** (71 lines) — four pure functions,
  taking `tier_order`/`tiers` as explicit parameters rather than reading
  `config_manager` internally, mirroring `model_router.py`'s own
  config-agnostic, directly-testable style:
  - `tier_index(tier_order, name)` — position lookup, unknown/`None` → 0.
  - `tier_of(tier_order, tiers, model_id)` — a model's declared tier,
    defaulting to the lowest.
  - `clears(tier_order, tiers, model_id, minimum)` — `True` if the model's
    tier is at or above `minimum`; `minimum=None` always clears.
  - `resolve_capable(tier_order, tiers, candidates, minimum)` — the actual
    decision: **first candidate, in the given order, that clears the
    bar** — deliberately cost-first ("cheapest model that's good enough,"
    not "most capable model available"), matching damiro's least-cost
    instruction directly. Fails open to the highest-tier candidate
    available if none clears the bar, rather than blocking the turn — the
    same philosophy as `model_router.resolve_turn_model`'s cold-model
    handling.
- An explicit registry, not name-sniffing heuristics (e.g. inferring
  "ollama = weak, gemini = strong" from the model-id string). A registry
  is the only way a capable local model and a weak cloud model both get
  judged correctly — a heuristic would silently reintroduce the exact
  assumption this ADR exists to remove.
- 15 new unit tests (`tests/unit/test_model_capability.py`), covering tier
  lookup defaults, an unassigned model of either kind failing a real
  floor (proving no local/cloud bias leaked in), cost-ordered resolution,
  and the fail-open path.

## Consequences

**Positive**

- Nothing currently calls `model_capability.resolve_capable` — Samantha's
  default frugal turn path (`engine.py:_select_turn_model`) is
  byte-for-byte unaffected, satisfying the "must not make the default
  path slower" constraint by construction rather than by care.
- The axis is genuinely orthogonal to ADR-122: a persona/skill that never
  declares a `minimum_capability_tier` (every existing one, until ADR-128
  wires a consumer) never touches this code at all.
- Pure-function design means the whole module is unit-tested without
  mocking `config_manager`, same as `model_router.py`.

**Negative / costs**

- A "dormant primitive with no consumer" is inherently unverified against
  a real call site until ADR-128 lands — the tests prove the functions do
  what they claim in isolation, not that the eventual wiring is correct.
  Accepted deliberately: shipping the mechanism and its wiring as two
  separate, independently-reviewable ADRs is lower-risk than one larger
  change touching both a new module and existing routing call sites at
  once.
- One more config section for `/config` to display, and one more explicit
  registry (`models.capability_tiers`) a user must populate for the axis
  to do anything beyond defaulting every model to the lowest tier — this
  is the accepted cost of avoiding heuristic guessing.

## Alternatives rejected

- **Deriving tiers automatically from model name/provider (e.g. "ollama/*
  = basic, anything else = standard").** Rejected — this is exactly the
  "local = cheap/dumb, cloud = smart" assumption damiro explicitly
  corrected; a heuristic can never let a genuinely capable local model
  (his own example: a 30B+ local model) clear a high bar, nor let an
  underpowered or misconfigured cloud model fail one.
- **Extending ADR-122's `is_local_backend`/`is_simple_message` axis
  in-place instead of adding a new one.** Rejected — that axis's entire
  design is a local-vs-cloud binary; bolting a capability concept onto it
  would conflate two independent questions ("is this the SIMPLE-tier
  hot path" vs. "does this model clear a capability floor") in one
  function, and risk regressing Samantha's already-shipped, already-tuned
  default routing path in the process.
- **A numeric capability score instead of named ordered tiers.** Rejected
  for this stage — adds precision nobody has asked for yet and
  complicates the authoring UX for the skill-frontmatter consumer ADR-128
  introduces (`minimum_capability_tier: standard` reads far more plainly
  in a SKILL.md file than a numeric threshold would). Revisitable later
  without disturbing callers, since `resolve_capable` only ever compares
  `tier_order` positions.
