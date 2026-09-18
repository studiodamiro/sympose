"""
Wiki Lint Support (ADR-134) — pure helpers over the existing vault
manifest graph (ADR-078), scoped to `wiki.root`, backing the `wiki_lint`
skill's orphan-page check. No new indexing: reuses
`VaultManager.get_manifest()`'s already-persisted nodes/links rather than
building a parallel graph.
"""

from typing import Any


def wiki_pages(manifest: dict[str, Any], wiki_root: str) -> list[dict[str, Any]]:
    """Real (non-ghost) nodes whose id lives under `wiki_root`."""
    prefix = wiki_root.strip("/") + "/"
    return [
        n
        for n in manifest.get("nodes", [])
        if n.get("exists") and n.get("id", "").startswith(prefix)
    ]


def orphan_pages(manifest: dict[str, Any], wiki_root: str) -> list[str]:
    """Wiki-root page ids with zero inbound links from anywhere in the
    vault — candidates for the wiki_lint skill to flag or fold into
    another page."""
    linked_targets = {link.get("target") for link in manifest.get("links", [])}
    return [
        n["id"] for n in wiki_pages(manifest, wiki_root) if n["id"] not in linked_targets
    ]
