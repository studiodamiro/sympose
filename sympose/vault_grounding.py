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
