"""Tests for sympose.engine.session — the JSONL per-conversation log
(docs/decisions/006)."""

import json
import os

import pytest
from helpers import write_persona

from sympose.engine import session


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    """A profiles dir with a `samantha` persona; sessions land in
    `<root>/<handle>/sessions/` (docs/decisions/011). Returns the root."""
    base = tmp_path / "profiles"
    write_persona(base, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return str(base)


def test_no_file_until_first_append_turn(sessions_root):
    sid = session.new_session_id()
    assert session.load_session("samantha", sid) is None
    assert not os.path.exists(session.session_path("samantha", sid))

    session.append_turn("samantha", sid, "hi", "hello there")

    assert os.path.exists(session.session_path("samantha", sid))
    assert session.load_session("samantha", sid) is not None


def test_meta_and_turn_shape_on_disk(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "what is my name", "your name is not in the vault yet")

    path = session.session_path("samantha", sid)
    with open(path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    assert lines[0]["type"] == "meta"
    assert lines[0]["session_id"] == sid
    assert lines[0]["handle"] == "samantha"
    assert lines[0]["turns_count"] == 1
    assert lines[0]["title"].startswith("what is my name")
    assert lines[1]["type"] == "turn"
    assert lines[1]["user"] == "what is my name"
    assert lines[1]["assistant"] == "your name is not in the vault yet"


def test_round_trip_via_load_session_and_history_as_messages(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "first", "first reply")
    session.append_turn("samantha", sid, "second", "second reply")

    loaded = session.load_session("samantha", sid)
    assert loaded["meta"]["turns_count"] == 2

    messages = session.history_as_messages(loaded)
    assert messages == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "first reply"},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "second reply"},
    ]


def test_history_as_messages_respects_max_turns(sessions_root):
    sid = session.new_session_id()
    for i in range(5):
        session.append_turn("samantha", sid, f"msg{i}", f"reply{i}")

    messages = session.history_as_messages(session.load_session("samantha", sid), max_turns=2)

    assert len(messages) == 4  # last 2 turns, 2 messages each
    assert messages[0]["content"] == "msg3"
    assert messages[-1]["content"] == "reply4"


def test_history_as_messages_max_turns_zero_returns_empty(sessions_root):
    """Regression test: Python's `turns[-0:]` is `turns[0:]` (the whole
    list), not an empty slice, since `-0 == 0` — `max_turns=0` used to
    silently return the *entire* history instead of none."""
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "hi", "hello")

    messages = session.history_as_messages(session.load_session("samantha", sid), max_turns=0)

    assert messages == []


def test_load_session_skips_a_malformed_non_dict_line(sessions_root):
    """Regression test: a line that parses as valid JSON but isn't a dict
    (e.g. `[1,2,3]` or `null`, plausible from a crash mid-write truncating
    a line) used to raise an uncaught AttributeError from `.get(...)`
    instead of degrading gracefully."""
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "hi", "hello")

    path = session.session_path("samantha", sid)
    with open(path, "a", encoding="utf-8") as f:
        f.write("[1, 2, 3]\n")

    loaded = session.load_session("samantha", sid)

    assert loaded is not None
    assert len(loaded["turns"]) == 1  # the malformed line was skipped, not crashed on


def test_load_session_skips_one_truncated_line_and_keeps_the_rest(sessions_root):
    """Regression test: a genuinely malformed line (not valid JSON at all —
    e.g. a write truncated mid-line, plausible if the process were killed
    mid-`append_turn`) used to fail the whole read via the function-level
    except, discarding every prior valid turn along with the bad line."""
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "first", "first reply")
    session.append_turn("samantha", sid, "second", "second reply")

    path = session.session_path("samantha", sid)
    with open(path, "a", encoding="utf-8") as f:
        f.write('{"type": "turn", "timestamp": "x", "user": "trunc\n')  # not valid JSON

    loaded = session.load_session("samantha", sid)

    assert loaded is not None
    assert len(loaded["turns"]) == 2  # both prior valid turns survive


def test_history_as_messages_handles_none_session():
    assert session.history_as_messages(None) == []


def test_corrupt_file_returns_none(sessions_root):
    sid = session.new_session_id()
    path = session.session_path("samantha", sid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not valid json\n")

    assert session.load_session("samantha", sid) is None


def test_title_truncates_long_opening_messages(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "one two three four five six seven eight", "reply")

    loaded = session.load_session("samantha", sid)
    assert loaded["meta"]["title"] == "one two three four five six..."


# -- where sessions live (docs/decisions/011) --


def test_sessions_are_written_inside_the_persona_directory(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "hi", "hello")

    expected = os.path.join(sessions_root, "samantha", "sessions", f"{sid}.jsonl")
    assert session.session_path("samantha", sid) == expected
    assert os.path.exists(expected)


def test_writing_a_session_does_not_make_a_persona_out_of_a_bare_directory(sessions_root):
    """A session for a handle with no `persona.yaml` (the factory-default
    safety net can produce one) creates `<handle>/sessions/` but must not
    make that handle appear in the roster."""
    from sympose import profile

    session.append_turn("ghost", session.new_session_id(), "hi", "hello")

    assert "ghost" not in [p["handle"] for p in profile.list_profiles()]


def test_fallback_mode_keeps_sessions_out_of_profiles(tmp_path, monkeypatch):
    """With no profiles/ dir at all, writing a session under profiles/
    would create it and flip the system out of fallback mode."""
    from sympose import profile

    missing = tmp_path / "profiles"
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(missing))
    monkeypatch.chdir(tmp_path)
    sid = session.new_session_id()

    session.append_turn("samantha", sid, "hi", "hello")

    assert os.path.exists(tmp_path / "sessions" / "samantha" / f"{sid}.jsonl")
    assert not missing.exists()
    assert profile.get_profile("samantha")["vault_folders"] == ["*"]  # still fallback


def test_a_traversal_handle_is_rejected(sessions_root):
    with pytest.raises(ValueError):
        session.session_path("../outside", "sid")


def test_a_traversal_session_id_cannot_reach_another_personas_files(sessions_root):
    with pytest.raises(ValueError):
        session.session_path("samantha", "../../dev/sessions/other")


@pytest.mark.parametrize("handle", [".", "a/b", ""])
def test_a_handle_that_is_not_a_plain_component_is_rejected_in_both_modes(
    sessions_root, tmp_path, monkeypatch, handle
):
    with pytest.raises(ValueError):
        session.session_path(handle, "sid")

    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "no-such-dir"))  # fallback mode
    with pytest.raises(ValueError):
        session.session_path(handle, "sid")


# -- where recaps live, and listing sessions (docs/decisions/023) --


def test_recaps_live_beside_the_sessions_of_the_same_persona(sessions_root):
    assert session.recaps_dir("samantha") == os.path.join(sessions_root, "samantha", "recaps")
    assert os.path.dirname(session.recaps_dir("samantha")) == os.path.dirname(session.sessions_dir("samantha"))
    assert session.recaps_dir("Samantha") == session.recaps_dir("samantha")


def test_recaps_dir_rejects_a_handle_that_is_not_one_plain_name(sessions_root):
    for bad in ("..", "a/b", ""):
        with pytest.raises(ValueError):
            session.recaps_dir(bad)


def test_in_the_whole_vault_fallback_mode_recaps_stay_out_of_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "no-such-dir"))
    monkeypatch.chdir(tmp_path)

    assert session.recaps_dir("samantha") == os.path.join(str(tmp_path), "recaps", "samantha")


def test_session_ids_are_listed_newest_first_and_only_the_session_files(sessions_root):
    for sid in ("20260921T090000-aaaaaaaa", "20260924T090000-bbbbbbbb", "20260923T090000-cccccccc"):
        session.append_turn("samantha", sid, "hi", "hello")
    open(os.path.join(session.sessions_dir("samantha"), "notes.txt"), "w").close()

    assert session.session_ids("samantha") == [
        "20260924T090000-bbbbbbbb",
        "20260923T090000-cccccccc",
        "20260921T090000-aaaaaaaa",
    ]


def test_a_persona_with_no_sessions_yet_lists_none(sessions_root):
    assert session.session_ids("samantha") == []


def test_what_reached_the_model_is_kept_on_the_turn_and_left_off_when_not_given(sessions_root):
    sid = session.new_session_id()
    sent = {"notes": [{"path": "A.md", "heading": "H", "source": "vault"}], "recaps": [], "searched": None}

    session.append_turn("samantha", sid, "one", "reply", sent=sent)
    session.append_turn("samantha", sid, "two", "reply")

    first, second = session.load_session("samantha", sid)["turns"]
    assert first["sent"] == sent
    assert "sent" not in second  # nothing recorded is not an empty record


def test_what_was_sent_is_not_part_of_the_history_the_model_gets(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "one", "reply", sent={"notes": [{"path": "Secret.md"}]})

    history = session.history_as_messages(session.load_session("samantha", sid))

    assert history == [{"role": "user", "content": "one"}, {"role": "assistant", "content": "reply"}]


def test_a_padded_saved_reply_is_sent_back_tidy_but_the_file_keeps_what_was_saved(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "hi", "Hey!  How are you?\n\n\n")

    loaded = session.load_session("samantha", sid)

    assert session.history_as_messages(loaded)[1] == {"role": "assistant", "content": "Hey! How are you?"}
    assert loaded["turns"][0]["assistant"] == "Hey!  How are you?\n\n\n"


def test_a_reply_cut_at_the_length_limit_is_marked_on_the_record_and_flagged_in_the_history(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "list some names", "Ada, Grace and", truncated=True)

    loaded = session.load_session("samantha", sid)
    history = session.history_as_messages(loaded)

    assert loaded["turns"][0]["truncated"] is True
    assert loaded["turns"][0]["assistant"] == "Ada, Grace and"  # the file keeps what was said
    assert history[1]["content"] == "Ada, Grace and\n\n[This reply was cut off at the length limit.]"


def test_a_reply_that_finished_carries_no_mark(sessions_root):
    sid = session.new_session_id()
    session.append_turn("samantha", sid, "hi", "Hello!")

    loaded = session.load_session("samantha", sid)

    assert "truncated" not in loaded["turns"][0]  # as for a record written before the key existed
    assert session.history_as_messages(loaded)[1]["content"] == "Hello!"


# -- found in the review of the engine (wave D of the cleanup) --------------------------------


def _two_turns(handle="samantha"):
    sid = session.new_session_id()
    session.append_turn(handle, sid, "first question", "first answer")
    session.append_turn(handle, sid, "second question", "second answer")
    return sid, session.session_path(handle, sid)


@pytest.mark.xfail(
    strict=True,
    reason="a session whose first (meta) line is damaged loads as no session, and the next message "
    "rewrites the file from scratch, destroying every turn that was still valid",
)
def test_a_damaged_first_line_does_not_cost_the_turns_after_it(sessions_root):
    sid, path = _two_turns()
    lines = open(path, encoding="utf-8").read().splitlines()
    with open(path, "w", encoding="utf-8") as f:
        f.write(lines[0][:20] + "\n" + "\n".join(lines[1:]) + "\n")

    session.append_turn("samantha", sid, "third question", "third answer", existing=session.load_session("samantha", sid))

    kept = [json.loads(line) for line in open(path, encoding="utf-8").read().splitlines()]
    assert [t["user"] for t in kept if t["type"] == "turn"] == ["first question", "second question", "third question"]


@pytest.mark.xfail(
    strict=True,
    reason="a turn record without a `user` or `assistant` text raises KeyError for every later message "
    "of that session, so it can never be resumed",
)
def test_a_turn_record_without_its_text_does_not_break_the_history(sessions_root):
    sid, path = _two_turns()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "turn", "assistant": "an answer with no question"}) + "\n")

    messages = session.history_as_messages(session.load_session("samantha", sid))

    assert [m["content"] for m in messages][:2] == ["first question", "first answer"]


@pytest.mark.xfail(
    strict=True,
    reason="the log is rewritten in place: the file is emptied first, so a failure part-way through "
    "(a full disk, a killed process) loses the whole conversation; recaps are written through a temporary file",
)
def test_a_write_that_fails_part_way_leaves_the_earlier_turns_on_disk(sessions_root, monkeypatch):
    sid, path = _two_turns()
    real_dumps, calls = json.dumps, []

    def fails_on_the_third_line(obj, *args, **kwargs):
        calls.append(1)
        if len(calls) == 3:
            raise OSError("no space left on device")
        return real_dumps(obj, *args, **kwargs)

    monkeypatch.setattr(session.json, "dumps", fails_on_the_third_line)
    session.append_turn("samantha", sid, "third question", "third answer")
    monkeypatch.undo()

    survivor = session.load_session("samantha", sid)
    assert survivor is not None
    assert [t["user"] for t in survivor["turns"]] == ["first question", "second question"]
