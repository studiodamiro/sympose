"""
Full-text vault search — classifies every note under a persona's allowed
folders as a title/tag/content match against a query, with a snippet.
Ported from sympose-legacy's `direct` search path (see docs/decisions/002)
onto this backend's existing `vault_snapshot.get_vault_snapshot`, which
already does the mtime-cached walk-and-parse this needs. This is also the
grounding mechanism for chat, once that exists — the same matcher, just
auto-triggered per turn instead of by a typed query.

Always whole-persona-scope, never narrowed to one folder — the web app
derives both its "in the folder you're viewing" and "beyond it" tiers by
filtering one unscoped result set client-side (`rel_path` prefix), rather
than this module re-deriving "which folder is the user looking at" from
the menu's own top-level id. That's deliberate: the menu id is only ever
the *first* path segment of a persona's sandbox (`vault_tree.build_tree`
folds every nested segment into one top-level entry), so mapping it back
to real directories here would either duplicate that folding logic or
approximate it with fragile path-segment string matching — better owned
in exactly one place (`vault_tree`), not re-derived a second way.
"""

import logging
from typing import Any

from sympose import vault_paths
from sympose.vault_manifest_build import _stem, _tags_of
from sympose.vault_snapshot import get_vault_snapshot

log = logging.getLogger(__name__)


def _truncate_snippet(text: str, limit: int = 70) -> str:
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _extract_title_match_snippet(body: str) -> str:
    fl = next(
        (
            line.strip("# \t\r")
            for line in body.splitlines()
            if line.strip() and not line.startswith("---") and ":" not in line
        ),
        "",
    )
    clean_fl = _truncate_snippet(" ".join(fl.split()))
    return clean_fl or "Exact title match"


def _extract_content_match(body: str, query_clean: str) -> tuple[int, str]:
    """Line number and display snippet for a content match already
    confirmed to exist somewhere in `body`. A query that spans multiple
    lines (e.g. a chat message verbatim-quoting two consecutive lines
    from a note) can't be found by searching one line at a time — a
    whole-body substring search instead, with the returned line number
    and snippet anchored to where the match actually starts."""
    lower_body = body.lower()
    match_idx = lower_body.find(query_clean)
    if match_idx == -1:
        return 1, ""
    line_no = lower_body.count("\n", 0, match_idx) + 1
    line = body.splitlines()[line_no - 1]
    clean_l = " ".join(line.strip().strip("#*-> ").split())
    first_query_line = query_clean.splitlines()[0] if query_clean else query_clean
    q_idx = clean_l.lower().find(first_query_line)
    if q_idx > 25:
        clean_l = "..." + clean_l[max(q_idx - 15, 0) :]
    return line_no, _truncate_snippet(clean_l)


def _base_match_result(entry: dict[str, Any], match_type: str, tags: list[str]) -> dict[str, Any]:
    file, meta = entry["file_name"], entry["meta"]
    return {
        "file_name": file,
        "rel_path": entry["rel_path"],
        "match_type": match_type,
        "line_no": 1,
        "snippet": "",
        "title": meta.get("title") or meta.get("name") or _stem(file),
        "tags": tags,
    }


def _classify_snapshot_entry(entry: dict[str, Any], query_clean: str) -> dict[str, Any] | None:
    """One vault_snapshot entry classified as a title/tag/content match (in
    that priority order — a note tagged `#urgent` is a deliberate tag match
    even though "urgent" would also satisfy the content check), or `None`
    when it matches nothing. The title check is against the filename's stem
    (extension stripped), not the raw filename — otherwise a query like
    "md" would spuriously title-match every note via its own `.md`
    extension. Matching against `body`, not `full_content`, for the same
    reason on the content side: `full_content` still carries the raw YAML
    frontmatter block, and a value like `status: keyword` surfacing as a
    "content" match on prose the user never wrote is exactly the kind of
    gap that matters once this matcher also drives chat grounding (see the
    module docstring). Filename only for the title check, not the whole
    rel_path — matching an ancestor *folder* name would otherwise flood
    results with folder-name coincidences."""
    file, body, meta = entry["file_name"], entry["body"], entry["meta"]
    tags = _tags_of(meta)

    if query_clean in _stem(file).lower():
        result = _base_match_result(entry, "title", tags)
        result["snippet"] = _extract_title_match_snippet(body)
        return result

    matched_tags = [t for t in tags if query_clean in t.lower()]
    if matched_tags:
        result = _base_match_result(entry, "tag", tags)
        result["snippet"] = " ".join(f"#{t}" for t in matched_tags)
        return result

    if query_clean in body.lower():
        line_no, snippet = _extract_content_match(body, query_clean)
        result = _base_match_result(entry, "content", tags)
        result["line_no"] = line_no
        result["snippet"] = snippet or f"Match found on line {line_no}"
        return result

    return None


def search_structured(
    profile: dict[str, Any],
    query: str,
    max_results: int = 40,
) -> list[dict[str, Any]]:
    """Every note under `profile`'s allowed folders classified as a
    title/tag/content match, capped at `max_results` in the returned list
    (title > tag > content priority). Classifies every entry rather than
    stopping early once enough candidates accumulate — `get_vault_snapshot`
    already reads and parses every file into memory before this function
    ever sees the first entry (it's mtime-cached, not a lazy per-call walk),
    so an early stop here wouldn't save any real I/O; it would only risk
    never reaching a genuine title match that happens to sit later in walk
    order, silently breaking the title > tag > content priority this
    function otherwise guarantees. `max_results` defaults higher than a
    single-tier search would need, because the one caller (the web app)
    derives two tiers — the folder in view, and everything beyond it —
    from this one unscoped list, and a low cap could starve the in-folder
    tier if enough out-of-folder matches happened to come first."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None:
        return []
    mv, allowed_dirs = scope

    query_clean = query.lower().strip().strip("\"'")
    if not query_clean:
        return []

    titles: list[dict[str, Any]] = []
    tags: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    try:
        for entry in get_vault_snapshot(mv, allowed_dirs):
            result = _classify_snapshot_entry(entry, query_clean)
            if result is None:
                continue
            if result["match_type"] == "title":
                titles.append(result)
            elif result["match_type"] == "tag":
                tags.append(result)
            else:
                contents.append(result)
    except Exception as e:
        # A single unreadable/corrupt note mid-walk degrades to whatever
        # matches were already found, rather than 500-ing the whole search.
        log.debug("Vault search ended early: %s", e)

    all_results = (titles + tags + contents)[:max_results]
    for idx, res in enumerate(all_results, start=1):
        res["index"] = idx
    return all_results
