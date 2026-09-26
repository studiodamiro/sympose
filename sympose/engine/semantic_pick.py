"""Which passages a message's similarity scores attach (docs/decisions/027): the best notes at or over
the threshold and within a margin of the best, or, when none reaches it, one note that clearly leads."""

from typing import Any

from sympose.engine.grounding_index import PASSAGES_PER_NOTE, Passage

# With no note over the threshold, the best is still attached if within `_STAND_OUT_BELOW` of it and
# `_STAND_OUT_GAP` ahead of the next ("can you search my vault for X?": filler words pull X just under).
_STAND_OUT_BELOW = 0.04
_STAND_OUT_GAP = 0.06


def hit(passage: Passage, similarity: float, via: str) -> dict[str, Any]:
    """A hit shaped like a keyword hit. Meaning is strong evidence, so `matched` is 2: it does not
    ask the follow-up rewrite to check it (docs/decisions/021)."""
    return {
        "rel_path": passage.rel_path,
        "title": passage.title,
        "heading": passage.heading,
        "text": passage.text,
        "tags": list(passage.tags),
        "kind": passage.kind,
        "score": round(similarity, 3),
        "matched": 2,
        "via": via,
    }


def by_meaning(
    passages: list[Passage], sims: list[float], threshold: float, margin: float, notes: int, via: str = "embedding"
) -> list[dict[str, Any]]:
    """The passages of the `notes` closest notes whose best passage reaches `threshold` and is within
    the margin of the best note's, best first."""
    per_note: dict[str, list[tuple[float, int]]] = {}
    for i, sim in enumerate(sims):
        if sim >= threshold:
            per_note.setdefault(passages[i].rel_path, []).append((sim, i))
    ranked = sorted(per_note.values(), key=lambda found: -max(found)[0])
    if ranked:
        floor = max(ranked[0])[0] - margin
        ranked = [found for found in ranked if max(found)[0] >= floor]
    ranked = ranked[:notes]
    return [
        hit(passages[i], sim, via)
        for found in ranked
        for sim, i in sorted(found, reverse=True)[:PASSAGES_PER_NOTE]
    ]


def clear_winner(
    passages: list[Passage], sims: list[float], threshold: float, margin: float, notes: int, via: str = "embedding"
) -> list[dict[str, Any]]:
    """The one note that is nearly at the threshold and clearly ahead of every other, else nothing."""
    best: dict[str, float] = {}
    for passage, sim in zip(passages, sims):
        best[passage.rel_path] = max(sim, best.get(passage.rel_path, 0.0))
    ranked = sorted(best.values(), reverse=True)
    if len(ranked) < 2 or ranked[0] < threshold - _STAND_OUT_BELOW or ranked[0] - ranked[1] < _STAND_OUT_GAP:
        return []
    return by_meaning(passages, sims, ranked[0], margin, notes, via)
