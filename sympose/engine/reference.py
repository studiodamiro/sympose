"""The Sympose reference library in a persona's turns (docs/decisions/022): the
notes about Sympose itself that ship in the package (`sympose/reference/`,
docs/decisions/019), searched with the strict retriever for the personas that
have them. Read-only, and never the user's vault."""

import logging
import os
from typing import Any

from sympose.engine import semantic
from sympose.engine.grounding import retrieve
from sympose.engine.grounding_index import Index, build_index
from sympose.vault_snapshot import get_vault_snapshot

log = logging.getLogger(__name__)

REFERENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reference")
SOURCE = "sympose"  # the `source` of a hit, so the prompt can tell it from a vault note
LABEL = "Sympose reference"  # the path prefix the reply header shows
MAX_PASSAGES = 3

# `(snapshot list object, its Index)`: the snapshot is mtime-cached and returns the
# very same list until a note changes, so an identity check is enough.
_CACHE: tuple[list[dict[str, Any]], Index] | None = None


def _index() -> Index | None:
    global _CACHE
    if not os.path.isdir(REFERENCE_DIR):
        return None
    snapshot = get_vault_snapshot(REFERENCE_DIR, [REFERENCE_DIR])
    if _CACHE is None or _CACHE[0] is not snapshot:
        _CACHE = (snapshot, build_index(snapshot))
    return _CACHE[1]


def library_index(persona: dict[str, Any]) -> Index | None:
    """The library's search index for a persona that has the library, else `None`."""
    return _index() if persona.get("sympose_reference") else None


def ground(persona: dict[str, Any], message: str) -> list[dict[str, Any]]:
    """Passages of the reference library for `message`, best first, or `[]`:
    for a persona without the library, when nothing qualifies, or when the notes
    are missing from this install (a packaging fault must not fail a turn)."""
    if not persona.get("sympose_reference"):
        return []
    index = _index()
    if index is None:
        log.warning("The Sympose reference notes are missing from this install: %s", REFERENCE_DIR)
        return []
    hits = retrieve(index, message, MAX_PASSAGES, strict=True)
    hits = semantic.refine(index, message, hits, library=True, max_results=MAX_PASSAGES)  # docs/decisions/027
    return [{**hit, "rel_path": f"{LABEL}/{hit['rel_path']}", "source": SOURCE} for hit in hits]
