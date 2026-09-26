"""Search by meaning (docs/decisions/027): a passage is attached when its vector is close to the
message's, instead of, or as well as, sharing a word with it. The knob `grounding_search` decides
(`keywords` never gets here past the first line of `refine`). Any trouble with the embedding model
returns the keyword hits it was given: the search never fails a turn."""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from sympose.engine import embedding_store as store
from sympose.engine import embeddings, semantic_refresh, sharing, similarity
from sympose.engine import semantic_pick as pick
from sympose.engine.grounding_index import Index, Passage

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

_WARNED: set[tuple[int, str]] = set()
_UNAVAILABLE_UNTIL: dict[str, float] = {}  # embedding model -> when to try it again
_QUERIES: dict[tuple[str, str], Any] = {}  # (model, message) -> its unit vector


@dataclass(frozen=True)
class _Vectors:
    passages: list[Passage]
    unit_vectors: similarity.VectorSet


# `(model, id(index))` -> (the index, its vectors); the index is held so its id is not reused.
_CACHE: dict[tuple[str, int], tuple[Index, _Vectors]] = {}
_CACHE_LOCK = threading.Lock()  # two personas can be answering at once


def _warn_once(reason: str, level: int | None = None) -> None:
    """Once per reason and level, so a note made in `auto` does not hide the warning the same fault
    deserves under `embeddings`. `level` defaults to how loudly a missing model is logged."""
    level = embeddings.unavailable_log_level() if level is None else level
    if (level, reason) not in _WARNED:
        _WARNED.add((level, reason))
        log.log(level, "Searching by keyword: meaning-based search is not available (%s)", reason)


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


def refine(
    index: Index, message: str, keyword_hits: list[dict[str, Any]], library: bool = False, max_results: int = 5
) -> list[dict[str, Any]]:
    """`keyword_hits` as the knob says: as they are (`keywords`), replaced by the passages closest
    in meaning (`embeddings`, and `auto`, which differs only in staying quiet when it cannot), or the
    keyword hits that agree in meaning plus the notes close in meaning that share no word (`hybrid`)."""
    mode = embeddings.mode()
    if library and mode == embeddings.AUTO:
        mode = embeddings.HYBRID  # the library's own words are strong evidence: meaning confirms them
    if mode == embeddings.KEYWORDS or not index.passages:
        return keyword_hits  # nothing to compare the message with: embedding it would only risk a timeout
    model = embeddings.model()  # once: the settings file may change while this runs
    if not sharing.embeds_notes(model):
        # A cloud embedder would receive the message, and every passage of the notes: the user has not
        # approved that (ADR 031). The library is public, but the message that searches it is not.
        _warn_once(f"'{model}' is a cloud model and the notes and messages may not be sent to it", logging.WARNING)
        return keyword_hits
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
        _warn_once("the stored vectors are from an embedding model of another size", logging.WARNING)
        return keyword_hits
    sims = vectors.unit_vectors.scores(query)
    threshold = embeddings.min_similarity() + (_LIBRARY if library else 0.0)
    margin = embeddings.margin()
    notes = max_results  # never more notes than passages the caller will take
    if mode in (embeddings.EMBEDDINGS, embeddings.AUTO):
        args = (vectors.passages, sims, threshold, margin, notes)
        hits = pick.by_meaning(*args) or pick.clear_winner(*args)
    else:
        best: dict[str, float] = {}
        for passage, sim in zip(vectors.passages, sims):
            best[passage.rel_path] = max(sim, best.get(passage.rel_path, 0.0))
        kept = [{**h, "via": "keyword"} for h in keyword_hits if best.get(h["rel_path"], 0.0) >= threshold + _KEEP]
        have = {(h["rel_path"], h["text"]) for h in kept}  # a passage, not a note: one note can hold many answers
        found = pick.by_meaning(vectors.passages, sims, threshold + _ADD, margin, notes)
        added = [h for h in found if (h["rel_path"], h["text"]) not in have]
        hits = kept + added
    return [{**h, "index": n} for n, h in enumerate(hits[:max_results], start=1)]


def _forget_for_tests() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
        _QUERIES.clear()
    _UNAVAILABLE_UNTIL.clear()
    _WARNED.clear()
