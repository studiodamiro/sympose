"""Tests for sympose.engine.grounding_index — passage splitting, term
folding, and index building (docs/decisions/014)."""


from sympose.engine import grounding_index as gi


def test_split_passages_tracks_the_nearest_heading():
    body = "Intro text.\n\n## Timeline\n\nReview in October.\n\nLaunch in November.\n\n## Notes\n\nA closing line."

    assert gi.split_passages(body) == [
        ("", "Intro text."),
        ("Timeline", "Review in October."),
        ("Timeline", "Launch in November."),
        ("Notes", "A closing line."),
    ]


def test_consecutive_lines_form_one_passage_and_whitespace_is_normalized():
    assert gi.split_passages("- one\n- two\n-   three") == [("", "- one - two - three")]


def test_a_long_paragraph_is_cut_at_sentence_ends_within_the_limit():
    sentence = "This is a fairly ordinary sentence about nothing much. "
    passages = gi.split_passages(sentence * 20)

    assert len(passages) > 1
    assert all(len(text) <= gi.MAX_PASSAGE_CHARS for _, text in passages)
    assert all(text.endswith(".") for _, text in passages)


def test_a_single_endless_sentence_is_cut_at_a_word_boundary():
    passages = gi.split_passages("word " * 300)

    assert all(len(text) <= gi.MAX_PASSAGE_CHARS for _, text in passages)
    assert all(not text.endswith("wor") for _, text in passages)  # never mid-word


def test_a_long_unbroken_token_is_hard_cut_without_losing_text():
    """`str.rfind` returns -1 (truthy) when there is no space, which once
    made the cut point wrong for a long URL or similar."""
    token = "x" * (gi.MAX_PASSAGE_CHARS * 2 + 50)

    passages = gi.split_passages(f"see {token}")

    assert all(len(text) <= gi.MAX_PASSAGE_CHARS for _, text in passages)
    assert "".join(text.replace(" ", "") for _, text in passages) == "see" + token


def test_a_fenced_code_block_is_one_passage_and_its_comments_are_not_headings():
    body = "Setup notes.\n\n```bash\n# Install the package\npip install foo\n\npip install bar\n```\n\nAfter that, restart."

    assert gi.split_passages(body) == [
        ("", "Setup notes."),
        ("", "# Install the package pip install foo pip install bar"),
        ("", "After that, restart."),
    ]


def test_a_block_fenced_with_tildes_is_one_passage_too():
    body = "Setup notes.\n\n~~~bash\n# Install the package\npip install foo\n\npip install bar\n~~~\n\nAfter that, restart."

    assert gi.split_passages(body) == [
        ("", "Setup notes."),
        ("", "# Install the package pip install foo pip install bar"),
        ("", "After that, restart."),
    ]


def test_a_line_of_inline_code_that_starts_with_backticks_does_not_open_a_fence():
    body = "# A\n\n```py x```\n\n## Real Heading\n\nAfter one.\n\nAfter two."

    assert gi.split_passages(body) == [
        ("A", "```py x```"),
        ("Real Heading", "After one."),
        ("Real Heading", "After two."),
    ]


def test_index_terms_drop_filler_and_fold_plurals():
    assert gi.index_terms("What are the Flights, notes and vault?") == ["flight"]
    assert gi.index_terms("The boss has a class") == ["boss", "class"]  # 'ss' is not a plural


def test_a_title_or_tag_term_outweighs_a_body_term():
    [passage] = gi.build_index(
        [
            {
                "rel_path": "A.md",
                "file_name": "Atlas.md",
                "meta": {"tags": ["launch"]},
                "body": "Some plain body text mentioning atlas once.",
            }
        ]
    ).passages

    assert passage.tf["atla"] == 1 + 3  # body once, plus the title weight
    assert passage.tf["launch"] == 3  # tag only


def test_a_frontmatter_title_is_indexed_alongside_the_filename():
    [passage] = gi.build_index(
        [{"rel_path": "F.md", "file_name": "Fitness Plan.md", "meta": {"title": "Training Plan"}, "body": "Run often."}]
    ).passages

    assert passage.title == "Training Plan"
    assert passage.tf["training"] and passage.tf["fitness"] and passage.tf["plan"]


def test_a_note_with_no_body_text_yields_no_passages():
    index = gi.build_index([{"rel_path": "E.md", "file_name": "E.md", "meta": {}, "body": "\n\n"}])

    assert index.passages == [] and index.note_count == 0


def test_note_df_counts_notes_not_passages():
    index = gi.build_index(
        [{"rel_path": "A.md", "file_name": "A.md", "meta": {}, "body": "quokka one.\n\nquokka two.\n\nquokka three."}]
    )

    assert index.note_df["quokka"] == 1 and index.note_count == 1


def test_passages_with_no_real_words_are_not_indexed():
    """A `---` rule or stray marker has zero body terms; with a title boost
    and a near-zero length it would otherwise outscore the real paragraph."""
    index = gi.build_index(
        [{"rel_path": "P.md", "file_name": "Priya.md", "meta": {}, "body": "Priya is my cousin.\n\n---\n\n***\n\nIt is what it is."}]
    )

    assert [p.text for p in index.passages] == ["Priya is my cousin."]
