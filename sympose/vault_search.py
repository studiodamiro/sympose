"""
Fast, sandboxed vault search: the `direct` (walk + substring) path and the
`sqlite_fts` fast path built on top of vault_index, plus the per-persona
"last search results" cache that `/read <n>` and `/open <n>` resolve
against.

Building the flat, parsed content list every search walks over is the one
genuinely expensive part — that's `get_vault_snapshot`, owned by vault.py
(it has other callers outside search: reindex hooks, manifest/graph
building), so every function here that needs it takes it as a
`get_vault_snapshot_fn` hook rather than importing vault.py back, which
would cycle.
"""

import logging
import os
from typing import Any, Callable

from sympose import vault_index, vault_paths
from sympose.config import config_manager, is_safe_path

log = logging.getLogger(__name__)

# Keyed strictly per-persona (profile["handle"]) — no shared fallback key. A
# shared key would let persona A's search results leak into persona B's
# `/read <n>` if B hadn't searched yet in the same process (two Slack
# threads on different personas, or two CLI runs sharing a workspace).
_last_searches: dict[str, list[dict[str, Any]]] = {}


def _workspace_dir() -> str:
    return os.path.dirname(os.path.abspath(config_manager.config_path)) or "."


def _search_fts(
    mv: str,
    search_dirs: list[str],
    query_clean: str,
    max_results: int,
    *,
    get_vault_snapshot_fn: Callable[[str, list[str]], list[dict[str, Any]]],
) -> list[dict[str, Any]] | None:
    """`sqlite_fts` search path (ADR-070.5). Returns None if the index isn't
    usable this run — the caller falls back to the `direct` walk below."""
    workspace_dir = _workspace_dir()
    fresh = vault_index.ensure_fresh(
        workspace_dir,
        mv,
        lambda: get_vault_snapshot_fn(mv, [mv]),
        ignore_folders=config_manager.get("vault.ignore_folders"),
    )
    if not fresh:
        return None
    rows = vault_index.query(workspace_dir, mv, query_clean, search_dirs, max_results)
    if rows is None:
        return None
    results = []
    for idx, r in enumerate(rows, start=1):
        results.append(
            {
                "file_name": r["file_name"],
                "rel_path": r["rel_path"],
                "abs_path": os.path.join(mv, r["rel_path"]),
                "match_type": r["match_type"],
                "line_no": 1,
                "snippet": r["snippet"],
                "title": r["title"],
                "tags": r["tags"],
                "meta": {},
                "index": idx,
            }
        )
    return results


def _resolve_search_dirs(
    allowed_dirs: list[str], target_folder: str | None
) -> list[str]:
    """`allowed_dirs` narrowed to `target_folder`. `allowed_dirs` only ever
    holds the persona's *root* access points (for a full-vault `["*"]`
    persona, that's just the vault itself) - matching a named folder
    against their basenames alone misses any actual subfolder, like
    `Thoughts/` under the vault root, so it's resolved the same way
    discovery elsewhere in the vault module does: either an allowed dir's
    own name, or an immediate child of one. A named folder that can't be
    resolved is a scope miss, not an invitation to search the whole vault
    instead - that silent widening is exactly what let an unrelated note
    answer a request meant to be confined to one folder."""
    if not target_folder:
        return allowed_dirs
    tf_lower = target_folder.lower()
    resolved = next(
        (d for d in allowed_dirs if os.path.basename(d).lower() == tf_lower),
        None,
    )
    if resolved is None:
        for d in allowed_dirs:
            candidate = os.path.join(d, target_folder)
            if os.path.isdir(candidate) and is_safe_path(candidate, d):
                resolved = candidate
                break
    return [resolved] if resolved else []


def _normalize_tags(meta: dict[str, Any]) -> list[str]:
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        return [t.strip() for t in tags.replace(",", " ").split() if t.strip()]
    if isinstance(tags, list):
        return tags
    return []


def _extract_title_match_snippet(body: str) -> str:
    fl = next(
        (
            line.strip("# \t\r")
            for line in body.splitlines()
            if line.strip() and not line.startswith("---") and ":" not in line
        ),
        "",
    )
    clean_fl = " ".join(fl.split())
    if len(clean_fl) > 70:
        clean_fl = clean_fl[:67].rstrip() + "..."
    return clean_fl or "Exact title match"


def _extract_content_match(full_content: str, query_clean: str) -> tuple[int, str]:
    for line_idx, line in enumerate(full_content.splitlines(), start=1):
        if query_clean in line.lower():
            clean_l = " ".join(line.strip().strip("#*-> ").split())
            q_idx = clean_l.lower().find(query_clean)
            if q_idx > 25:
                clean_l = "..." + clean_l[max(q_idx - 15, 0) :]
            if len(clean_l) > 70:
                clean_l = clean_l[:67].rstrip() + "..."
            return line_idx, clean_l
    return 1, ""


def _base_match_result(
    entry: dict[str, Any], match_type: str, tags: list[str]
) -> dict[str, Any]:
    file, meta = entry["file_name"], entry["meta"]
    return {
        "file_name": file,
        "rel_path": entry["rel_path"],
        "abs_path": entry["abs_path"],
        "match_type": match_type,
        "line_no": 1,
        "snippet": "",
        "title": meta.get("title") or meta.get("name") or os.path.splitext(file)[0],
        "tags": tags,
        "meta": meta,
    }


def _classify_snapshot_entry(
    entry: dict[str, Any], query_clean: str
) -> dict[str, Any] | None:
    """One vault_snapshot entry classified as a title/tag/content match (in
    that priority order — a note tagged `#urgent` is a deliberate tag
    match even though "urgent" would also satisfy the content check), or
    None when it matches nothing. Filename only for the title check, not
    the whole rel_path — matching an ancestor *folder* name would
    otherwise flood results with folder-name coincidences and hide
    genuine tag/content hits elsewhere in the vault."""
    file, full_content, meta, body = (
        entry["file_name"],
        entry["full_content"],
        entry["meta"],
        entry["body"],
    )
    tags = _normalize_tags(meta)

    if query_clean in file.lower():
        result = _base_match_result(entry, "title", tags)
        result["snippet"] = _extract_title_match_snippet(body)
        return result

    matched_tags = [t for t in tags if query_clean in str(t).lower()]
    if matched_tags:
        result = _base_match_result(entry, "tag", tags)
        result["snippet"] = " ".join(f"#{t}" for t in matched_tags)
        return result

    if query_clean in full_content.lower():
        line_no, snippet = _extract_content_match(full_content, query_clean)
        result = _base_match_result(entry, "content", tags)
        result["line_no"] = line_no
        result["snippet"] = snippet or f"Match found on line {line_no}"
        return result

    return None


def _scan_snapshot_for_matches(
    get_vault_snapshot_fn: Callable[[str, list[str]], list[dict[str, Any]]],
    mv: str,
    search_dirs: list[str],
    query_clean: str,
    max_results: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """The `direct` search path's snapshot walk, classifying and bucketing
    each entry until 2x `max_results` total matches accumulate (title/tag
    matches are cheap and usually plenty; capping early keeps a huge vault
    from being fully re-scanned on a broad query). Returns
    (title_matches, tag_matches, content_matches)."""
    buckets: dict[str, list[dict[str, Any]]] = {"title": [], "tag": [], "content": []}
    try:
        for entry in get_vault_snapshot_fn(mv, search_dirs):
            result = _classify_snapshot_entry(entry, query_clean)
            if result is not None:
                buckets[result["match_type"]].append(result)
            if sum(len(b) for b in buckets.values()) >= max_results * 2:
                break
    except Exception as e:
        log.debug("Vault search ended early: %s", e)
    return buckets["title"], buckets["tag"], buckets["content"]


def search_structured(
    profile: dict[str, Any],
    query: str,
    target_folder: str | None = None,
    max_results: int = 15,
    *,
    get_vault_snapshot_fn: Callable[[str, list[str]], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Performs fast sandboxed vault search returning structured match metadata with snippets."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return []

    search_dirs = _resolve_search_dirs(allowed_dirs, target_folder)
    query_clean = query.lower().strip().strip("\"'")
    if not query_clean:
        return []

    if config_manager.get("vault.search_mode", "direct") == "sqlite_fts":
        fts_results = _search_fts(
            mv,
            search_dirs,
            query_clean,
            max_results,
            get_vault_snapshot_fn=get_vault_snapshot_fn,
        )
        if fts_results is not None:
            handle_key = profile.get("handle", "default").lower()
            _last_searches[handle_key] = fts_results
            return fts_results
        # Index unusable this run (no FTS5, or a rebuild failure) — fall
        # through to `direct` below rather than return an empty result.

    title_matches, tag_matches, content_matches = _scan_snapshot_for_matches(
        get_vault_snapshot_fn, mv, search_dirs, query_clean, max_results
    )
    all_results = (title_matches + tag_matches + content_matches)[:max_results]
    for idx, res in enumerate(all_results, start=1):
        res["index"] = idx

    handle_key = profile.get("handle", "default").lower()
    _last_searches[handle_key] = all_results
    return all_results


def get_last_search(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns the most recent search results for the given profile."""
    handle_key = profile.get("handle", "default").lower()
    return _last_searches.get(handle_key, [])


def format_search_digest(query: str, results: list[dict[str, Any]]) -> str:
    """Formats structured search results into a clean, high-density Markdown list."""
    if not results:
        return f"No notes found matching `{query}` in allowed vault folders."

    lines = [
        f'### 🔍 Vault Search: "{query}" ({len(results)} note{"s" if len(results) != 1 else ""} found):\n'
    ]
    for r in results:
        idx = r.get("index", 1)
        rel = r.get("rel_path", r.get("file_name", "note.md"))
        mtype = r.get("match_type", "content")
        line_no = r.get("line_no", 1)
        snippet = r.get("snippet", "")
        tags = r.get("tags", [])
        tag_str = (
            f" `[{' '.join('#' + t.lstrip('#') for t in tags[:3])}]`" if tags else ""
        )

        type_label = "*(Title Match)*" if mtype == "title" else f"*(Line {line_no})*"
        lines.append(f"**[{idx}] `{rel}`** {type_label}{tag_str}")
        if snippet:
            lines.append(f"  > {snippet}")
        lines.append("")

    lines.append(
        "──────────────────────────────────────────────────────────────────────────"
    )
    lines.append(
        "*Quick Nav: `/read <#>` to view in terminal | `/open <#>` to open in Obsidian | `/vault back` to return*"
    )
    return "\n".join(lines)


def search(
    profile: dict[str, Any],
    query: str,
    target_folder: str | None = None,
    *,
    get_vault_snapshot_fn: Callable[[str, list[str]], list[dict[str, Any]]],
) -> str:
    results = search_structured(
        profile,
        query,
        target_folder=target_folder,
        get_vault_snapshot_fn=get_vault_snapshot_fn,
    )
    return format_search_digest(query, results)
