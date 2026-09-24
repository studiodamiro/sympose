"""Chat grounding (docs/decisions/014): find the passages of the persona's
notes that a message is about and hand them to the model as evidence.

A plain, deterministic keyword retriever, no model in the loop: the message's
terms are weighted by how rare they are across the vault (BM25-style), passages
are ranked, and only clearly relevant ones are returned; if nothing scores,
nothing is grounded. Replaces the earlier reuse of the search bar's matcher
(docs/decisions/002, 006), which matched raw substrings and returned one
70-character line per note. The search bar still uses that matcher."""

import math
from typing import Any

from sympose import vault_paths
from sympose.engine.grounding_index import Index, Passage, build_index, index_terms
from sympose.vault_snapshot import get_vault_snapshot

_K1, _B = 1.2, 0.75  # standard BM25 constants
# A term in more than this share of notes says nothing about which note is
# meant, so it is ignored — but only once the vault is big enough for a
# share to mean anything.
_MAX_NOTE_SHARE = 0.25
_MIN_NOTES_FOR_SHARE = 10
# Keep only passages scoring at least this fraction of the best one, so one
# strong hit is not diluted by a tail of weak ones.
_RELATIVE_CUTOFF = 0.4
_PASSAGES_PER_NOTE = 2

# `(snapshot list object, its Index)` per scope. The snapshot is already
# mtime-cached and returns the very same list until the vault changes, so an
# identity check is enough to know the index is still current.
_INDEX_CACHE: dict[tuple[str, ...], tuple[list[dict[str, Any]], Index]] = {}


def _index_for(mv: str, allowed_dirs: list[str]) -> Index:
    snapshot = get_vault_snapshot(mv, allowed_dirs)
    key = tuple(sorted(allowed_dirs))
    cached = _INDEX_CACHE.get(key)
    if cached is not None and cached[0] is snapshot:
        return cached[1]
    index = build_index(snapshot)
    _INDEX_CACHE[key] = (snapshot, index)
    return index


def _informative_terms(message: str, index: Index, strict: bool) -> list[str]:
    """The message's own informative terms: no filler, and no term nearly
    every note uses (which says nothing about which note is meant). A
    `strict` (single-topic) source keeps those, since there most notes share
    the subject's own words."""
    terms: list[str] = []
    for word in dict.fromkeys(index_terms(message)):
        df = index.note_df.get(word, 0)
        if not strict and index.note_count >= _MIN_NOTES_FOR_SHARE and df / index.note_count > _MAX_NOTE_SHARE:
            continue
        terms.append(word)
    return terms


def _qualifies(passage: Passage, matched: list[str], informative: list[str], strict: bool) -> bool:
    """Precision over recall: a wrong note derails a small model's reply
    (tested on the default model: it answered the irrelevant context instead
    of the question, and instructions to ignore it did not help), while no
    note only costs a normal reply. So a passage is grounded only on strong
    evidence: a match on its note's title, tags, or heading; or two distinct
    message words in it; or the message having just one informative word
    (so "who is Priya?" still finds Priya). One ordinary word matching one
    body sentence ("create", "called") is not enough.

    A `strict` source (small, written as questions and answers, so its
    headings are made of ordinary words) asks for more: two distinct message
    words in the passage's own text or heading (a title word does not count,
    every passage of the note carries it), or a message made only of the
    note's title words, which is asking for the note by name. Ordinary chat
    ("thanks, that helps!", "I'm getting started on my taxes") is a heading
    word or two away from a note."""
    if strict:
        own = [t for t in matched if t in passage.own_terms]
        return len(own) >= 2 or set(informative) <= passage.title_terms
    return (
        any(t in passage.topical for t in matched)
        or len(matched) >= 2
        or len(informative) == 1
    )


def _score(passage: Passage, terms: list[str], index: Index) -> float:
    norm = 1 - _B + _B * (passage.length / index.avg_length if index.avg_length else 1)
    total = 0.0
    for term in terms:
        tf = passage.tf.get(term, 0)
        if not tf:
            continue
        df = index.note_df[term]
        idf = math.log(1 + (index.note_count - df + 0.5) / (df + 0.5))
        total += idf * tf * (_K1 + 1) / (tf + _K1 * norm)
    return total


def retrieve(
    index: Index, message: str, max_results: int = 5, strict: bool = False
) -> list[dict[str, Any]]:
    """The best passages for `message`, best first, as hit dicts. Knows
    nothing about vaults or personas. `strict` is for a small source about one
    subject (docs/decisions/019): common words are kept, and a passage needs
    two of the message's words in its own text, or a message that is just the
    note's name."""
    informative = _informative_terms(message, index, strict)
    terms = [t for t in informative if index.note_df.get(t, 0) > 0]
    if not terms:
        return []
    scored = []
    for passage in index.passages:
        matched = [t for t in terms if t in passage.tf]
        if matched and _qualifies(passage, matched, informative, strict):
            scored.append((_score(passage, terms, index), passage))
    if not scored:
        return []
    scored.sort(key=lambda sp: -sp[0])
    floor = scored[0][0] * _RELATIVE_CUTOFF

    hits: list[dict[str, Any]] = []
    per_note: dict[str, int] = {}
    for score, passage in scored:
        if score < floor or len(hits) >= max_results:
            break
        if per_note.get(passage.rel_path, 0) >= _PASSAGES_PER_NOTE:
            continue
        per_note[passage.rel_path] = per_note.get(passage.rel_path, 0) + 1
        hits.append(
            {
                "rel_path": passage.rel_path,
                "title": passage.title,
                "heading": passage.heading,
                "text": passage.text,
                "tags": list(passage.tags),
                "score": round(score, 3),
                "index": len(hits) + 1,
            }
        )
    return hits


def ground(profile: dict[str, Any], user_message: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Passages from the notes `profile` may read that `user_message` is
    about; `[]` if no vault is configured or nothing is relevant."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return []
    mv, allowed_dirs = scope
    return retrieve(_index_for(mv, allowed_dirs), user_message, max_results)
