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

    if target_folder:
        # `allowed_dirs` only ever holds the persona's *root* access points
        # (for a full-vault `["*"]` persona, that's just the vault itself) -
        # matching a named folder against their basenames alone misses any
        # actual subfolder, like `Thoughts/` under the vault root. Resolve it
        # the same way discovery elsewhere in the vault module does: either
        # an allowed dir's own name, or an immediate child of one.
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
        # A named folder that can't be resolved is a scope miss, not an
        # invitation to search the whole vault instead - that silent
        # widening is exactly what let an unrelated note answer a request
        # meant to be confined to one folder.
        search_dirs = [resolved] if resolved else []
    else:
        search_dirs = allowed_dirs

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

    title_matches: list[dict[str, Any]] = []
    tag_matches: list[dict[str, Any]] = []
    content_matches: list[dict[str, Any]] = []

    try:
        for entry in get_vault_snapshot_fn(mv, search_dirs):
            file, rel_path, full_content, meta, body = (
                entry["file_name"],
                entry["rel_path"],
                entry["full_content"],
                entry["meta"],
                entry["body"],
            )
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.replace(",", " ").split() if t.strip()]
            elif not isinstance(tags, list):
                tags = []

            # Filename only, not the whole `rel_path` — the old
            # rel_path-inclusive check meant a query matching an ancestor
            # *folder* name (e.g. "quote" -> "Quotes/") classified every
            # note in that folder as a "title" match, flooding the
            # `max_results` cap with folder-name coincidences and hiding
            # genuine tag/content hits elsewhere in the vault.
            is_title_match = query_clean in file.lower()
            matched_tags = [t for t in tags if query_clean in str(t).lower()]

            if is_title_match:
                fl = next(
                    (
                        line.strip("# \t\r")
                        for line in body.splitlines()
                        if line.strip()
                        and not line.startswith("---")
                        and ":" not in line
                    ),
                    "",
                )
                clean_fl = " ".join(fl.split())
                if len(clean_fl) > 70:
                    clean_fl = clean_fl[:67].rstrip() + "..."
                title_matches.append(
                    {
                        "file_name": file,
                        "rel_path": rel_path,
                        "abs_path": entry["abs_path"],
                        "match_type": "title",
                        "line_no": 1,
                        "snippet": clean_fl or "Exact title match",
                        "title": meta.get("title")
                        or meta.get("name")
                        or os.path.splitext(file)[0],
                        "tags": tags,
                        "meta": meta,
                    }
                )
            # Checked ahead of the raw full-content substring test below so
            # a note tagged `#urgent` classifies as a deliberate tag match
            # rather than an incidental content hit that merely happens to
            # contain the tag's literal text in its frontmatter block.
            elif matched_tags:
                tag_matches.append(
                    {
                        "file_name": file,
                        "rel_path": rel_path,
                        "abs_path": entry["abs_path"],
                        "match_type": "tag",
                        "line_no": 1,
                        "snippet": " ".join(f"#{t}" for t in matched_tags),
                        "title": meta.get("title")
                        or meta.get("name")
                        or os.path.splitext(file)[0],
                        "tags": tags,
                        "meta": meta,
                    }
                )
            elif query_clean in full_content.lower():
                matched_line_no = 1
                matched_snippet = ""
                for line_idx, line in enumerate(full_content.splitlines(), start=1):
                    if query_clean in line.lower():
                        matched_line_no = line_idx
                        clean_l = " ".join(line.strip().strip("#*-> ").split())
                        q_idx = clean_l.lower().find(query_clean)
                        if q_idx > 25:
                            clean_l = "..." + clean_l[max(q_idx - 15, 0) :]
                        if len(clean_l) > 70:
                            clean_l = clean_l[:67].rstrip() + "..."
                        matched_snippet = clean_l
                        break
                content_matches.append(
                    {
                        "file_name": file,
                        "rel_path": rel_path,
                        "abs_path": entry["abs_path"],
                        "match_type": "content",
                        "line_no": matched_line_no,
                        "snippet": matched_snippet
                        or f"Match found on line {matched_line_no}",
                        "title": meta.get("title")
                        or meta.get("name")
                        or os.path.splitext(file)[0],
                        "tags": tags,
                        "meta": meta,
                    }
                )

            if (
                len(title_matches) + len(tag_matches) + len(content_matches)
                >= max_results * 2
            ):
                break
    except Exception as e:
        log.debug("Vault search ended early: %s", e)

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
