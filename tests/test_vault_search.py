"""Tests for sympose.vault_search — title/tag/content classification, per
docs/decisions/002 (this is also the future grounding mechanism, so its
match priority and snippet behavior are worth pinning down directly)."""

import os

import pytest

from sympose import vault_search


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
    return str(tmp_path)


def _write(vault_root: str, rel_path: str, content: str) -> None:
    full = os.path.join(vault_root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def test_title_match_beats_content_match(vault_root):
    _write(vault_root, "Typography.md", "Some notes about fonts.")
    _write(vault_root, "Other.md", "This note mentions typography in passing.")

    results = vault_search.search_structured({"vault_folders": ["*"]}, "typography")

    assert [r["rel_path"] for r in results] == ["Typography.md", "Other.md"]
    assert results[0]["match_type"] == "title"
    assert results[1]["match_type"] == "content"


def test_tag_match_is_reported_with_matching_tags_only(vault_root):
    _write(
        vault_root,
        "Note.md",
        "---\ntags: [urgent, reading]\n---\nBody text.",
    )

    results = vault_search.search_structured({"vault_folders": ["*"]}, "urgent")

    assert results[0]["match_type"] == "tag"
    assert results[0]["snippet"] == "#urgent"


def test_content_match_reports_line_number_and_snippet(vault_root):
    _write(vault_root, "Note.md", "line one\nline two has the keyword\nline three")

    results = vault_search.search_structured({"vault_folders": ["*"]}, "keyword")

    assert results[0]["match_type"] == "content"
    assert results[0]["line_no"] == 2
    assert "keyword" in results[0]["snippet"]


def test_no_match_returns_empty(vault_root):
    _write(vault_root, "Note.md", "nothing relevant here")

    assert vault_search.search_structured({"vault_folders": ["*"]}, "zzz") == []


def test_search_is_scoped_to_allowed_dirs_not_the_whole_vault(vault_root):
    # No folder-narrowing exists in this module anymore — the dashboard
    # derives its in-folder/beyond-folder tiers by filtering one unscoped
    # result set client-side instead. What this module still owns is the
    # persona's own sandbox boundary.
    _write(vault_root, "Code/Snippet.md", "keyword here")
    _write(vault_root, "Journal/Entry.md", "keyword here too")

    results = vault_search.search_structured(
        {"vault_folders": ["Code"]}, "keyword"
    )

    assert [r["rel_path"] for r in results] == ["Code/Snippet.md"]


def test_nested_persona_scope_is_searched_in_full(vault_root):
    # A persona scoped to a nested folder ("Team/ProjectX") is still
    # searched by its real, full sandbox path — nothing here re-derives
    # that from a menu id anymore.
    _write(vault_root, "Team/ProjectX/Note.md", "keyword here")

    results = vault_search.search_structured(
        {"vault_folders": ["Team/ProjectX"]}, "keyword"
    )

    assert [r["rel_path"] for r in results] == ["Team/ProjectX/Note.md"]


def test_title_match_excludes_the_file_extension(vault_root):
    # `file_name` includes the extension — matching against the raw
    # filename would make a query like "md" spuriously title-match every
    # note in the vault via its own `.md` extension.
    _write(vault_root, "Note.md", "nothing relevant in the body")

    assert vault_search.search_structured({"vault_folders": ["*"]}, "md") == []


def test_content_match_ignores_frontmatter(vault_root):
    # Content matches classify against `body`, not `full_content` — the raw
    # YAML frontmatter block isn't prose the user wrote, and surfacing a
    # frontmatter value as if it were a body match is exactly the kind of
    # gap that matters once this matcher also drives chat grounding.
    _write(
        vault_root,
        "Note.md",
        "---\nstatus: shadowkeyword\n---\nNothing relevant in the body.",
    )

    assert vault_search.search_structured({"vault_folders": ["*"]}, "shadowkeyword") == []


def test_max_results_caps_the_returned_list(vault_root):
    for i in range(20):
        _write(vault_root, f"Note{i}.md", "keyword in every one of these")

    results = vault_search.search_structured(
        {"vault_folders": ["*"]}, "keyword", max_results=5
    )

    assert len(results) == 5
    assert [r["index"] for r in results] == [1, 2, 3, 4, 5]


def test_title_match_is_never_dropped_by_a_flood_of_content_matches(vault_root):
    # Regression: an earlier version capped the scan once enough total
    # candidates had accumulated, which could stop the walk before it ever
    # reached a genuine title match sitting later in walk order — silently
    # breaking the documented title > tag > content priority.
    for i in range(20):
        _write(vault_root, f"Filler{i}.md", "keyword appears in the body too")
    _write(vault_root, "ZZZ-keyword-title.md", "unrelated body text")

    results = vault_search.search_structured(
        {"vault_folders": ["*"]}, "keyword", max_results=5
    )

    assert results[0]["rel_path"] == "ZZZ-keyword-title.md"
    assert results[0]["match_type"] == "title"
