"""Tests for sympose.engine.grounding_index — passage splitting, term
folding, and index building (docs/decisions/014)."""


import pytest

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


def _note(name, body="", **meta):
    return {"rel_path": f"{name}.md", "file_name": f"{name}.md", "meta": meta, "body": body}


# -- a note with no body text is still a note (docs/decisions/030) ---------------------------


def test_a_note_with_no_body_text_is_indexed_as_a_title_passage():
    index = gi.build_index([_note("Anna Ruiz", "\n\n")])

    [passage] = index.passages
    assert (passage.kind, passage.title, passage.heading, passage.text) == ("title", "Anna Ruiz", "", "")
    assert passage.tf["anna"] == 3 and passage.tf["ruiz"] == 3  # the title weight, as on any passage of the note
    assert index.note_count == 1 and index.note_df["anna"] == 1


def test_a_note_with_a_body_gets_no_title_passage():
    index = gi.build_index([_note("Anna Ruiz", "Met at the conference.")])

    assert [p.kind for p in index.passages] == ["text"]


def test_a_body_of_only_rules_and_markers_is_a_note_with_no_body_text():
    index = gi.build_index([_note("Anna Ruiz", "---\n\n***\n\n```\n```")])

    assert [p.kind for p in index.passages] == ["title"]


def test_a_body_of_only_filler_words_is_text_and_is_shown_as_it_is_not_as_an_empty_note():
    """"Yes, ok, thanks" has nothing to search for, but it is not empty, and calling the note empty
    would tell the model something false about the vault."""
    passages = gi.build_index([_note("Reply", "Yes, ok, thanks.\n\n---\n\nI am on it")]).passages

    assert [(p.kind, p.text) for p in passages] == [("text", "Yes, ok, thanks."), ("text", "I am on it")]
    assert all(p.tf["reply"] == 3 and p.length == 1 and p.title == "Reply" for p in passages)


def test_filler_only_paragraphs_are_still_dropped_when_the_note_has_real_text_too():
    index = gi.build_index([_note("Reply", "Yes, ok, thanks.\n\nThe quarterly forecast changed.")])

    assert [p.text for p in index.passages] == ["The quarterly forecast changed."]


def test_a_note_of_only_filler_words_with_a_title_of_only_filler_words_has_nothing_to_be_found_by():
    assert gi.build_index([_note("The", "Yes, ok, thanks.")]).passages == []


def test_a_title_made_only_of_filler_words_still_gets_its_outline_indexed():
    [passage] = gi.build_index([_note("Notes", "# Flights\n\n## Hotels\n")]).passages

    assert passage.kind == "title" and passage.heading == "Flights, Hotels" and passage.tf["flight"] == 2


def test_the_headings_of_an_outline_leave_out_code_in_a_fence_and_lines_with_no_words():
    [passage] = gi.build_index([_note("Outline", "# Plan\n\n```\n# ---\n```\n\n## ---\n")]).passages

    assert passage.kind == "title" and passage.heading == "Plan"


def test_a_title_with_no_real_words_gives_a_note_nothing_to_be_found_by():
    index = gi.build_index([_note("E"), _note("The")])

    assert index.passages == [] and index.note_count == 0


def test_the_title_of_a_note_comes_from_its_title_property_before_its_file_name():
    [passage] = gi.build_index([_note("2026-09-25", title="Quote of the Day")]).passages

    assert passage.title == "Quote of the Day" and passage.tf["quote"] == 3 and passage.tf["2026"] == 3


def test_aliases_are_the_text_of_a_title_passage_and_count_as_its_title():
    [passage] = gi.build_index([_note("Anna Ruiz", aliases=["Annie", "A. Ruiz"])]).passages

    assert passage.text == "Annie, A. Ruiz"
    assert passage.tf["annie"] == 3 and passage.tf["ruiz"] == 3
    assert frozenset({"annie"}) in passage.labels and frozenset({"anna", "ruiz"}) in passage.labels
    assert {"annie", "ruiz", "anna"} <= passage.title_terms


def test_aliases_count_as_the_title_of_every_passage_of_a_note_with_a_body():
    [passage] = gi.build_index([_note("Anna Ruiz", "Met at the conference.", aliases="Annie")]).passages

    assert passage.kind == "text" and passage.text == "Met at the conference."
    assert passage.tf["annie"] == 3 and frozenset({"annie"}) in passage.labels and "annie" in passage.title_terms


@pytest.mark.parametrize(
    "meta, aliases",
    [
        ({"aliases": "Annie"}, "Annie"),
        ({"alias": ["Annie", "Ann"]}, "Annie, Ann"),  # the older spelling of the property
        ({"aliases": ["Annie", 5, None, "  ", ["nested"]]}, "Annie"),  # only text counts
        ({"aliases": 5}, ""),
        ({"aliases": None}, ""),
        ({"aliases": "Annie, Ann"}, "Annie, Ann"),  # a comma-separated string is two names
        ({"aliases": [], "alias": "Annie"}, "Annie"),  # an empty list does not hide the older spelling
        ({"aliases": ["Annie"], "alias": ["Ann", "annie"]}, "Annie, Ann"),  # both are read, once each
    ],
)
def test_aliases_are_read_as_text_from_either_spelling_and_anything_else_is_ignored(meta, aliases):
    [passage] = gi.build_index([_note("Anna Ruiz", **meta)]).passages

    assert passage.text == aliases
    if "," in aliases:  # each name is a label of its own: naming one of them is naming the note
        assert frozenset({"annie"}) in passage.labels


def test_an_outline_with_no_text_under_its_headings_is_a_title_passage_that_carries_the_headings():
    body = "# Packing\n\n## Clothes\n\n## Chargers and adapters\n\n### Documents\n"
    [passage] = gi.build_index([_note("Packing Outline", body)]).passages

    assert passage.kind == "title" and passage.text == ""
    assert passage.heading == "Packing, Clothes, Chargers and adapters, Documents"
    assert passage.tf["charger"] == 2 and passage.tf["adapter"] == 2 and passage.tf["outline"] == 3  # heading weight, title weight
    assert frozenset({"charger", "adapter"}) in passage.labels and frozenset({"clothe"}) in passage.labels


def test_a_heading_line_with_no_words_is_not_a_heading_of_the_outline():
    [passage] = gi.build_index([_note("Outline", "##\n\n## Clothes\n\n#  \n")]).passages

    assert passage.heading == "Clothes"


def test_the_headings_of_a_long_outline_are_cut_to_a_passage_size():
    body = "\n".join(f"## Heading number {n} of the outline" for n in range(200))
    [passage] = gi.build_index([_note("Long Outline", body)]).passages

    assert len(passage.heading) <= gi.MAX_PASSAGE_CHARS


def test_a_note_with_text_under_its_headings_gets_no_headings_passage():
    index = gi.build_index([_note("Packing", "## Clothes\n\nTwo shirts and a jacket.")])

    assert [(p.kind, p.heading) for p in index.passages] == [("text", "Clothes")]


def test_a_passage_says_what_kind_it_is():
    assert [p.kind for p in gi.build_index([_note("Anna Ruiz", "Some text here.")]).passages] == ["text"]


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
