"""
Unit tests for sympose.slack.SlackDaemon._conversation_key — the memory/
session continuity boundary for Slack conversations.
"""

from sympose.slack import SlackDaemon


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
