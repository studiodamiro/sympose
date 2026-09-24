"""Tests for sympose.engine.grounding — the dedicated passage retriever
(docs/decisions/014). The broad, table-driven quality checks live in
test_grounding_eval.py; these pin down the mechanics."""

import os

import pytest

from sympose.engine import grounding
from sympose.engine.grounding_index import build_index


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path.parent / "settings.json"))
    return str(tmp_path)


def _write(vault_root: str, rel_path: str, content: str) -> None:
    full = os.path.join(vault_root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


WHOLE = {"vault_folders": ["*"]}


def test_a_short_message_finds_the_note(vault_root):
    _write(vault_root, "Typography.md", "Some notes about fonts.")

    results = grounding.ground(WHOLE, "typography")

    assert results and results[0]["rel_path"] == "Typography.md"


def test_a_sentence_shaped_message_grounds_via_its_informative_words(vault_root):
    # Live-verified regression (docs/decisions/006): a full chat question
    # essentially never appears verbatim in a note, even when its answer does.
    _write(
        vault_root,
        "VISION.md",
        "the dev machine — Apple M2, 24GB RAM — runs a quantized 9B model comfortably",
    )

    results = grounding.ground(
        WHOLE, "what dev machine specs can run gemma2 comfortably per the vision doc"
    )

    assert any(r["rel_path"] == "VISION.md" for r in results)


def test_a_hit_returns_the_passage_text_not_a_line_capped_at_70_chars(vault_root):
    body = "The Atlas decision. " + "Reasoning about storage and setup costs. " * 6
    _write(vault_root, "Atlas.md", body)

    [hit] = grounding.ground(WHOLE, "atlas decision")

    assert len(hit["text"]) > 200


def test_matching_is_on_whole_words_not_substrings(vault_root):
    _write(vault_root, "Journal.md", "Long walk today, felt good.")

    assert grounding.ground(WHOLE, "day") == []


def test_plural_is_folded_both_ways(vault_root):
    _write(vault_root, "Trip.md", "Flights booked for May.")

    assert grounding.ground(WHOLE, "which flight")
    assert grounding.ground(WHOLE, "which flights")


def test_filler_only_messages_ground_nothing(vault_root):
    _write(vault_root, "The.md", "a note literally named 'the', matching the filler word itself")

    assert grounding.ground(WHOLE, "what is this about") == []
    assert grounding.ground(WHOLE, "hey, my note in the vault please") == []


def test_a_term_in_most_notes_is_ignored_once_the_vault_is_big_enough(vault_root):
    for i in range(12):
        _write(vault_root, f"Daily{i}.md", "Today I did some things around the house.")
    _write(vault_root, "Rare.md", "The zeppelin hangar opens in spring.")

    assert grounding.ground(WHOLE, "today") == []  # in 12 of 13 notes: says nothing
    assert grounding.ground(WHOLE, "zeppelin")[0]["rel_path"] == "Rare.md"


def test_a_term_in_most_notes_still_counts_in_a_tiny_vault(vault_root):
    _write(vault_root, "One.md", "Today I did some things.")
    _write(vault_root, "Two.md", "Today was quiet.")

    assert grounding.ground(WHOLE, "today")  # 2 notes: a share means nothing yet


def test_rarer_terms_outrank_common_ones(vault_root):
    for i in range(8):
        _write(vault_root, f"Common{i}.md", "meeting notes about the schedule and planning.")
    _write(vault_root, "Rare.md", "meeting about the quokka enclosure.")

    results = grounding.ground(WHOLE, "meeting quokka")

    assert results[0]["rel_path"] == "Rare.md"


def test_a_title_hit_brings_the_notes_content(vault_root):
    _write(vault_root, "Atlas.md", "# Atlas\n\nWe chose SQLite because it needs zero setup.")

    [hit] = grounding.ground(WHOLE, "tell me about atlas")

    assert "SQLite" in hit["text"]


def test_at_most_two_passages_per_note_and_max_results_is_respected(vault_root):
    _write(vault_root, "Big.md", "\n\n".join(f"Keyword paragraph {i}." for i in range(6)))
    for i in range(6):
        _write(vault_root, f"Other{i}.md", "keyword appears here")

    results = grounding.ground(WHOLE, "keyword", max_results=4)

    assert len(results) == 4
    assert [r["rel_path"] for r in results].count("Big.md") <= 2


def test_a_weak_tail_is_cut_off_relative_to_the_best_hit(vault_root):
    _write(vault_root, "Strong.md", "quokka quokka enclosure repairs planned for spring")
    _write(vault_root, "Weak.md", "an enclosure of some other kind entirely, unrelated to animals")
    for i in range(6):
        _write(vault_root, f"Filler{i}.md", "nothing to see here at all")

    results = grounding.ground(WHOLE, "quokka enclosure")

    assert [r["rel_path"] for r in results][:1] == ["Strong.md"]


def test_results_are_numbered_from_one(vault_root):
    _write(vault_root, "Note.md", "typography and fonts both mentioned here")

    results = grounding.ground(WHOLE, "typography and fonts")

    assert [r["index"] for r in results] == list(range(1, len(results) + 1))


def test_no_match_returns_an_empty_list(vault_root):
    _write(vault_root, "Note.md", "nothing relevant here")

    assert grounding.ground(WHOLE, "completely unrelated question") == []


def test_a_rule_or_fence_marker_is_never_handed_to_the_model_as_evidence(vault_root):
    """Reviewer-reproduced: '---' and a bare fence had the top score."""
    _write(vault_root, "Priya.md", "Priya is my cousin who lives in Lisbon.\n\n---\n\n```\n```\n")
    for i in range(12):
        _write(vault_root, f"Other{i}.md", f"Unrelated note number {i} about gardening.")

    hits = grounding.ground(WHOLE, "who is Priya?")

    assert [h["text"] for h in hits] == ["Priya is my cousin who lives in Lisbon."]


def test_a_word_the_vault_lacks_makes_the_message_about_more_than_one_thing(vault_root):
    """By design: the single-informative-word rule counts words the vault
    does not contain, so an otherwise identical question with an extra
    unknown word no longer grounds on a lone body-only match. Precision over
    recall (docs/decisions/014)."""
    _write(vault_root, "Meeting.md", "# Sync\n\nOwner: Priya. Follow up Thursday.")

    assert grounding.ground(WHOLE, "who is Priya?")
    assert grounding.ground(WHOLE, "who is Priya and what does Zorblax do?") == []


def test_the_personas_folders_are_respected(vault_root):
    _write(vault_root, "Public/Open.md", "The picnic is on Saturday.")
    _write(vault_root, "Private/Secret.md", "The picnic surprise is a cake.")

    results = grounding.ground({"vault_folders": ["Public"]}, "picnic")

    assert [r["rel_path"] for r in results] == ["Public/Open.md"]


def test_the_index_is_reused_until_the_vault_changes(vault_root, monkeypatch):
    _write(vault_root, "Note.md", "The quokka enclosure.")
    builds = []
    real_build = grounding.build_index
    monkeypatch.setattr(
        grounding, "build_index", lambda notes: builds.append(1) or real_build(notes)
    )

    grounding.ground(WHOLE, "quokka")
    grounding.ground(WHOLE, "enclosure")
    assert len(builds) == 1  # second turn reused it

    _write(vault_root, "Note.md", "The quokka enclosure, now with a new roof.")
    os.utime(os.path.join(vault_root, "Note.md"), (9_999_999_999, 9_999_999_999))
    results = grounding.ground(WHOLE, "roof")

    assert len(builds) == 2 and results  # rebuilt, and sees the new text


def test_the_core_indexes_plain_note_dicts_with_no_vault(vault_root):
    """Source-agnostic: `retrieve` needs only note data, so a second source
    (e.g. reference docs) can be indexed without touching the vault."""
    index = build_index(
        [{"rel_path": "docs/Search.md", "file_name": "Search.md", "meta": {}, "body": "Search ranks passages by rarity."}]
    )

    [hit] = grounding.retrieve(index, "how does search rank")

    assert hit["rel_path"] == "docs/Search.md"


def test_no_vault_configured_returns_an_empty_list(tmp_path, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))

    assert grounding.ground(WHOLE, "anything") == []


# Strict mode: a small single-subject source written as questions and answers
# (the Sympose reference library, docs/decisions/019).


def _note(name: str, body: str) -> dict:
    return {"rel_path": f"{name}.md", "file_name": f"{name}.md", "meta": {}, "body": body}


def _strict(notes: list[dict], message: str) -> list[str]:
    return [h["rel_path"] for h in grounding.retrieve(build_index(notes), message, strict=True)]


def test_strict_keeps_a_word_most_notes_share_where_the_default_drops_it():
    notes = [_note(f"N{i}", f"## About the widget\n\nThe widget number {i} is blue.") for i in range(12)]
    notes.append(_note("Other", "## Something\n\nnothing here"))
    index = build_index(notes)

    assert grounding.retrieve(index, "widget blue") == []  # in 12 of 13 notes, so ignored
    assert len(grounding.retrieve(index, "widget blue", strict=True)) > 0


def test_strict_needs_two_words_where_a_lone_heading_word_is_enough_by_default():
    notes = [_note("Chat commands", "## What can I do about help\n\nThe help command lists commands.")]
    index = build_index(notes)

    assert grounding.retrieve(index, "thanks, that helps!")  # the default trusts a lone heading word
    assert grounding.retrieve(index, "thanks, that helps!", strict=True) == []


def test_strict_two_distinct_words_in_a_passage_qualify():
    notes = [_note("Chat commands", "## What does help do\n\nThe help command lists every command.")]

    assert _strict(notes, "what does the help command do") == ["Chat commands.md"]


def test_strict_a_message_that_is_only_a_note_name_qualifies():
    notes = [_note("Personas", "Each persona has a folder."), _note("Settings", "Kept in a file.")]

    assert _strict(notes, "tell me about personas") == ["Personas.md"]


def test_strict_a_lone_word_from_a_heading_or_the_body_does_not():
    notes = [_note("Settings", "## Where is the file\n\nIt lives next to the project.")]

    assert _strict(notes, "where is my dinner") == []  # 'where' is filler, 'dinner' absent
    assert _strict(notes, "any project ideas") == []  # a body word, one only
    assert _strict(notes, "what file") == []  # a heading word, one only


def test_strict_two_title_words_in_chat_are_one_signal_not_two():
    notes = [_note("Getting started", "# Getting started\n\nPython and a vault folder.")]  # the first line repeats the title

    assert _strict(notes, "I'm getting started on my taxes") == []
    assert _strict(notes, "getting started") == ["Getting started.md"]  # asking for it by name


def test_strict_a_title_word_plus_a_word_of_the_passage_qualifies():
    notes = [_note("Settings", "## context_window\n\nThe context_window setting is a size in tokens.")]

    assert _strict(notes, "what does the context_window setting do") == ["Settings.md"]


# -- what is not a topic (docs/decisions/021) --


def test_a_hit_says_how_many_distinct_message_words_it_matched(vault_root):
    _write(vault_root, "Wine.md", "The merlot from the cellar was better than the malbec.")

    [both] = grounding.ground(WHOLE, "merlot malbec")
    [one] = grounding.ground(WHOLE, "merlot")

    assert both["matched"] == 2 and one["matched"] == 1


def test_the_personas_name_and_a_nickname_of_it_are_searched_but_are_no_evidence(vault_root):
    _write(vault_root, "Sam.md", "Sam is my brother and lives in Porto.")
    samantha = {**WHOLE, "name": "Samantha", "handle": "samantha"}

    # Still found ("who is Sam?" is a real question) but reported as matching no
    # word that says which note is meant, so the rewrite step decides.
    for message in ("hey sam, how are you?", "who is Sam?"):
        [hit] = grounding.ground(samantha, message)
        assert hit["matched"] == 0, message
    # For a persona with another name the same word is evidence.
    [hit] = grounding.ground({**WHOLE, "name": "Grace", "handle": "grace"}, "hey sam, how are you?")
    assert hit["matched"] == 1


def test_a_topic_word_that_is_also_the_personas_role_is_still_searched(vault_root):
    _write(vault_root, "Editing.md", "How to edit a chapter: read it aloud, then cut a third.")

    [hit] = grounding.ground({**WHOLE, "name": "The Editor", "handle": "editor"}, "how do I edit a chapter")

    assert hit["rel_path"] == "Editing.md"  # found, not filtered out of the search


def test_only_a_real_prefix_of_the_name_counts_as_addressing():
    address = frozenset({"samantha"})

    assert grounding._is_addressing("sam", address)
    assert grounding._is_addressing("samantha", address)
    assert not grounding._is_addressing("sa", address)  # too short to mean anything
    assert not grounding._is_addressing("samuel", address)
    assert not grounding._is_addressing("mantha", address)  # a suffix is not a nickname


def test_contractions_typed_without_their_apostrophe_are_filler(vault_root):
    _write(vault_root, "Whats up.md", "Whats going on. Arent we late? Theres time. Im fine, dont worry.")

    assert grounding.ground(WHOLE, "whats with theres arent im dont") == []
    assert grounding.ground(WHOLE, "what's with there's aren't I'm don't") == []  # as they always were


def test_the_handle_counts_as_addressing_even_when_the_display_name_differs(vault_root):
    _write(vault_root, "Ed.md", "Ed runs the print shop on Elm Street.")

    [by_handle] = grounding.ground({**WHOLE, "name": "The Editor", "handle": "ed"}, "hey ed, how are you?")
    [by_other] = grounding.ground({**WHOLE, "name": "The Editor", "handle": "editor"}, "hey ed, how are you?")

    assert by_handle["matched"] == 0 and by_other["matched"] == 1


def test_contractions_that_are_also_words_stay_searchable(vault_root):
    _write(vault_root, "Passport.md", "The passport id is on the second page.")

    [hit] = grounding.ground(WHOLE, "where is my passport id")

    assert hit["matched"] == 2  # passport and id
