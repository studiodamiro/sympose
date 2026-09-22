"""Tests for sympose.engine.session — the JSONL per-conversation log
(docs/decisions/006)."""

import json
import os

import pytest

from sympose.engine import session


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SESSIONS_DIR", str(tmp_path))
    return str(tmp_path)


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
