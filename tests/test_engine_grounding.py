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
