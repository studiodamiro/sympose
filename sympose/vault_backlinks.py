"""
Backlink lookups for rename's wikilink-rewrite step, derived from the same
ephemeral manifest the tree endpoint already builds — no separate inverted-
index cache. The legacy backend maintains one (`vault_links.py`) because it
also serves an always-on `GET /api/vault/backlinks` endpoint under
real-time chat load; this backend only needs backlinks momentarily, during
a rename, so reusing the manifest builder is simpler and one less cache to
keep coherent.
"""

import os
from typing import Any

from sympose import vault_manifest_build, vault_paths
from sympose.vault_snapshot import get_vault_snapshot


def _build_manifest(profile: dict[str, Any]) -> dict:
    """Scoped to the *renaming* persona's own sandbox, matching how the
    legacy backend's equivalent lookup (`VaultManager._find_notes_by_stem`)
    was scoped — a persona restricted to one folder can't discover, and
    therefore can't silently rewrite, a wikilink living in a note outside
    its own sandbox. That's the sandbox boundary working as designed, not
    a missed case: the tradeoff is a backlink outside the sandbox is left
    stale rather than rewritten. Today's only persona (`samantha`) has
    `vault_folders: ["*"]`, so this never actually narrows anything."""
    mv = vault_paths.get_master_vault()
    allowed_dirs = vault_paths.get_allowed_dirs(profile)
    return vault_manifest_build.build(mv, get_vault_snapshot(mv, allowed_dirs))


def get_backlinks(profile: dict[str, Any], note_stem: str) -> list[dict[str, str]]:
    """Every note whose wikilinks name `note_stem` (by bare stem, matching
    what's actually written in the source text) — used to find which notes
    need relinking after a rename."""
    stem_l = note_stem.strip().lower()
    manifest = _build_manifest(profile)
    by_id = {n["id"]: n for n in manifest["nodes"]}
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for link in manifest["links"]:
        if link.get("target_stem", "").strip().lower() != stem_l:
            continue
        source = by_id.get(link["source"])
        rel = source["rel_path"] if source else link["source"]
        if rel not in seen:
            seen.add(rel)
            out.append({"rel_path": rel})
    return out


def find_notes_by_stem(profile: dict[str, Any], stem: str) -> list[str]:
    """Vault-relative paths of every real note sharing `stem` — lets a
    rename tell an unambiguous bare wikilink from one that could mean a
    different, same-named note elsewhere."""
    want = stem.strip().lower()
    manifest = _build_manifest(profile)
    return [
        n["rel_path"]
        for n in manifest["nodes"]
        if n.get("exists") and os.path.splitext(os.path.basename(n["rel_path"]))[0].lower() == want
    ]
