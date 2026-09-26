"""What a cloud model may receive (docs/decisions/031): which categories a model is allowed, what the gate
holds back, and what the model is told about it. The turn, recap and embedder paths that use the gate are
tested beside those modules."""

import pytest

from sympose import settings_store
from sympose.engine import prompt, sharing

CLOUD = "anthropic/claude-sonnet-5"
NOTE = {"rel_path": "Atlas.md", "title": "Atlas", "heading": "Atlas", "text": "We use SQLite.", "kind": "text"}
PROPERTIES = {**NOTE, "rel_path": "Priya.md", "title": "Priya", "text": "email: p@example.com", "kind": "properties"}
LIBRARY = {**NOTE, "rel_path": "Sympose reference/Search.md", "title": "Search", "source": "sympose"}
RECAP = {"session": "20260923T090000-bbbbbbbb", "date": "2026-09-23", "text": "Planning a trip.", "last": True}
PERSONA = {"handle": "samantha", "name": "Samantha"}


@pytest.mark.parametrize("model", ["ollama/nomic", "ollama_chat/gemma2:9b"])
def test_a_local_model_may_receive_every_category(model):
    assert sharing.allowed(model) == {"notes", "properties", "recaps"}


def test_a_cloud_model_may_receive_nothing_until_the_user_approves():
    assert sharing.allowed(CLOUD) == frozenset()


def test_a_cloud_model_may_receive_the_approved_categories_only():
    settings_store.set("cloud_share", ["notes", "recaps"])

    assert sharing.allowed(CLOUD) == {"notes", "recaps"}
    assert sharing.allowed("ollama_chat/x") == {"notes", "properties", "recaps"}  # local: not the list's business


@pytest.mark.parametrize(
    "value, expected",
    [
        ("notes", set()),  # a string is not a list
        ({"notes": True}, set()),
        (True, set()),
        (None, set()),
        (["everything", 3, None, ["notes"]], set()),  # nothing here is a category
        (["notes", "everything", 3], {"notes"}),  # the known names count, the rest are ignored
    ],
)
def test_a_setting_of_the_wrong_shape_shares_nothing_it_did_not_name(value, expected):
    settings_store.set("cloud_share", value)

    assert sharing.allowed(CLOUD) == expected


def test_the_gate_holds_back_each_category_that_is_not_approved():
    gated = sharing.gate(CLOUD, [NOTE, PROPERTIES], [RECAP])

    assert (gated.grounding, gated.recaps) == ([], [])
    assert gated.withheld == {"notes": 1, "properties": 1, "recaps": 1}


def test_the_gate_keeps_what_is_approved_and_holds_back_the_rest():
    settings_store.set("cloud_share", ["properties"])

    gated = sharing.gate(CLOUD, [NOTE, PROPERTIES], [RECAP])

    assert gated.grounding == [PROPERTIES]
    assert gated.withheld == {"notes": 1, "recaps": 1}


def test_the_gate_never_holds_back_the_sympose_library():
    gated = sharing.gate(CLOUD, [LIBRARY, NOTE], [])

    assert gated.grounding == [LIBRARY]
    assert gated.withheld == {"notes": 1}


def test_the_gate_holds_nothing_back_from_a_local_model():
    gated = sharing.gate("ollama_chat/gemma2:9b", [NOTE, PROPERTIES, LIBRARY], [RECAP])

    assert gated.grounding == [NOTE, PROPERTIES, LIBRARY] and gated.recaps == [RECAP]
    assert gated.withheld == {}


def test_a_title_passage_is_a_note_for_the_gate():
    title_only = {**NOTE, "kind": "title", "text": ""}

    assert sharing.gate(CLOUD, [title_only], []).withheld == {"notes": 1}


def test_the_categories_a_turn_sent_are_listed_in_order():
    assert sharing.categories_of([PROPERTIES, LIBRARY, NOTE], [RECAP]) == ["notes", "properties", "recaps"]
    assert sharing.categories_of([LIBRARY], []) == []


def test_a_cloud_embedder_may_see_the_notes_only_when_approved():
    assert not sharing.embeds_notes("openai/text-embedding-3-small")
    assert sharing.embeds_notes("ollama/nomic-embed-text")
    settings_store.set("cloud_share", ["notes"])
    assert sharing.embeds_notes("openai/text-embedding-3-small")


# -- what the model is told --


def test_withheld_notes_are_said_not_to_be_an_empty_vault():
    turn = prompt.build_user_turn("what did we pick?", [], withheld={"notes": 2})

    assert prompt.WITHHELD_NOTES in turn
    assert prompt.NO_NOTES not in turn
    assert "/share" in turn


def test_nothing_withheld_leaves_the_notes_block_as_it_was():
    turn = prompt.build_user_turn("what did we pick?", [], withheld={})

    assert prompt.NO_NOTES in turn and prompt.WITHHELD_NOTES not in turn


def test_withheld_properties_are_said_beside_the_notes_that_were_sent():
    turn = prompt.build_user_turn("who is Priya?", [NOTE], withheld={"properties": 1})

    assert "We use SQLite." in turn
    assert prompt.WITHHELD_PROPERTIES in turn and prompt.WITHHELD_NOTES not in turn


def test_withheld_properties_alone_still_do_not_read_as_no_match():
    turn = prompt.build_user_turn("who is Priya?", [], withheld={"properties": 1})

    assert prompt.WITHHELD_PROPERTIES in turn and prompt.NO_NOTES not in turn


def test_withheld_recaps_are_said_in_the_system_prompt():
    messages = prompt.build_messages(PERSONA, [], [], "where did we leave off?", withheld={"recaps": 2})

    assert prompt.WITHHELD_RECAPS in messages[0]["content"]
    assert prompt.WITHHELD_RECAPS not in messages[-1]["content"]


def test_no_recaps_at_all_add_nothing_to_the_system_prompt():
    system = prompt.build_system_prompt(PERSONA)

    assert prompt.WITHHELD_RECAPS not in system


# -- changing what is approved --


def test_approving_a_category_keeps_the_others_and_the_order_of_the_categories():
    assert sharing.set_approved("recaps", True)
    assert sharing.set_approved("notes", True)

    assert settings_store.get("cloud_share") == ["notes", "recaps"]


def test_stopping_a_category_removes_only_that_one():
    settings_store.set("cloud_share", ["notes", "properties", "recaps"])

    assert sharing.set_approved("properties", False)

    assert settings_store.get("cloud_share") == ["notes", "recaps"]


def test_approving_twice_or_stopping_what_was_never_approved_changes_nothing():
    sharing.set_approved("notes", True)
    sharing.set_approved("notes", True)
    sharing.set_approved("recaps", False)

    assert settings_store.get("cloud_share") == ["notes"]


def test_saving_drops_names_that_are_not_categories():
    settings_store.set("cloud_share", ["notes", "everything"])

    sharing.set_approved("recaps", True)

    assert settings_store.get("cloud_share") == ["notes", "recaps"]


def test_an_unknown_category_is_refused_and_nothing_is_written():
    with pytest.raises(ValueError):
        sharing.set_approved("vault", True)

    assert settings_store.get("cloud_share") is None


def test_a_settings_file_that_cannot_be_written_says_so(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x")
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(blocker / "settings.json"))

    assert sharing.set_approved("notes", True) is False


def test_every_category_has_a_description_for_the_question_asked_of_the_user():
    assert set(sharing.DESCRIPTIONS) == set(sharing.CATEGORIES)
