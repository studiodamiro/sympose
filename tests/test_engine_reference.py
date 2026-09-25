"""Tests for sympose.engine.reference (docs/decisions/022): the Sympose reference
library in a persona's turns. What the notes answer is measured in
test_reference_eval.py; these pin down who gets them and how they are labelled."""

import os

import pytest

from sympose.engine import reference

HAS = {"sympose_reference": True}


def test_a_persona_without_the_library_gets_nothing():
    assert reference.ground({}, "how do I add a second vault?") == []
    assert reference.ground({"sympose_reference": False}, "how do I add a second vault?") == []


def test_a_persona_with_it_gets_labelled_passages_marked_as_sympose():
    hits = reference.ground(HAS, "how do I add a second vault?")

    assert hits and all(h["source"] == "sympose" for h in hits)
    assert all(h["rel_path"].startswith("Sympose reference/") for h in hits)
    assert hits[0]["rel_path"] == "Sympose reference/Add or switch vaults.md"
    assert "workspace switcher" in hits[0]["text"]


def test_at_most_three_passages_are_returned():
    assert len(reference.ground(HAS, "what does the context_window setting do?")) <= 3


def test_ordinary_chat_finds_nothing_in_the_library():
    assert reference.ground(HAS, "hey, how are you today?") == []
    assert reference.ground(HAS, "thanks, that helps!") == []


def test_missing_notes_are_no_hits_and_not_a_failed_turn(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(reference, "REFERENCE_DIR", str(tmp_path / "nowhere"))

    assert reference.ground(HAS, "how do I add a second vault?") == []
    assert "missing from this install" in caplog.text


def test_the_index_is_reused_until_a_note_changes(monkeypatch, tmp_path):
    (tmp_path / "Personas.md").write_text("# Personas\n\n## What is a persona\n\nA persona is a character you chat with.")
    monkeypatch.setattr(reference, "REFERENCE_DIR", str(tmp_path))
    monkeypatch.setattr(reference, "_CACHE", None)
    built = []
    real = reference.build_index
    monkeypatch.setattr(reference, "build_index", lambda snap: built.append(1) or real(snap))

    reference.ground(HAS, "what is a persona")
    reference.ground(HAS, "what is a persona")
    assert len(built) == 1
    (tmp_path / "Extra.md").write_text("# Extra\n\nAnother note.")
    os.utime(tmp_path, (1, 1_000_000_000))  # the directory's own mtime is what the cache watches
    reference.ground(HAS, "what is a persona")
    assert len(built) == 2


def test_the_shipped_notes_are_in_the_package_data_glob():
    import tomllib

    with open(os.path.join(reference.REFERENCE_DIR, "..", "..", "pyproject.toml"), "rb") as f:
        config = tomllib.load(f)
    assert "reference/*.md" in config["tool"]["setuptools"]["package-data"]["sympose"]  # the web app is there too (ADR 028)
    assert all(n.endswith(".md") for n in os.listdir(reference.REFERENCE_DIR))


def test_the_shipped_samantha_has_the_library_and_says_so_explicitly():
    import yaml

    with open(os.path.join(reference.REFERENCE_DIR, "..", "..", "profiles", "samantha", "persona.yaml")) as f:
        assert yaml.safe_load(f)["sympose_reference"] is True


@pytest.mark.parametrize("message", ["who made Sympose?", "does Sympose work in Slack?", "can Samantha write my notes?"])
def test_the_questions_the_library_is_for_find_something(message):
    assert reference.ground(HAS, message)


def test_a_broad_question_still_returns_at_most_three_passages():
    # Uncapped, this question matches nine.
    assert len(reference.ground(HAS, "which settings go in settings.json and which in .env")) == 3
