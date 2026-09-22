"""Chat grounding — the same title/tag/content matcher `vault_search` uses
for the search bar, auto-triggered against a turn's user message instead of
a typed query (docs/decisions/002, docs/decisions/006).

`search_structured` matches by checking whether a whole query is a single
contiguous substring of a note's title/tag/body — a literal match, not a
token/keyword one. Fine for a short, note-name-like search-bar query, but
live-verified against a real vault and found wanting for chat: a
sentence-shaped question essentially never appears verbatim in a note, so
passing the raw message through unmodified surfaced zero grounding on real
phrasing (docs/decisions/006's Consequences). `search_structured` itself
stays untouched — this only tries more queries against it: the whole
message first (still catches a short, search-bar-like message), then each
of the message's own significant individual words, merged and deduped."""

import re
from typing import Any

from sympose.vault_search import search_structured

_STOPWORDS = {
    "a", "about", "an", "and", "any", "are", "as", "at", "be", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "how",
    "i", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our", "per",
    "please", "should", "tell", "that", "the", "their", "there", "this",
    "to", "was", "we", "were", "what", "which", "who", "will", "with",
    "would", "you", "your",
}
_MAX_KEYWORD_TERMS = 6
_MIN_KEYWORD_LEN = 3


def _keywords(user_message: str) -> list[str]:
    """The message's own significant words, in the order they appear,
    deduped, stopwords/short words dropped, capped so a long message can't
    turn into an unbounded number of vault walks."""
    words = re.findall(r"[\w'-]+", user_message.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for word in words:
        if word in _STOPWORDS or len(word) < _MIN_KEYWORD_LEN or word in seen:
            continue
        seen.add(word)
        keywords.append(word)
        if len(keywords) >= _MAX_KEYWORD_TERMS:
            break
    return keywords


def ground(profile: dict[str, Any], user_message: str, max_results: int = 5) -> list[dict[str, Any]]:
    """`max_results` defaults far lower than `search_structured`'s own
    default of 40: that default serves the dashboard's browsable two-tier
    UI, while a prompt only needs a handful of top matches to ground a
    reply."""
    seen_paths: set[str] = set()
    combined: list[dict[str, Any]] = []

    def _add(hits: list[dict[str, Any]]) -> None:
        for hit in hits:
            if hit["rel_path"] in seen_paths:
                continue
            seen_paths.add(hit["rel_path"])
            combined.append(hit)

    _add(search_structured(profile, user_message, max_results=max_results))
    for keyword in _keywords(user_message):
        if len(combined) >= max_results:
            break
        _add(search_structured(profile, keyword, max_results=max_results))

    combined = combined[:max_results]
    for idx, result in enumerate(combined, start=1):
        result["index"] = idx
    return combined
