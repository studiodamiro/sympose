"""What a cloud model may receive (docs/decisions/031). Everything derived from the user's vault
is a category, and `cloud_share` in the settings file lists the categories the user has approved
for models that are not local; it is empty until they do. A local model gets everything, since
nothing leaves the machine. The user's own messages and the conversation so far are not a
category (they go to the model the user chose), and neither is the Sympose reference library
(shipped documentation, not the user's data).

The turn calls `gate` once, before the prompt is built, so the prompt, the token count and the
session record all see the same set; recap writing and the embedder ask `allowed` themselves."""

from dataclasses import dataclass
from typing import Any

from sympose import settings_store
from sympose.engine import budget

SETTING = "cloud_share"
NOTES, PROPERTIES, RECAPS = "notes", "properties", "recaps"
CATEGORIES = (NOTES, PROPERTIES, RECAPS)
# What a grounded passage of the user's own notes is, by its `kind` (a note's properties are a
# passage of their own, docs/decisions/030); anything else that is a vault passage is note text.
_PROPERTIES_KIND = "properties"
# What each category is, in the words a user is asked about it (the CLI's `/share`, later the web app).
DESCRIPTIONS = {
    NOTES: "passages of your notes found for a message",
    PROPERTIES: "the properties of your notes (frontmatter: emails, phone numbers, links)",
    RECAPS: "recaps of your earlier conversations",
}
_REFERENCE_SOURCE = "sympose"


@dataclass(frozen=True)
class Gated:
    grounding: list[dict[str, Any]]
    recaps: list[dict[str, Any]]
    # The categories something was held back from, with how many passages or recaps.
    withheld: dict[str, int]


def is_local(model: str) -> bool:
    return budget.is_ollama(model)


def approved() -> frozenset[str]:
    """The categories the user has approved for cloud models. Only known names in a list count, so a
    hand-edited setting of the wrong shape shares nothing: it fails closed, never open."""
    value = settings_store.get(SETTING)
    if not isinstance(value, list):
        return frozenset()
    return frozenset(name for name in value if name in CATEGORIES)


def allowed(model: str) -> frozenset[str]:
    """The categories `model` may receive: all of them for a local model, the approved ones otherwise."""
    return frozenset(CATEGORIES) if is_local(model) else approved()


def category_of(hit: dict[str, Any]) -> str | None:
    """The category a grounded passage belongs to, or `None` for one that is not the user's data."""
    if hit.get("source") == _REFERENCE_SOURCE:
        return None
    return PROPERTIES if hit.get("kind") == _PROPERTIES_KIND else NOTES


def gate(model: str, grounding: list[dict[str, Any]], recaps: list[dict[str, Any]]) -> Gated:
    """`grounding` and `recaps` as `model` may receive them, and what was held back."""
    ok = allowed(model)
    withheld: dict[str, int] = {}

    def keep(category: str | None) -> bool:
        if category is None or category in ok:
            return True
        withheld[category] = withheld.get(category, 0) + 1
        return False

    kept = [hit for hit in grounding if keep(category_of(hit))]
    kept_recaps = [recap for recap in recaps if keep(RECAPS)]
    return Gated(kept, kept_recaps, withheld)


def embeds_notes(embedding_model: str) -> bool:
    """Whether the user's notes may be sent to `embedding_model`: always for a local one."""
    return NOTES in allowed(embedding_model)


def categories_of(grounding: list[dict[str, Any]], recaps: list[dict[str, Any]]) -> list[str]:
    """The categories that `grounding` and `recaps` carry, in the order of `CATEGORIES` (what a turn
    actually sent, for the reply header and the session record)."""
    present = {category_of(hit) for hit in grounding} | ({RECAPS} if recaps else set())
    return [name for name in CATEGORIES if name in present]


def set_approved(category: str, on: bool) -> bool:
    """Approve (`on`) or stop approving `category` for cloud models and save it; `False` when the
    settings file could not be written. Only known names are kept, in the order of `CATEGORIES`."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category!r}")
    chosen = (approved() - {category}) | ({category} if on else set())
    return settings_store.set(SETTING, [name for name in CATEGORIES if name in chosen])
