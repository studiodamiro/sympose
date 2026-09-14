"""
Wikilink extraction and the inverted backlink index built from it, plus the
compact "ground-truth structure map" digest that surfaces the most-linked
notes from a vault_manifest snapshot — a backlinks-adjacent computation,
kept here rather than splitting off a module for one function.

`build_backlink_index` owns the only mutable cache in this module
(`_BACKLINK_CACHE`); anything that changes wikilink targets on disk
(rename, delete, a folder move) must call `clear_cache()` afterward — the
callers doing that live in vault.py / vault_write.py, not here.
"""

import logging
import os
import re
from collections import defaultdict
from typing import Any, Callable

from sympose import vault_paths
from sympose.config import config_manager, is_safe_path

log = logging.getLogger(__name__)

_WIKILINK_PATTERN = re.compile(r"\[\[([^\]\|#]+)(?:#([^\]\|]+))?(?:\|([^\]]+))?\]\]")

# Key: tuple of allowed_dirs paths → (combined_mtime, inverted index). Avoids
# a full vault walk on every message; invalidated by vault_paths.dirs_mtime.
_BACKLINK_CACHE: dict[
    tuple[str, ...], tuple[float, dict[str, list[dict[str, Any]]]]
] = {}


def clear_cache() -> None:
    """Invalidates the backlink index — call after any write that could
    change a note's wikilinks (rename, delete, folder move/delete)."""
    _BACKLINK_CACHE.clear()


def extract_wikilinks(content: str) -> list[dict[str, Any]]:
    """Extracts structured wikilink metadata from text content, supporting aliases and heading anchors."""
    links = []
    for match in _WIKILINK_PATTERN.finditer(content):
        target = match.group(1).strip()
        heading = match.group(2).strip() if match.group(2) else None
        alias = match.group(3).strip() if match.group(3) else None
        stem = os.path.splitext(os.path.basename(target))[0].lower().strip()
        links.append(
            {
                "target": target,
                "stem": stem,
                "heading": heading,
                "alias": alias,
                "raw": match.group(0),
            }
        )
    return links


def get_forward_links(
    profile: dict[str, Any],
    note_name: str,
    *,
    read_note_fn: Callable[[dict[str, Any], str], str],
) -> list[dict[str, Any]]:
    """Extracts all outgoing wikilinks from a given note within allowed
    vault folders. `read_note_fn` is `VaultManager.read_note` — that logic
    hasn't moved out of vault.py yet."""
    content = read_note_fn(profile, note_name)
    if not content or content.startswith("Note `") or content.startswith("⚠️"):
        return []
    return extract_wikilinks(content)


def build_backlink_index(profile: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Constructs an inverted backlink index, using a mtime cache to skip re-walks on unchanged vaults."""
    mv, allowed_dirs = (
        vault_paths.get_master_vault(),
        vault_paths.get_allowed_dirs(profile),
    )
    if not mv or not allowed_dirs:
        return {}

    cache_key = tuple(sorted(allowed_dirs))
    current_mtime = vault_paths.dirs_mtime(allowed_dirs)
    cached_mtime, cached_index = _BACKLINK_CACHE.get(cache_key, (0.0, {}))
    if current_mtime == cached_mtime and cached_index:
        return cached_index

    inverted_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_ignore = config_manager.get("vault.ignore_folders") or [
        ".obsidian",
        ".git",
        "Attachments",
        ".trash",
    ]
    ignore_dirs = {str(d).lower().strip() for d in raw_ignore}

    try:
        for allowed in allowed_dirs:
            if not os.path.exists(allowed):
                continue
            for root, dirs, files in os.walk(allowed):
                dirs[:] = [
                    d
                    for d in dirs
                    if d.lower() not in ignore_dirs and not d.startswith(".")
                ]
                for fn in sorted(files):
                    if fn.endswith((".md", ".markdown", ".txt")):
                        fp = os.path.join(root, fn)
                        if not is_safe_path(fp, allowed):
                            continue
                        rel_path = os.path.relpath(fp, mv)
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                for line_idx, line in enumerate(f, start=1):
                                    for match in _WIKILINK_PATTERN.finditer(line):
                                        target = match.group(1).strip()
                                        heading = (
                                            match.group(2).strip()
                                            if match.group(2)
                                            else None
                                        )
                                        alias = (
                                            match.group(3).strip()
                                            if match.group(3)
                                            else None
                                        )
                                        stem = (
                                            os.path.splitext(os.path.basename(target))[
                                                0
                                            ]
                                            .lower()
                                            .strip()
                                        )
                                        inverted_index[stem].append(
                                            {
                                                "source_file": fn,
                                                "rel_path": rel_path,
                                                "target": target,
                                                "target_stem": stem,
                                                "heading": heading,
                                                "alias": alias,
                                                "line_no": line_idx,
                                                "context_snippet": line.strip(),
                                            }
                                        )
                        except Exception as e:
                            log.debug(
                                "Skipping unreadable file in backlink index %s: %s",
                                rel_path,
                                e,
                            )
    except Exception as e:
        log.debug("Backlink index build ended early: %s", e)

    result = dict(inverted_index)
    _BACKLINK_CACHE[cache_key] = (current_mtime, result)
    return result


def get_backlinks(profile: dict[str, Any], note_name: str) -> list[dict[str, Any]]:
    """Queries the in-memory inverted index for all incoming references to note_name."""
    clean_target = note_name.strip().strip("\"'").replace("[[", "").replace("]]", "")
    stem = os.path.splitext(os.path.basename(clean_target))[0].lower().strip()
    index = build_backlink_index(profile)
    return index.get(stem, [])


def get_backlinks_digest(
    profile: dict[str, Any], note_name: str, max_entries: int = 15
) -> str:
    """Generates a high-density Markdown summary of backlinks for note_name."""
    clean_target = note_name.strip().strip("\"'").replace("[[", "").replace("]]", "")
    backlinks = get_backlinks(profile, clean_target)
    if not backlinks:
        return f"No backlinks found referencing `[[{clean_target}]]` in allowed vault folders."

    lines = [
        f"### ◀ Backlinks for `[[{clean_target}]]` ({len(backlinks)} reference(s) found):"
    ]
    for b in backlinks[:max_entries]:
        rel = b.get("rel_path", b.get("source_file", "unknown"))
        line_no = b.get("line_no", "")
        line_str = f" (Line {line_no})" if line_no else ""
        ctx = b.get("context_snippet", "")
        if ctx:
            lines.append(f"- **`{rel}`**{line_str}:\n  > {ctx[:200]}")
        else:
            lines.append(f"- **`{rel}`**{line_str}")

    if len(backlinks) > max_entries:
        lines.append(f"\n*(+ {len(backlinks) - max_entries} more references in vault)*")

    return "\n".join(lines)


def format_manifest_digest(
    manifest: dict[str, Any],
    max_folders: int = 30,
    max_tags: int = 12,
    max_hubs: int = 8,
) -> str:
    """Compact, disk-true structural map from an ADR-078 manifest — folder
    counts, top tags, most-linked notes, unresolved links. Structure only:
    no note text, so it says *where* to look, never *what a note says*."""
    nodes = manifest.get("nodes", [])
    real = [n for n in nodes if n.get("exists")]
    real_ids = {n["id"] for n in real}
    top = sorted(
        ((k, v) for k, v in manifest.get("folders", {}).items() if "/" not in k),
        key=lambda kv: -kv[1],
    )
    folder_lines = [
        f"- `{k}/` — {v} note{'s' if v != 1 else ''}" for k, v in top[:max_folders]
    ] or ["- *(flat vault — no folders)*"]

    tag_counts: dict[str, int] = {}
    inbound: dict[str, int] = {}
    for n in real:
        for t in n.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    for link in manifest.get("links", []):
        if link["target"] in real_ids:
            inbound[link["target"]] = inbound.get(link["target"], 0) + 1
    tag_line = (
        ", ".join(
            f"#{t} ({c})"
            for t, c in sorted(tag_counts.items(), key=lambda kv: -kv[1])[:max_tags]
        )
        or "—"
    )
    hub_line = (
        ", ".join(
            f"[[{h}]] ({c})"
            for h, c in sorted(inbound.items(), key=lambda kv: -kv[1])[:max_hubs]
        )
        or "—"
    )

    out = [
        f"### Ground-Truth Vault Structure Map ({len(real)} notes, {len(top)} top-level folders)",
        "",
        "**Folders:**",
        *folder_lines,
        "",
        f"**Top tags:** {tag_line}",
        f"**Most-linked notes:** {hub_line}",
    ]
    ghosts = [n["id"] for n in nodes if not n.get("exists")]
    if ghosts:
        sample = ", ".join(f"[[{g}]]" for g in ghosts[:6])
        out.append(
            f"**Unresolved links:** {len(ghosts)} ({sample}{', …' if len(ghosts) > 6 else ''})"
        )
    out.append("\n*Structure only — read the actual note for its contents.*")
    return "\n".join(out)
