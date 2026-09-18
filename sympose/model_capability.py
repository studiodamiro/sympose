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
    `tier_order` if unassigned or assigned an unknown tier name."""
    assigned = tiers.get(model_id)
    if assigned in tier_order:
        return assigned
    return tier_order[0] if tier_order else "basic"


def clears(
    tier_order: list[str], tiers: dict[str, str], model_id: str, minimum: str | None
) -> bool:
    """True if `model_id`'s declared tier is at or above `minimum`.
    `minimum=None` always clears — no floor declared for this operation."""
    if not minimum:
        return True
    return tier_index(tier_order, tier_of(tier_order, tiers, model_id)) >= tier_index(
        tier_order, minimum
    )


def resolve_capable(
    tier_order: list[str],
    tiers: dict[str, str],
    candidates: list[str],
    minimum: str | None,
) -> str:
    """First candidate, in the given (cost-preferred) order, that clears
    `minimum`. Fails open to the highest-tier candidate available if none
    clears the bar, rather than blocking the turn — same philosophy as
    model_router.resolve_turn_model's cold-model handling. Raises
    ValueError only if `candidates` is empty, since that's a caller bug,
    not a runtime condition to fail open from."""
    if not candidates:
        raise ValueError("resolve_capable requires at least one candidate")
    if not minimum:
        return candidates[0]
    for model_id in candidates:
        if clears(tier_order, tiers, model_id, minimum):
            return model_id
    return max(
        candidates, key=lambda m: tier_index(tier_order, tier_of(tier_order, tiers, m))
    )
