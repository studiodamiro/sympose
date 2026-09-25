"""Search by meaning (docs/decisions/027): a passage is attached when its vector is close to the
message's, instead of, or as well as, sharing a word with it. The knob `grounding_search` decides
(`keywords` is today's search and never gets here past the first line of `refine`). Any trouble with
the embedding model returns the keyword hits it was given: the search never fails a turn."""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from sympose.engine import embedding_store as store
from sympose.engine import embeddings, semantic_refresh, similarity
from sympose.engine.grounding_index import PASSAGES_PER_NOTE, Index, Passage

log = logging.getLogger(__name__)

# How the one threshold is used (all measured, docs/decisions/027): the library is a little looser
# than the user's notes; in `hybrid` a keyword hit must be within `_KEEP` of it, and a note found by
# meaning alone must be within `_ADD` of it.
_LIBRARY = -0.02
_KEEP = -0.06
_ADD = -0.02
# A note edited during the chat is embedded on the spot up to this many passages; more than that (a
# first index of a vault) is built in the background and the turn searches by keyword meanwhile. The
# Sympose library is shipped, about 110 passages, so on its first use (a second and a half, once, and
# only if the launch-time build has not finished) it is embedded on the spot.
_SYNC_LIMIT = 64
_LIBRARY_SYNC_LIMIT = 256
_KEEP_INDEXES = 4
# After the embedding model fails to answer, the turns search by keyword without trying it again for
# this long: a hung Ollama must not cost every message its timeout (twice: notes and library).
_COOLDOWN_SECONDS = 60.0
_QUERIES_KEPT = 4  # the vault and the library are searched for the same message: one embedding call

_WARNED: set[str] = set()
_UNAVAILABLE_UNTIL: dict[str, float] = {}  # embedding model -> when to try it again
_QUERIES: dict[tuple[str, str], Any] = {}  # (model, message) -> its unit vector


@dataclass(frozen=True)
class _Vectors:
    passages: list[Passage]
    unit_vectors: similarity.VectorSet


# `(model, id(index))` -> (the index, its vectors); the index is held so its id is not reused.
_CACHE: dict[tuple[str, int], tuple[Index, _Vectors]] = {}
_CACHE_LOCK = threading.Lock()  # two personas can be answering at once


def _warn_once(reason: str) -> None:
    if reason not in _WARNED:
        _WARNED.add(reason)
        log.warning("Searching by keyword: meaning-based search is not available (%s)", reason)


def _vectors_for(index: Index, sync_limit: int, model: str) -> _Vectors | None:
    """The vectors of every passage of `index`, or `None` while a background build is still running."""
    token = (model, id(index))
    with _CACHE_LOCK:
        cached = _CACHE.get(token)
    if cached is not None and cached[0] is index:
        return cached[1]
    if semantic_refresh.blocked(index, model):
        return None  # a build is running or failed: keywords now, without reading the cache to see what is missing
    texts, keys, have, missing = semantic_refresh.pending(index, model)
    if len(missing) > sync_limit:
        semantic_refresh.start_build(index, model=model)
        return None
    if missing:
        made = embeddings.embed([texts[i] for i in missing], "document", model)
        fresh = {keys[i]: v for i, v in zip(missing, made)}
        store.save(fresh)  # if it cannot be kept, they are still used from memory
        have.update(fresh)
    vectors = _Vectors(list(index.passages), similarity.VectorSet([embeddings.unit(have[k]) for k in keys]))
    with _CACHE_LOCK:
        while len(_CACHE) >= _KEEP_INDEXES:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[token] = (index, vectors)
    return vectors


def _query_vector(message: str, model: str) -> Any:
    """The unit vector of `message`, embedded once however many indexes it is searched in."""
    key = (model, message)
    with _CACHE_LOCK:
        found = _QUERIES.get(key)
    if found is not None:
        return found
    vector = embeddings.unit(embeddings.embed([message], "query", model)[0])
    with _CACHE_LOCK:
        while len(_QUERIES) >= _QUERIES_KEPT:
            _QUERIES.pop(next(iter(_QUERIES)))
        _QUERIES[key] = vector
    return vector


def _hit(passage: Passage, similarity: float, via: str) -> dict[str, Any]:
    """A hit shaped like a keyword hit. Meaning is strong evidence, so `matched` is 2: it does not
    ask the follow-up rewrite to check it (docs/decisions/021)."""
    return {
        "rel_path": passage.rel_path,
        "title": passage.title,
        "heading": passage.heading,
        "text": passage.text,
        "tags": list(passage.tags),
        "score": round(similarity, 3),
        "matched": 2,
        "via": via,
    }


def _by_meaning(
    vectors: _Vectors, sims: list[float], threshold: float, notes: int, via: str = "embedding"
) -> list[dict[str, Any]]:
    """The passages of the `notes` closest notes whose best passage reaches `threshold`, best first."""
    per_note: dict[str, list[tuple[float, int]]] = {}
    for i, sim in enumerate(sims):
        if sim >= threshold:
            per_note.setdefault(vectors.passages[i].rel_path, []).append((sim, i))
    ranked = sorted(per_note.values(), key=lambda found: -max(found)[0])[:notes]
    return [
        _hit(vectors.passages[i], sim, via)
        for found in ranked
        for sim, i in sorted(found, reverse=True)[:PASSAGES_PER_NOTE]
    ]


def refine(
    index: Index, message: str, keyword_hits: list[dict[str, Any]], library: bool = False, max_results: int = 5
) -> list[dict[str, Any]]:
    """`keyword_hits` as the knob says: as they are (`keywords`), replaced by the passages closest
    in meaning (`embeddings`), or the keyword hits that agree in meaning plus the notes close in
    meaning that share no word (`hybrid`)."""
    mode = embeddings.mode()
    if mode == embeddings.KEYWORDS:
        return keyword_hits
    model = embeddings.model()  # once: the settings file may change while this runs
    if time.monotonic() < _UNAVAILABLE_UNTIL.get(model, 0.0):
        return keyword_hits
    try:
        vectors = _vectors_for(index, _LIBRARY_SYNC_LIMIT if library else _SYNC_LIMIT, model)
        if vectors is None:
            return keyword_hits
        query = _query_vector(message, model)
    except embeddings.EmbeddingUnavailable as e:
        _UNAVAILABLE_UNTIL[model] = time.monotonic() + _COOLDOWN_SECONDS
        _warn_once(str(e))
        return keyword_hits
    if vectors.unit_vectors.dims and len(query) != vectors.unit_vectors.dims:
        _warn_once("the stored vectors are from an embedding model of another size")
        return keyword_hits
    sims = vectors.unit_vectors.scores(query)
    threshold = embeddings.min_similarity() + (_LIBRARY if library else 0.0)
    notes = max_results  # never more notes than passages the caller will take
    if mode == embeddings.EMBEDDINGS:
        hits = _by_meaning(vectors, sims, threshold, notes)
    else:
        best: dict[str, float] = {}
        for passage, sim in zip(vectors.passages, sims):
            best[passage.rel_path] = max(sim, best.get(passage.rel_path, 0.0))
        kept = [{**h, "via": "keyword"} for h in keyword_hits if best.get(h["rel_path"], 0.0) >= threshold + _KEEP]
        have = {h["rel_path"] for h in kept}
        added = [h for h in _by_meaning(vectors, sims, threshold + _ADD, notes) if h["rel_path"] not in have]
        hits = kept + added
    return [{**h, "index": n} for n, h in enumerate(hits[:max_results], start=1)]


def _forget_for_tests() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
        _QUERIES.clear()
    _UNAVAILABLE_UNTIL.clear()
    _WARNED.clear()
