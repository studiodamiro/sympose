"""Tests for sympose.engine.grounding — the auto-triggered wrapper over
vault_search.search_structured (docs/decisions/002, docs/decisions/006)."""

import os

import pytest

from sympose.engine import grounding


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return str(tmp_path)


def _write(vault_root: str, rel_path: str, content: str) -> None:
    full = os.path.join(vault_root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def test_short_message_matches_verbatim(vault_root):
    _write(vault_root, "Typography.md", "Some notes about fonts.")

    results = grounding.ground({"vault_folders": ["*"]}, "typography")

    assert results and results[0]["rel_path"] == "Typography.md"


def test_sentence_shaped_message_still_grounds_via_significant_words(vault_root):
    # Live-verified regression (docs/decisions/006): a full chat question
    # essentially never appears verbatim in a note, even when its answer
    # does — search_structured's whole-string-substring matcher misses it
    # unless grounding also tries the message's own significant words.
    _write(
        vault_root,
        "VISION.md",
        "the dev machine — Apple M2, 24GB RAM — runs a quantized 9B model comfortably",
    )

    results = grounding.ground(
        {"vault_folders": ["*"]},
        "what dev machine specs can run gemma2 comfortably per the vision doc",
    )

    assert any(r["rel_path"] == "VISION.md" for r in results)


def test_stopwords_are_not_queried(vault_root):
    _write(vault_root, "The.md", "a note literally named 'the', matching the stopword itself")

    # "what is this about" is all stopwords/short words once "about" (a
    # stopword) and "this"/"what"/"is" are excluded — nothing should be
    # queried, so a coincidental stopword-named note must not surface.
    results = grounding.ground({"vault_folders": ["*"]}, "what is this about")

    assert results == []


def test_max_results_caps_the_merged_list(vault_root):
    for i in range(10):
        _write(vault_root, f"Keyword{i}.md", "keyword appears here")

    results = grounding.ground({"vault_folders": ["*"]}, "keyword", max_results=3)

    assert len(results) == 3


def test_duplicate_hits_across_terms_are_not_repeated(vault_root):
    _write(vault_root, "Note.md", "typography and fonts both mentioned here")

    # Both "typography" and "fonts" independently match the same note —
    # it must appear once in the merged result, not twice.
    results = grounding.ground({"vault_folders": ["*"]}, "typography and fonts")

    paths = [r["rel_path"] for r in results]
    assert paths.count("Note.md") == 1


def test_no_match_anywhere_returns_empty_list(vault_root):
    _write(vault_root, "Note.md", "nothing relevant here")

    assert grounding.ground({"vault_folders": ["*"]}, "completely unrelated question") == []


def test_results_are_reindexed_after_merge(vault_root):
    _write(vault_root, "Note.md", "typography and fonts both mentioned here")

    results = grounding.ground({"vault_folders": ["*"]}, "typography and fonts")

    assert [r["index"] for r in results] == list(range(1, len(results) + 1))
