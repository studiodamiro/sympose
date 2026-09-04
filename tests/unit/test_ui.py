"""
Unit tests for sympose.ui.AnimatedStatus.

Covers: purely cosmetic phrase-cycling behavior for the "thinking" spinner —
no LLM round-trip involved, just terminal presentation while a stream's
first chunk is pending.
"""

import io
import time

from rich.console import Console

from sympose.ui import AnimatedStatus


def _silent_console():
    """A Console writing into a throwaway buffer, safe for tests (no real TTY)."""
    return Console(file=io.StringIO(), force_terminal=True, width=80)


class TestAnimatedStatus:
    def test_single_phrase_never_starts_cycling_thread(self):
        """With only one phrase there's nothing to cycle to, so no thread runs."""
        status = AnimatedStatus(_silent_console(), "Samantha", ["Thinking..."], interval=0.05)
        status.start()
        assert not status._thread.is_alive()
        status.stop()

    def test_multi_phrase_thread_starts_and_stops_cleanly(self):
        status = AnimatedStatus(
            _silent_console(),
            "Samantha",
            ["Connecting dots...", "Synthesizing options...", "Consulting notes..."],
            interval=0.03,
        )
        status.start()
        assert status._thread.is_alive()
        time.sleep(0.15)  # let it cycle a few times
        status.stop()
        status._thread.join(timeout=1.0)
        assert not status._thread.is_alive()

    def test_render_uses_name_and_lowercased_phrase(self):
        status = AnimatedStatus(_silent_console(), "Grace", ["Reviewing the Diff"], interval=1.0)
        rendered = status._render("Reviewing the Diff")
        assert "Grace is reviewing the diff" in rendered
        status.start()
        status.stop()

    def test_stop_is_safe_to_call_without_start(self):
        """Mirrors the cli.py usage pattern: stop() may be called on a status
        that failed before start() (e.g. inside a `finally` after an early
        exception) and must not raise."""
        status = AnimatedStatus(_silent_console(), "Samantha", ["Thinking..."], interval=1.0)
        status.stop()
