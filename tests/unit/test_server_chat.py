"""
Unit tests for sympose.server_chat — the ADR-130 SSE streaming wrapper
around PersonaEngine.chat_stream.
"""

from unittest.mock import MagicMock

from sympose.server_chat import (
    ChatMessageIn,
    _compose_session_id,
    _post_chat_stream,
    stream_chat_events,
)


class _FakeEngine:
    """Stand-in for PersonaEngine — records the exact call chat_stream() got
    and yields a scripted sequence of chunks, firing on_action mid-stream
    the same way the real pipeline does (synchronously, before the chunk
    that follows it)."""

    def __init__(self, chunks, actions_after_chunk=None):
        self.chunks = chunks
        # {chunk_index: [action_event, ...]} — actions fired during the
        # generator step that produces that chunk, before it's returned.
        self.actions_after_chunk = actions_after_chunk or {}
        self.received_call = None

    def chat_stream(self, handle, text, session_id=None, on_action=None):
        self.received_call = {
            "handle": handle,
            "text": text,
            "session_id": session_id,
            "on_action": on_action,
        }
        for i, chunk in enumerate(self.chunks):
            for event in self.actions_after_chunk.get(i, []):
                if on_action:
                    on_action(event)
            yield chunk


class TestStreamChatEvents:
    def test_text_chunks_forwarded_as_text_frames(self):
        engine = _FakeEngine(["Hello", " world"])
        frames = list(stream_chat_events(engine, "samantha", "hi", "s1"))
        assert frames[0] == 'event: text\ndata: "Hello"\n\n'
        assert frames[1] == 'event: text\ndata: " world"\n\n'

    def test_multiline_text_chunk_stays_json_encoded_not_raw(self):
        """A raw (un-JSON-encoded) multi-line chunk would corrupt SSE
        framing, since `data:` is itself newline-delimited."""
        engine = _FakeEngine(["line one\nline two"])
        frames = list(stream_chat_events(engine, "samantha", "hi", "s1"))
        assert frames[0] == 'event: text\ndata: "line one\\nline two"\n\n'
        assert frames[0].count("\n\n") == 1  # exactly one frame terminator

    def test_final_frame_is_always_done(self):
        engine = _FakeEngine(["Hello"])
        frames = list(stream_chat_events(engine, "samantha", "hi", "s1"))
        assert frames[-1] == "event: done\ndata: {}\n\n"

    def test_cleared_session_sentinel_becomes_its_own_event(self):
        engine = _FakeEngine(["CLEARED_SESSION"])
        frames = list(stream_chat_events(engine, "samantha", "/clear", "s1"))
        assert frames[0] == "event: cleared\ndata: {}\n\n"
        assert not any(f.startswith("event: text") for f in frames)

    def test_action_fired_before_a_chunk_is_emitted_before_that_chunks_text_frame(self):
        engine = _FakeEngine(
            ["saved it"],
            actions_after_chunk={0: [{"action": "WRITE_NOTE", "detail": "x.md"}]},
        )
        frames = list(stream_chat_events(engine, "samantha", "hi", "s1"))
        assert frames[0].startswith("event: action")
        assert '"action": "WRITE_NOTE"' in frames[0]
        assert '"detail": "x.md"' in frames[0]
        assert frames[1] == 'event: text\ndata: "saved it"\n\n'
        assert frames[2] == 'event: done\ndata: {}\n\n'

    def test_actions_queued_after_the_last_chunk_still_get_drained(self):
        """Actions that fire on the generator's final resumption (after the
        last yielded chunk, before StopIteration) must not be silently lost."""

        def chat_stream(handle, text, session_id=None, on_action=None):
            yield "reply"
            if on_action:
                on_action({"action": "CONFIG_SET", "detail": "vault.search_mode"})

        engine = MagicMock()
        engine.chat_stream = chat_stream
        frames = list(stream_chat_events(engine, "samantha", "hi", "s1"))
        assert frames == [
            'event: text\ndata: "reply"\n\n',
            'event: action\ndata: {"action": "CONFIG_SET", "detail": "vault.search_mode"}\n\n',
            "event: done\ndata: {}\n\n",
        ]

    def test_session_id_and_on_action_are_passed_through_to_chat_stream(self):
        engine = _FakeEngine(["hi"])
        list(stream_chat_events(engine, "samantha", "hello", "chat:dashboard:abc"))
        assert engine.received_call["handle"] == "samantha"
        assert engine.received_call["text"] == "hello"
        assert engine.received_call["session_id"] == "chat:dashboard:abc"
        assert callable(engine.received_call["on_action"])


class TestComposeSessionId:
    def test_defaults_source_and_session_id(self):
        assert _compose_session_id("pomodoro-widget", None) == "chat:pomodoro-widget:default"

    def test_preserves_an_explicit_session_id(self):
        assert _compose_session_id("dashboard", "tab-1") == "chat:dashboard:tab-1"


class TestPostChatStream:
    def test_response_is_sse_media_type(self):
        engine = _FakeEngine(["hi"])
        body = ChatMessageIn(persona="samantha", text="hi")
        response = _post_chat_stream(engine, body)
        assert response.media_type == "text/event-stream"

    def test_no_cache_and_no_buffering_headers_are_set(self):
        engine = _FakeEngine(["hi"])
        body = ChatMessageIn(persona="samantha", text="hi")
        response = _post_chat_stream(engine, body)
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
