"""
Unit tests for sympose.sessions.SessionManager
Covers: create_session, append_turn, update_session_title, load_session,
        list_sessions, delete_session, prune_ghost_sessions, derive_title,
        is_generic_prompt, format_relative_time.
"""

import os
import json
import datetime
import pytest
from unittest.mock import patch

from sympose.sessions import SessionManager


# ---------------------------------------------------------------------------
# Helpers — redirect sessions dir to a tmp dir for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_sessions_dir(tmp_sessions_dir, monkeypatch):
    """Redirect SessionManager to use a fresh tmp dir for every test."""
    monkeypatch.setattr(
        "sympose.sessions.resolve_workspace_dir",
        lambda: str(tmp_sessions_dir.parent),
    )
    # Ensure the sessions dir exists inside that workspace dir
    (tmp_sessions_dir.parent / "sessions").mkdir(exist_ok=True)
    return tmp_sessions_dir


# ---------------------------------------------------------------------------
# derive_title
# ---------------------------------------------------------------------------

class TestDeriveTitle:
    def test_short_title_returned_verbatim(self):
        assert SessionManager.derive_title("Hello world") == "Hello world"

    def test_long_title_truncated_at_word_boundary(self):
        long = "a " * 40  # 80 chars
        result = SessionManager.derive_title(long)
        assert len(result) <= 68
        assert result.endswith("...")

    def test_trailing_punctuation_stripped(self):
        result = SessionManager.derive_title("Fix the bug:")
        assert not result.endswith(":")

    def test_empty_input_returns_untitled(self):
        assert SessionManager.derive_title("") == "Untitled Session"

    def test_only_first_line_used(self):
        result = SessionManager.derive_title("Line one\nLine two")
        assert result == "Line one"


# ---------------------------------------------------------------------------
# is_generic_prompt
# ---------------------------------------------------------------------------

class TestIsGenericPrompt:
    def test_hi_is_generic(self):
        assert SessionManager.is_generic_prompt("hi") is True

    def test_hello_is_generic(self):
        assert SessionManager.is_generic_prompt("Hello!") is True

    def test_substantive_prompt_not_generic(self):
        assert SessionManager.is_generic_prompt("Write me a Python web scraper") is False

    def test_very_short_prompt_is_generic(self):
        assert SessionManager.is_generic_prompt("ok") is True

    def test_good_morning_is_generic(self):
        assert SessionManager.is_generic_prompt("Good morning!") is True


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_creates_jsonl_file(self):
        meta = SessionManager.create_session("samantha")
        sid = meta["session_id"]
        fpath = os.path.join(SessionManager.get_sessions_dir(), f"{sid}.jsonl")
        assert os.path.exists(fpath)

    def test_meta_has_correct_handle(self):
        meta = SessionManager.create_session("arch")
        assert meta["handle"] == "arch"

    def test_meta_type_is_meta(self):
        meta = SessionManager.create_session("samantha")
        assert meta["type"] == "meta"

    def test_custom_title_stored(self):
        meta = SessionManager.create_session("samantha", title="My Custom Session")
        assert meta["title"] == "My Custom Session"

    def test_default_title_is_new_conversation(self):
        meta = SessionManager.create_session("samantha")
        assert meta["title"] == "New Conversation"


# ---------------------------------------------------------------------------
# append_turn
# ---------------------------------------------------------------------------

class TestAppendTurn:
    def test_turn_appended_to_file(self):
        meta = SessionManager.create_session("samantha", title="Test")
        sid = meta["session_id"]
        SessionManager.append_turn(sid, "samantha", "Hello!", "Hi there!")
        loaded = SessionManager.load_session(sid)
        assert loaded is not None
        assert len(loaded["turns"]) == 1
        assert loaded["turns"][0]["user"] == "Hello!"

    def test_turns_count_increments(self):
        meta = SessionManager.create_session("samantha", title="Test")
        sid = meta["session_id"]
        SessionManager.append_turn(sid, "samantha", "Msg 1", "Reply 1")
        SessionManager.append_turn(sid, "samantha", "Msg 2", "Reply 2")
        loaded = SessionManager.load_session(sid)
        assert loaded["turns_count"] == 2

    def test_creates_file_if_absent(self, tmp_sessions_dir):
        sid = "samantha_20240101_999999_abcdef"
        result = SessionManager.append_turn(sid, "samantha", "Hello", "World")
        assert result is not None
        assert result["handle"] == "samantha"

    def test_title_upgraded_from_generic(self):
        meta = SessionManager.create_session("samantha")
        sid = meta["session_id"]
        SessionManager.append_turn(sid, "samantha", "Write me a poem about the sea", "Sure!")
        loaded = SessionManager.load_session(sid)
        # Title should have been upgraded from "New Conversation"
        assert loaded["title"] != "New Conversation"


# ---------------------------------------------------------------------------
# update_session_title
# ---------------------------------------------------------------------------

class TestUpdateSessionTitle:
    def test_title_updated_successfully(self):
        meta = SessionManager.create_session("samantha")
        sid = meta["session_id"]
        result = SessionManager.update_session_title(sid, "New Title Here")
        assert result is True
        loaded = SessionManager.load_session(sid)
        assert loaded["title"] == "New Title Here"

    def test_returns_false_for_nonexistent_session(self):
        result = SessionManager.update_session_title("nonexistent_id", "Title")
        assert result is False

    def test_long_title_gets_truncated(self):
        meta = SessionManager.create_session("samantha")
        sid = meta["session_id"]
        long_title = "This is a very long title that should be truncated by derive_title method"
        SessionManager.update_session_title(sid, long_title)
        loaded = SessionManager.load_session(sid)
        assert len(loaded["title"]) <= 68


# ---------------------------------------------------------------------------
# load_session
# ---------------------------------------------------------------------------

class TestLoadSession:
    def test_load_returns_none_for_missing(self):
        result = SessionManager.load_session("ghost_session_id")
        assert result is None

    def test_load_returns_turns(self, sample_session_jsonl):
        _fpath, sid = sample_session_jsonl
        # sample_session_jsonl already writes into the mock sessions dir
        loaded = SessionManager.load_session(sid)
        assert loaded is not None
        assert len(loaded["turns"]) == 1

    def test_load_includes_relative_time(self, sample_session_jsonl):
        _fpath, sid = sample_session_jsonl
        loaded = SessionManager.load_session(sid)
        assert "relative_time" in loaded


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_delete_removes_file(self):
        meta = SessionManager.create_session("samantha")
        sid = meta["session_id"]
        assert SessionManager.delete_session(sid) is True
        assert SessionManager.load_session(sid) is None

    def test_delete_nonexistent_returns_false(self):
        assert SessionManager.delete_session("ghost_id") is False


# ---------------------------------------------------------------------------
# prune_ghost_sessions
# ---------------------------------------------------------------------------

class TestPruneGhostSessions:
    def test_zero_turn_session_pruned(self):
        meta = SessionManager.create_session("samantha")
        sid = meta["session_id"]
        count = SessionManager.prune_ghost_sessions()
        assert count >= 1
        assert SessionManager.load_session(sid) is None

    def test_active_session_not_pruned(self):
        meta = SessionManager.create_session("samantha")
        sid = meta["session_id"]
        count = SessionManager.prune_ghost_sessions(active_session_id=sid)
        # Active session should be skipped
        assert SessionManager.load_session(sid) is not None

    def test_substantive_session_not_pruned(self):
        meta = SessionManager.create_session("samantha", title="Deep Dive")
        sid = meta["session_id"]
        SessionManager.append_turn(sid, "samantha", "What is quantum computing?", "It's...")
        count = SessionManager.prune_ghost_sessions()
        assert SessionManager.load_session(sid) is not None


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_lists_sessions_for_handle(self):
        for i in range(3):
            meta = SessionManager.create_session("samantha")
            sid = meta["session_id"]
            SessionManager.append_turn(sid, "samantha", f"Question {i} about topic", "Answer")
        results = SessionManager.list_sessions(handle="samantha")
        assert len(results) >= 3

    def test_sorted_newest_first(self):
        sessions = []
        for i in range(2):
            meta = SessionManager.create_session("samantha")
            sid = meta["session_id"]
            SessionManager.append_turn(sid, "samantha", f"Q{i}", "A")
            sessions.append(sid)
        results = SessionManager.list_sessions(handle="samantha")
        updated_ats = [r["updated_at"] for r in results[:2]]
        assert updated_ats == sorted(updated_ats, reverse=True)

    def test_limit_respected(self):
        for i in range(5):
            meta = SessionManager.create_session("samantha")
            sid = meta["session_id"]
            SessionManager.append_turn(sid, "samantha", f"Q{i}", "A")
        results = SessionManager.list_sessions(handle="samantha", limit=2)
        assert len(results) <= 2
