"""
Structural (not phrase-based) grounding checks: does a piece of text name
something that actually exists in the vault, regardless of how it's worded.

See ADR-124 (docs/journal/2026-09/2026-09-18_adr-124-...) for why this exists
alongside, not instead of, the phrase-based checks in vault_recall.py and
engine.py's `_VAULT_CLAIM_RE` - each catches a case the other misses. A
phrase like "your entry" or "in your vault" needs no real entity to fire and
so keeps catching referent-less claims this module can't touch; this module
catches a claim phrased in wholly unanticipated words ("this one is from
the People directory") as long as it names something real, which no fixed
phrase list can ever fully enumerate.

Pure text/data processing only - no I/O, and no dependency on vault.py
(which imports this module the same way it already imports vault_recall).
Callers hand in whatever vault-index-shaped data they already have.
"""

import re
from typing import Any

# A vault note or folder name a reply can plausibly be naming without
# quoting it verbatim: 1-3 Title-Case words. Not a vocabulary - every match
# is checked against the vault's real names by the caller, so casting this
# net wide (including ordinary sentence-initial capitals) costs nothing but
# a discarded lookup when nothing matches.
_CAPITALIZED_RUN_RE = re.compile(r"\b[A-Z][\w'-]{2,}(?:\s+[A-Z][\w'-]{2,}){0,2}\b")


def extract_referent_candidates(text: str, path_token_re: re.Pattern) -> list[str]:
    """Every path-shaped (via `path_token_re` - the caller's own
    VAULT_PATH_TOKEN_RE) and Title-Case token in `text`, in appearance
    order. Not filtered against real vault data here - that's the caller's
    job in `first_unverified_referent`, which is what makes false positives
    harmless (an ordinary capitalized word that isn't a real vault name is
    just a wasted lookup, not a wrong flag)."""
    if not text:
        return []
    return [m.group(0) for m in path_token_re.finditer(text)] + [
        m.group(0) for m in _CAPITALIZED_RUN_RE.finditer(text)
    ]


def real_vault_referents_from_snapshot(
    discovered_folders: dict[str, str], snapshot: list[dict[str, Any]]
) -> frozenset[str]:
    """Lowercased ground truth for structural claim-checking: every real
    folder name (from directory discovery) plus every note's filename stem
    and frontmatter title (from the vault snapshot). Built entirely from
    data the caller already read for other purposes - no new I/O pattern,
    no LLM call."""
    names = set(discovered_folders.keys())
    for entry in snapshot:
        file_name = entry.get("file_name", "")
        stem = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
        if stem:
            names.add(stem.lower())
        meta = entry.get("meta")
        title = meta.get("title") if isinstance(meta, dict) else None
        if title:
            names.add(str(title).strip().lower())
    return frozenset(n for n in names if n)


def first_unverified_referent(
    text: str,
    path_token_re: re.Pattern,
    real_referents: frozenset[str],
    extra_stop: frozenset[str] | set[str] = frozenset(),
) -> str:
    """First candidate in `text` naming a real vault folder, note, or
    title, in appearance order - '' if none does. The structural
    counterpart to phrase-based claim/intent detection (ADR-124): it flags
    a message or reply naming something real no matter how it's worded,
    instead of matching wording someone already had to anticipate.

    `extra_stop` mirrors `PersonaEngine._entity_guess`'s own parameter -
    names that are never a legitimate referent in this install (the active
    user, the personas themselves), resolved dynamically by the caller."""
    if not real_referents:
        return ""
    stop = {s.lower() for s in extra_stop}
    for cand in extract_referent_candidates(text, path_token_re):
        key = cand.strip().rstrip(".,!?\"'").lower()
        if key and key not in stop and key in real_referents:
            return cand.strip().rstrip(".,!?\"'")
    return ""


# Plain letter runs, case-insensitive - unlike `_CAPITALIZED_RUN_RE`, this
# assumes nothing about capitalization at all (ADR-123.5: plenty of real
# chat is typed all-lowercase, so a check that only fires on Title Case
# misses every one of those mentions). Splits on apostrophes on purpose -
# "dylan's" tokenizes as "dylan" + "s", so a possessive doesn't need its
# own stripping step to match the bare name.
_WORD_RE = re.compile(r"[A-Za-z]+")


def real_referent_mentioned(
    text: str,
    real_referents: frozenset[str],
    extra_stop: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Case-insensitive counterpart to `first_unverified_referent`: finds a
    real vault referent named in `text` with no capitalization assumed at
    all. Checks every 1-3 word window in appearance order, longest first
    at each position, so an exact multi-word title is preferred over a
    shorter, coincidental single-word match starting at the same spot -
    and, unlike a fixed-size regex run, a name embedded inside a longer
    ordinary phrase ("I ran into dylan today") still gets tried on its
    own instead of being swallowed into a window that matches nothing.

    Kept separate from `first_unverified_referent` rather than making that
    one capitalization-agnostic, so the outbound fabrication check's
    already-verified behavior (ADR-124) doesn't shift underneath it - this
    is for inbound chat, which can't be assumed to follow Title-Case
    conventions the way a model's own formatted reply usually does."""
    if not real_referents:
        return ""
    stop = {s.lower() for s in extra_stop}
    words = _WORD_RE.findall(text)
    for i in range(len(words)):
        for size in (3, 2, 1):
            if i + size > len(words):
                continue
            window = " ".join(words[i : i + size])
            key = window.lower()
            if key and key not in stop and key in real_referents:
                return window
    return ""


# A possessive mention ("Marco's birthday", "dylan's school") - unlike a
# bare word, this is a capitalization-independent signal that the speaker
# is naming a specific thing, not just using an ordinary word in a
# sentence. Used only for the miss side (ADR-123.5): reporting "nothing
# found" for every unmatched plain word would flag nearly every sentence,
# but a possessive is deliberately narrow enough not to.
_POSSESSIVE_RE = re.compile(r"\b([A-Za-z]+)'s\b")

# English's closed set of pronouns/adverbs that contract with "'s" ("it's"
# = "it is", "let's" = "let us") rather than possess anything - live bug,
# found against a real vault: "I'm bored, let's play a game" flagged "let"
# as a miss, since "let's" is syntactically identical to a genuine
# possessive and nothing about the text itself tells them apart. This is
# a fixed, complete grammatical class (not an open-ended list of phrases
# someone might use), so excluding it doesn't reopen the enumerable-phrase
# problem this project otherwise avoids - no one will ever name a vault
# entry "It" or "Let" for this to wrongly suppress.
_CONTRACTION_ONLY_WORDS = frozenset(
    {
        # Demonstratives / wh-words / existential adverbs
        "it",
        "that",
        "this",
        "what",
        "who",
        "here",
        "there",
        "how",
        "when",
        "where",
        "why",
        "let",
        "one",
        # Personal pronouns - "she's"/"he's"/"they's" contract just as
        # readily as "it's" does, and never name a specific real thing.
        "he",
        "she",
        "we",
        "they",
        "you",
        # Indefinite pronouns - "everyone's fine", "nobody's perfect":
        # grammatically possessive-shaped, but not a named referent.
        "everyone",
        "everybody",
        "someone",
        "somebody",
        "anyone",
        "anybody",
        "nobody",
        "everything",
        "something",
        "anything",
        "nothing",
        # Temporal deictic nouns - "today's a good day": possessive-shaped,
        # but naming a moment in time, not a specific real thing to look up.
        "today",
        "yesterday",
        "tomorrow",
        "tonight",
    }
)


def possessive_mentions(text: str) -> list[str]:
    """Every possessive-shaped mention in `text`, in appearance order -
    the bare name before the "'s", not the possessive form itself. Skips
    the closed set of words that only ever contract with "'s" rather than
    possess something, so "let's"/"it's"/"that's" aren't mistaken for a
    named referent."""
    return [
        name
        for name in _POSSESSIVE_RE.findall(text)
        if name.lower() not in _CONTRACTION_ONLY_WORDS
    ]
