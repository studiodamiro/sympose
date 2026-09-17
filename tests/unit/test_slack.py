"""
Unit tests for sympose.slack.SlackDaemon — `_conversation_key` (the memory/
session continuity boundary for Slack conversations) plus `_process_message`
and the helpers it was decomposed into (mccabe flagged the original
monolithic `_process_message` at complexity 20; see slack.py's own history
for the extraction). The latter had no prior coverage at all.
"""

import time
from unittest.mock import MagicMock

from sympose.slack import SlackDaemon


def _daemon(**overrides):
    """Builds a SlackDaemon without running __init__ (which needs a real
    ProfileManager/config and env-derived tokens) — attributes are set
    directly to whatever a real __init__ would have assigned."""
    d = SlackDaemon.__new__(SlackDaemon)
    d.engine = MagicMock()
    d.pm = MagicMock()
    d.config = MagicMock()
    d.config.get.side_effect = lambda k: {
        "performance.max_consecutive_bot_turns": 4,
    }.get(k, 4)
    d.default_persona = "samantha"
    d.thread_histories = {}
    d.bot_user_id = "UBOT"
    d.bot_id = "BBOT"
    d.bot_user_ids = {"UBOT"}
    d.boot_ts = time.time() - 100
    d.name_to_id = {}
    d.primary_user = "damiro"
    for k, v in overrides.items():
        setattr(d, k, v)
    return d


class TestConversationKey:
    def test_dm_key_is_stable_across_untreaded_followups(self):
        """A plain DM back-and-forth never uses Slack's thread feature, so
        every message has a different `ts` and no `thread_ts` at all. The DM
        key must ignore both and stay pinned to the channel — this is the
        actual bug: keying on thread_ts/ts meant every untHreaded follow-up
        reset the persona's memory to zero."""
        first_message = {"ts": "1000.0001"}
        second_message = {"ts": "1000.0099"}

        key_one = SlackDaemon._conversation_key("D123", True, first_message)
        key_two = SlackDaemon._conversation_key("D123", True, second_message)

        assert key_one == key_two == "D123"

    def test_dm_key_ignores_thread_ts_too(self):
        """Even if a DM message happens to carry a thread_ts (the user did
        explicitly thread a reply), the DM key still doesn't fragment on it —
        a DM is one conversation regardless."""
        threaded_message = {"ts": "1000.0050", "thread_ts": "1000.0001"}

        assert SlackDaemon._conversation_key("D123", True, threaded_message) == "D123"

    def test_channel_key_uses_thread_ts_when_present(self):
        """A channel can hold several simultaneous conversations, so an
        explicitly-threaded reply must stay scoped to its own thread."""
        reply = {"ts": "1000.0050", "thread_ts": "1000.0001"}

        assert SlackDaemon._conversation_key("C456", False, reply) == "C456:1000.0001"

    def test_channel_key_falls_back_to_own_ts_for_unthreaded_first_message(self):
        """The first message in a new channel conversation has no thread_ts
        yet — it becomes the anchor for whatever thread starts under it."""
        first_message = {"ts": "1000.0001"}

        assert (
            SlackDaemon._conversation_key("C456", False, first_message)
            == "C456:1000.0001"
        )

    def test_channel_key_falls_back_to_channel_id_when_no_timestamp_at_all(self):
        assert SlackDaemon._conversation_key("C456", False, {}) == "C456:C456"

    def test_two_different_dms_never_collide(self):
        assert SlackDaemon._conversation_key(
            "D111", True, {"ts": "1"}
        ) != SlackDaemon._conversation_key("D222", True, {"ts": "1"})


class TestShouldSkipMessage:
    def test_empty_text_is_skipped(self):
        d = _daemon()
        assert d._should_skip_message("   ", str(time.time()), "U1", "") is True

    def test_stale_message_before_boot_is_skipped(self):
        d = _daemon(boot_ts=time.time())
        assert d._should_skip_message("hello", "1.0", "U1", "") is True

    def test_own_bot_user_id_echo_is_skipped(self):
        d = _daemon()
        assert d._should_skip_message("hi", str(time.time()), "UBOT", "") is True

    def test_own_bot_id_echo_is_skipped(self):
        d = _daemon()
        assert d._should_skip_message("hi", str(time.time()), "", "BBOT") is True

    def test_normal_message_is_not_skipped(self):
        d = _daemon()
        assert d._should_skip_message("hi there", str(time.time()), "U2", "") is False


class TestBotStreakNotice:
    def test_non_bot_message_leaves_prompt_untouched(self):
        d = _daemon()
        client = MagicMock()
        out = d._maybe_append_bot_streak_notice(
            client, "C1", {"subtype": None, "thread_ts": "1.0"}, "U2", "", "hello"
        )
        assert out == "hello"
        client.conversations_replies.assert_not_called()

    def test_bot_message_with_no_thread_leaves_prompt_untouched(self):
        d = _daemon()
        client = MagicMock()
        out = d._maybe_append_bot_streak_notice(
            client, "C1", {"subtype": "bot_message"}, "", "B1", "hello"
        )
        assert out == "hello"
        client.conversations_replies.assert_not_called()

    def test_streak_below_threshold_leaves_prompt_untouched(self):
        d = _daemon()
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"bot_id": "B1"}, {"user": "U2"}]
        }
        out = d._maybe_append_bot_streak_notice(
            client, "C1", {"subtype": "bot_message", "thread_ts": "1.0"}, "", "B1", "hello"
        )
        assert out == "hello"

    def test_streak_at_threshold_appends_notice(self):
        d = _daemon()
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"bot_id": "B1"}] * 4
        }
        out = d._maybe_append_bot_streak_notice(
            client, "C1", {"subtype": "bot_message", "thread_ts": "1.0"}, "", "B1", "hello"
        )
        assert "hello" in out and "Discussion turn limit reached" in out

    def test_lookup_failure_leaves_prompt_untouched(self):
        d = _daemon()
        client = MagicMock()
        client.conversations_replies.side_effect = RuntimeError("boom")
        out = d._maybe_append_bot_streak_notice(
            client, "C1", {"subtype": "bot_message", "thread_ts": "1.0"}, "", "B1", "hello"
        )
        assert out == "hello"


class TestThreadWipeRequest:
    def test_non_wipe_prompt_returns_false_and_does_nothing(self):
        d = _daemon()
        say = MagicMock()
        handled = d._handle_thread_wipe_request(
            MagicMock(), {}, "C1", "1.0", "1.0", "T1", "samantha", "hello there", say
        )
        assert handled is False
        say.assert_not_called()

    def test_wipe_phrase_clears_history_and_confirms(self):
        d = _daemon()
        d.thread_histories["T1:samantha"] = [{"role": "user", "content": "hi"}]
        say = MagicMock()
        client = MagicMock()
        client.conversations_replies.return_value = {"messages": [{"ts": "1.0"}]}
        handled = d._handle_thread_wipe_request(
            client, {}, "C1", "1.0", "1.0", "T1", "samantha", "please delete our chat", say
        )
        assert handled is True
        assert "T1:samantha" not in d.thread_histories
        d.engine.reset_history.assert_called_once_with("samantha", session_id="T1:samantha")
        say.assert_called_once()
        assert "deleted" in say.call_args.kwargs["text"]

    def test_slash_clear_alias_is_also_a_wipe(self):
        d = _daemon()
        say = MagicMock()
        handled = d._handle_thread_wipe_request(
            MagicMock(), {}, "C1", "1.0", "1.0", "T1", "samantha", "/clear", say
        )
        assert handled is True

    def test_do_not_reply_suppresses_confirmation(self):
        d = _daemon()
        say = MagicMock()
        handled = d._handle_thread_wipe_request(
            MagicMock(),
            {},
            "C1",
            "1.0",
            "1.0",
            "T1",
            "samantha",
            "please delete our chat, do not reply",
            say,
        )
        assert handled is True
        say.assert_not_called()

    def test_thread_ts_present_deletes_slack_messages(self):
        d = _daemon()
        say = MagicMock()
        client = MagicMock()
        client.conversations_replies.return_value = {
            "messages": [{"ts": "1.0"}, {"ts": "2.0"}]
        }
        d._handle_thread_wipe_request(
            client,
            {"thread_ts": "0.5"},
            "C1",
            "1.0",
            "1.0",
            "T1",
            "samantha",
            "/reset",
            say,
        )
        assert client.chat_delete.call_count == 2


class TestRunChatTurnAndReply:
    def test_normal_reply_is_said_and_reacted(self):
        d = _daemon()
        d.engine.chat_stream.return_value = iter(["Here's ", "the answer."])
        d.engine.get_history.return_value = []
        say = MagicMock()
        client = MagicMock()
        d._run_chat_turn_and_reply(
            client, "C1", "1.0", "1.0", "T1:samantha", "samantha", "hi", "Samantha", say
        )
        say.assert_called_once()
        assert "the answer" in say.call_args.kwargs["text"]
        client.reactions_remove.assert_called_once()

    def test_silent_reply_gets_checkmark_and_no_say(self):
        d = _daemon()
        d.engine.chat_stream.return_value = iter(["(no response)"])
        d.engine.get_history.return_value = []
        say = MagicMock()
        client = MagicMock()
        d._run_chat_turn_and_reply(
            client, "C1", "1.0", "1.0", "T1:samantha", "samantha", "hi", "Samantha", say
        )
        say.assert_not_called()
        client.reactions_add.assert_called_once_with(
            channel="C1", timestamp="1.0", name="white_check_mark"
        )

    def test_react_tag_drives_reaction_choice(self):
        d = _daemon()
        d.engine.chat_stream.return_value = iter(["Great news! [REACT: tada]"])
        d.engine.get_history.return_value = []
        say = MagicMock()
        client = MagicMock()
        d._run_chat_turn_and_reply(
            client, "C1", "1.0", "1.0", "T1:samantha", "samantha", "hi", "Samantha", say
        )
        client.reactions_add.assert_called_once_with(
            channel="C1", timestamp="1.0", name="tada"
        )

    def test_engine_exception_says_error_not_raise(self):
        d = _daemon()
        d.engine.chat_stream.side_effect = RuntimeError("model offline")
        say = MagicMock()
        d._run_chat_turn_and_reply(
            MagicMock(), "C1", "1.0", "1.0", "T1:samantha", "samantha", "hi", "Samantha", say
        )
        say.assert_called_once()
        assert "model offline" in say.call_args.kwargs["text"]


class TestProcessMessageOrchestration:
    """End-to-end checks of `_process_message` itself, with
    `_resolve_persona_and_prompt`/`_fetch_slack_context` stubbed out (their
    own real logic is exercised elsewhere) so these focus on how the
    extracted phases are wired together."""

    def _wired_daemon(self, handle="samantha", prompt="hello"):
        d = _daemon()
        d._resolve_persona_and_prompt = MagicMock(return_value=(handle, prompt))
        d._fetch_slack_context = MagicMock(return_value="")
        d.pm.get_profile.return_value = {"name": "Samantha"}
        return d

    def test_skip_guard_short_circuits_before_anything_else(self):
        d = self._wired_daemon()
        client = MagicMock()
        say = MagicMock()
        d._process_message(client, {"channel": "C1", "ts": "1.0", "text": "   "}, say)
        d._resolve_persona_and_prompt.assert_not_called()
        client.reactions_add.assert_not_called()

    def test_wrong_bot_token_persona_is_skipped(self, monkeypatch):
        d = self._wired_daemon(handle="rosalind")
        monkeypatch.setenv("SLACK_ROSALIND_BOT_TOKEN", "xoxb-dedicated")
        client = MagicMock()
        say = MagicMock()
        d._process_message(
            client, {"channel": "C1", "ts": str(time.time()), "text": "hi"}, say
        )
        client.reactions_add.assert_not_called()
        d.engine.chat_stream.assert_not_called()

    def test_wipe_request_stops_before_chat_turn(self):
        d = self._wired_daemon(prompt="/reset")
        client = MagicMock()
        say = MagicMock()
        d._process_message(
            client, {"channel": "C1", "ts": str(time.time()), "text": "/reset"}, say
        )
        d.engine.chat_stream.assert_not_called()
        d.engine.reset_history.assert_called_once()

    def test_normal_message_runs_full_pipeline(self):
        d = self._wired_daemon(prompt="what's up")
        d.engine.chat_stream.return_value = iter(["All good!"])
        d.engine.get_history.return_value = []
        client = MagicMock()
        say = MagicMock()
        d._process_message(
            client,
            {"channel": "C1", "ts": str(time.time()), "text": "what's up"},
            say,
        )
        say.assert_called_once()
        assert "All good!" in say.call_args.kwargs["text"]
        eyes_calls = [
            c for c in client.reactions_add.call_args_list if c.kwargs.get("name") == "eyes"
        ]
        assert eyes_calls, "expected an 'eyes' reaction while the turn was processed"
