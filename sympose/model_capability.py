"""
Capability-Tier Model Resolution for Sympose (ADR-127).

Picks the cheapest candidate model that clears a declared minimum
capability tier for an operation, or fails open to the most-capable
candidate available rather than blocking a turn. Deliberately independent
of model_router.py's local-vs-cloud SIMPLE-tier routing (ADR-122): this
axis never asks whether a model is local, only whether it has been
declared capable enough — a capable local model can clear a high bar, and
a cloud model can be assigned a low one. Pure functions, no config reads
here (mirrors model_router.py's style) — callers fetch
`models.capability_tier_order`/`models.capability_tiers` from
`config_manager` and pass them in, keeping this module trivially testable.
"""


def tier_index(tier_order: list[str], name: str | None) -> int:
    """Position of `name` in `tier_order`; unknown or `None` -> 0 (the
    lowest tier) — conservative by default, same bias as ADR-122's
    is_simple_message."""
    if not name:
        return 0
    try:
        return tier_order.index(name)
    except ValueError:
        return 0


def tier_of(tier_order: list[str], tiers: dict[str, str], model_id: str) -> str:
    """A model's declared tier, defaulting to the lowest tier in
    `tier_order` if unassigned or assigned an unknown tier name. An empty
    `tier_order` has no lowest tier to name, so this returns `""` rather
    than guessing a schema-default tier name — `tier_index` already treats
    any unrecognized name (including `""`) as tier 0, so behavior is
    unchanged either way."""
    assigned = tiers.get(model_id)
    if assigned in tier_order:
        return assigned
    return tier_order[0] if tier_order else ""


def _minimum_index(tier_order: list[str], minimum: str, strict: bool) -> int:
    """Index for a *floor requirement* string (a persona's
    `capability_min_tier`, a skill's `minimum_capability_tier`) — the
    opposite fallback direction from `tier_index`. `tier_index` is used for
    a model's own *assigned* tier, where "unknown" should conservatively
    read as the lowest tier (ADR-122's bias). A floor requirement is the
    reverse: an unrecognized name (a typo, or a tier renamed out of
    `tier_order`) must never silently relax to "no requirement at all", so
    it conservatively reads as the *highest* declared tier instead —
    nothing clears it but the top tier. `strict=True` (the
    `models.strict_capability_tiers` knob) raises instead, for catching a
    misconfigured tier name during development rather than routing around
    it silently."""
    if minimum in tier_order:
        return tier_order.index(minimum)
    if strict:
        raise ValueError(f"Unknown capability tier requirement: {minimum!r}")
    return len(tier_order) - 1 if tier_order else 0


def strictest_tier(
    tier_order: list[str], a: str | None, b: str | None, *, strict: bool = False
) -> str | None:
    """The higher of two declared minimum tiers, either of which may be
    `None` (no floor declared). Lets a caller combining floors from several
    sources (e.g. every skill a sub-agent task carries) fold them one at a
    time without ad hoc last-write-wins logic. Raises ValueError if
    `strict=True` and either declared tier is unrecognized."""
    if not a:
        return b
    if not b:
        return a
    return (
        a
        if _minimum_index(tier_order, a, strict) >= _minimum_index(tier_order, b, strict)
        else b
    )


def clears(
    tier_order: list[str],
    tiers: dict[str, str],
    model_id: str,
    minimum: str | None,
    *,
    strict: bool = False,
) -> bool:
    """True if `model_id`'s declared tier is at or above `minimum`.
    `minimum=None` always clears — no floor declared for this operation.
    Raises ValueError if `strict=True` and `minimum` is unrecognized."""
    if not minimum:
        return True
    return tier_index(
        tier_order, tier_of(tier_order, tiers, model_id)
    ) >= _minimum_index(tier_order, minimum, strict)


def resolve_capable(
    tier_order: list[str],
    tiers: dict[str, str],
    candidates: list[str],
    minimum: str | None,
    *,
    strict: bool = False,
) -> str:
    """First candidate, in the given (cost-preferred) order, that clears
    `minimum`. Fails open to the highest-tier candidate available if none
    clears the bar, rather than blocking the turn — same philosophy as
    model_router.resolve_turn_model's cold-model handling. Raises
    ValueError if `candidates` is empty (a caller bug, not a runtime
    condition to fail open from), or if `strict=True` and `minimum` is
    unrecognized."""
    if not candidates:
        raise ValueError("resolve_capable requires at least one candidate")
    if not minimum:
        return candidates[0]
    for model_id in candidates:
        if clears(tier_order, tiers, model_id, minimum, strict=strict):
            return model_id
    return max(
        candidates, key=lambda m: tier_index(tier_order, tier_of(tier_order, tiers, m))
    )
