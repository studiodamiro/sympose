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


def wiki_lint_write_gate(
    *,
    skills: list[Any],
    lint_auto_fix: bool,
    wiki_root: str,
    log_file: str,
    rel_path: str,
) -> str | None:
    """`None` when a WRITE_NOTE/APPEND_NOTE should proceed as normal.
    Otherwise the `_op_failed`-recognized denial string (ADR-134's
    structural gap, revisited): the code-level backstop for a persona that
    ignores its own `Wiki Lint Mode` prompt block.

    ADR-134 originally rejected hard-coding a check into WRITE_NOTE/
    APPEND_NOTE because those tags serve many skills, and a `wiki_ingest`
    persona's ordinary writes into `wiki.root` are indistinguishable from a
    lint-mode fix at this layer. That's still true in general, so this
    only fires for the one case where it isn't ambiguous: a persona that
    carries `wiki_lint` but *not* `wiki_ingest` has no other legitimate
    reason to touch a page under `wiki.root`, so with `lint_auto_fix` off,
    any such write except the append-only log is unambiguously a would-be
    auto-fix its own report-only mode forbids. A persona that also carries
    `wiki_ingest` is left entirely to the existing prompt-level judgment —
    still the only option there, per ADR-134's own reasoning.
    """
    names = {s.lower().strip() for s in skills if isinstance(s, str)}
    if "wiki_lint" not in names or "wiki_ingest" in names or lint_auto_fix:
        return None

    root = wiki_root.strip("/")
    if not root:
        return None

    prefix = root + "/"
    if not rel_path.startswith(prefix):
        return None
    if rel_path == f"{prefix}{log_file.strip()}":
        return None

    return (
        f"Security Error: `{rel_path}` is a wiki_lint page and this "
        "persona's `lint_auto_fix` is off — report the finding to "
        f"`{log_file}` instead of editing the page directly."
    )
