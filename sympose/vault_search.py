"""
Full-text vault search — classifies every note under a persona's allowed
folders as a title/tag/content match against a query, with a snippet.
Ported from sympose-legacy's `direct` search path (see docs/decisions/002)
onto this backend's existing `vault_snapshot.get_vault_snapshot`, which
already does the mtime-cached walk-and-parse this needs. This is also the
grounding mechanism for chat, once that exists — the same matcher, just
auto-triggered per turn instead of by a typed query.
"""

import logging
import os
from typing import Any

from sympose import vault_paths
from sympose.security import is_safe_path
from sympose.vault_manifest_build import _stem, _tags_of
from sympose.vault_snapshot import get_vault_snapshot

log = logging.getLogger(__name__)


def _resolve_search_dirs(mv: str, allowed_dirs: list[str], target_folder: str | None) -> list[str]:
    """`allowed_dirs` narrowed to `target_folder` — the folder currently in
    view in the dashboard, matching the client-side filter's existing
    "search within what you're looking at" scope.

    `target_folder` is the dashboard's top-level menu id, which is only the
    *first* path segment of a persona's own sandbox when that sandbox is
    nested (`vault_folders: ["Notes/Journal"]` still shows as one "Notes"
    entry — `vault_tree.build_tree` folds every path segment into
    intermediate nodes the same way regardless of scope, and the menu never
    descends past the top-level entry per-persona). So a match on *any*
    path segment of an allowed dir counts, not just its exact basename —
    the old basename-only check missed every nested sandbox and silently
    returned zero results for it. Every allowed dir sharing that segment is
    included (two sandboxes both nested under "Notes" both show under one
    "Notes" menu entry, so both belong in that entry's search). Falls back
    to joining `target_folder` onto each allowed dir, for a whole-vault
    persona browsing into a real subfolder that isn't a sandbox boundary at
    all. A folder that resolves neither way is a scope miss, not a
    fallback to searching the whole vault instead."""
    if not target_folder:
        return allowed_dirs
    tf_lower = target_folder.strip().lower()
    if not tf_lower:
        return allowed_dirs

    matched = []
    for d in allowed_dirs:
        rel = os.path.relpath(d, mv).replace(os.sep, "/")
        if tf_lower in (s.lower() for s in rel.split("/")):
            matched.append(d)
    if matched:
        return matched

    for d in allowed_dirs:
        candidate = os.path.join(d, target_folder)
        if os.path.isdir(candidate) and is_safe_path(candidate, d):
            return [candidate]
    return []


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


def _extract_content_match(full_content: str, query_clean: str) -> tuple[int, str]:
    for line_idx, line in enumerate(full_content.splitlines(), start=1):
        if query_clean in line.lower():
            clean_l = " ".join(line.strip().strip("#*-> ").split())
            q_idx = clean_l.lower().find(query_clean)
            if q_idx > 25:
                clean_l = "..." + clean_l[max(q_idx - 15, 0) :]
            return line_idx, _truncate_snippet(clean_l)
    return 1, ""


def _base_match_result(entry: dict[str, Any], match_type: str, tags: list[str]) -> dict[str, Any]:
    file, meta = entry["file_name"], entry["meta"]
    return {
        "file_name": file,
        "rel_path": entry["rel_path"],
        "match_type": match_type,
        "line_no": 1,
        "snippet": "",
        "title": meta.get("title") or meta.get("name") or os.path.splitext(file)[0],
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
    target_folder: str | None = None,
    max_results: int = 15,
) -> list[dict[str, Any]]:
    """Every note under `profile`'s allowed folders (optionally narrowed to
    `target_folder`) classified as a title/tag/content match, capped at
    `max_results` in the returned list. Classifies every entry rather than
    stopping early once enough candidates accumulate — `get_vault_snapshot`
    already reads and parses every file into memory before this function
    ever sees the first entry (it's mtime-cached, not a lazy per-call walk),
    so an early stop here wouldn't save any real I/O; it would only risk
    never reaching a genuine title match that happens to sit later in walk
    order, silently breaking the title > tag > content priority this
    function otherwise guarantees."""
    mv = vault_paths.get_master_vault()
    allowed_dirs = vault_paths.get_allowed_dirs(profile)
    if not mv or not allowed_dirs:
        return []

    search_dirs = _resolve_search_dirs(mv, allowed_dirs, target_folder)
    query_clean = query.lower().strip().strip("\"'")
    if not query_clean or not search_dirs:
        return []

    buckets: dict[str, list[dict[str, Any]]] = {"title": [], "tag": [], "content": []}
    try:
        for entry in get_vault_snapshot(mv, search_dirs):
            result = _classify_snapshot_entry(entry, query_clean)
            if result is not None:
                buckets[result["match_type"]].append(result)
    except Exception as e:
        # A single unreadable/corrupt note mid-walk degrades to whatever
        # matches were already found, rather than 500-ing the whole search.
        log.debug("Vault search ended early: %s", e)

    all_results = (buckets["title"] + buckets["tag"] + buckets["content"])[:max_results]
    for idx, res in enumerate(all_results, start=1):
        res["index"] = idx
    return all_results
