"""
Unit tests for sympose.wiki_lint_support — pure manifest-graph helpers
backing the wiki_lint skill (ADR-134).
"""

from sympose import wiki_lint_support


def _manifest(nodes, links):
    return {"nodes": nodes, "links": links}


def _node(id_, exists=True):
    return {"id": id_, "exists": exists}


def _link(source, target):
    return {"source": source, "target": target, "target_stem": target.split("/")[-1]}


class TestWikiPages:
    def test_returns_only_nodes_under_the_wiki_root(self):
        manifest = _manifest(
            [_node("Wiki/Alpha.md"), _node("Journal/2026-09-19.md")], []
        )
        pages = wiki_lint_support.wiki_pages(manifest, "Wiki")
        assert [p["id"] for p in pages] == ["Wiki/Alpha.md"]

    def test_excludes_ghost_nodes(self):
        manifest = _manifest([_node("Wiki/Ghost.md", exists=False)], [])
        assert wiki_lint_support.wiki_pages(manifest, "Wiki") == []

    def test_root_with_trailing_slash_matches_the_same_way(self):
        manifest = _manifest([_node("Wiki/Alpha.md")], [])
        pages = wiki_lint_support.wiki_pages(manifest, "Wiki/")
        assert len(pages) == 1

    def test_does_not_match_a_similarly_named_sibling_folder(self):
        """"Wiki" must not prefix-match "WikiArchive/..." — the join adds
        the separator before comparing."""
        manifest = _manifest([_node("WikiArchive/Old.md")], [])
        assert wiki_lint_support.wiki_pages(manifest, "Wiki") == []


class TestOrphanPages:
    def test_page_with_no_inbound_links_is_an_orphan(self):
        manifest = _manifest([_node("Wiki/Lonely.md")], [])
        assert wiki_lint_support.orphan_pages(manifest, "Wiki") == ["Wiki/Lonely.md"]

    def test_page_linked_from_another_wiki_page_is_not_an_orphan(self):
        # Beta -> Alpha: Alpha has an inbound link and isn't an orphan;
        # nothing points *to* Beta, so Beta legitimately still is.
        manifest = _manifest(
            [_node("Wiki/Alpha.md"), _node("Wiki/Beta.md")],
            [_link("Wiki/Beta.md", "Wiki/Alpha.md")],
        )
        assert wiki_lint_support.orphan_pages(manifest, "Wiki") == ["Wiki/Beta.md"]

    def test_page_linked_from_outside_the_wiki_root_is_not_an_orphan(self):
        manifest = _manifest(
            [_node("Wiki/Alpha.md")],
            [_link("Daily/2026-09-19.md", "Wiki/Alpha.md")],
        )
        assert wiki_lint_support.orphan_pages(manifest, "Wiki") == []

    def test_only_reports_orphans_actually_inside_the_wiki_root(self):
        manifest = _manifest(
            [_node("Wiki/Lonely.md"), _node("Journal/AlsoLonely.md")], []
        )
        assert wiki_lint_support.orphan_pages(manifest, "Wiki") == ["Wiki/Lonely.md"]
