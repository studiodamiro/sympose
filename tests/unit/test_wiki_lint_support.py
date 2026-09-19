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


class TestWikiLintWriteGate:
    """ADR-134's structural gap, revisited: a code-level backstop for a
    lint-only persona (wiki_lint without wiki_ingest) with lint_auto_fix
    off, so the write block doesn't depend solely on the model obeying its
    own prompt-level `Wiki Lint Mode` instruction."""

    def _gate(self, **overrides):
        kwargs = {
            "skills": ["wiki_lint"],
            "lint_auto_fix": False,
            "wiki_root": "Wiki",
            "log_file": "log.md",
            "rel_path": "Wiki/Some Page.md",
        }
        kwargs.update(overrides)
        return wiki_lint_support.wiki_lint_write_gate(**kwargs)

    def test_blocks_a_lint_only_persona_editing_a_wiki_page_with_auto_fix_off(self):
        assert self._gate() is not None

    def test_allows_the_same_write_once_lint_auto_fix_is_on(self):
        assert self._gate(lint_auto_fix=True) is None

    def test_allows_a_persona_that_also_carries_wiki_ingest(self):
        """Ambiguous by design (ADR-134): wiki_ingest's own legitimate
        writes into wiki.root can't be told apart from a lint fix here."""
        assert self._gate(skills=["wiki_lint", "wiki_ingest"]) is None

    def test_ignores_skill_name_casing(self):
        assert self._gate(skills=["Wiki_Lint"]) is not None

    def test_always_allows_appending_to_the_log_file(self):
        assert self._gate(rel_path="Wiki/log.md") is None

    def test_allows_writes_outside_the_wiki_root(self):
        assert self._gate(rel_path="Journal/2026-09-19.md") is None

    def test_does_not_prefix_match_a_similarly_named_sibling_folder(self):
        assert self._gate(rel_path="WikiArchive/Old.md") is None

    def test_no_op_when_wiki_root_is_unset(self):
        assert self._gate(wiki_root="") is None

    def test_no_op_for_a_persona_without_the_wiki_lint_skill(self):
        assert self._gate(skills=["vault_write"]) is None

    def test_denial_message_names_the_path_and_the_log_file(self):
        message = self._gate()
        assert "Wiki/Some Page.md" in message
        assert "log.md" in message
