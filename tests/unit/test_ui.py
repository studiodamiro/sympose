"""
Unit tests for sympose.ui.AnimatedStatus and TerminalUI.render_markdown_typewriter.

Covers: purely cosmetic terminal-presentation behavior — the "thinking"
spinner's phrase cycling while a stream's first chunk is pending, and the
progressive reveal of a completed reply in `buffered` render mode. Neither
touches the model stream, adds a round-trip, or costs a token.
"""

import io
import time

import pytest
from rich.console import Console

from sympose.ui import AnimatedStatus, TerminalUI


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


class TestRenderMarkdownTypewriter:
    def test_short_text_skips_animation_entirely(self):
        """Below the effect threshold there's nothing worth animating —
        must return near-instantly, not wait out any part of `duration`."""
        console = _silent_console()
        start = time.time()
        TerminalUI.render_markdown_typewriter(console, "Hi there.", duration=5.0)
        assert time.time() - start < 0.2

    def test_non_terminal_console_skips_animation(self):
        """Piped/redirected output (a real Console, not force_terminal) must
        render instantly rather than animate into a file or pipe."""
        console = Console(file=io.StringIO(), force_terminal=False, width=80)
        long_text = "This is a much longer reply that clears the effect length threshold easily. " * 3
        start = time.time()
        TerminalUI.render_markdown_typewriter(console, long_text, duration=5.0)
        assert time.time() - start < 0.2

    def test_long_reply_stays_bounded_by_duration(self):
        """A long reply must not take proportionally longer to reveal than a
        short one — total wall time stays pinned near `duration` regardless
        of how many reveal steps that requires."""
        console = _silent_console()
        long_text = ("Simulated reply content, several sentences long. " * 150).strip()
        start = time.time()
        TerminalUI.render_markdown_typewriter(console, long_text, duration=0.3)
        elapsed = time.time() - start
        assert elapsed < 1.0  # generous ceiling; unbounded per-step sleep used to blow past this

    def test_keyboard_interrupt_propagates_not_swallowed(self, monkeypatch):
        """A user hitting Ctrl+C mid-reveal must interrupt the reveal, not be
        silently absorbed by the animation's own fallback error handling."""
        console = _silent_console()
        monkeypatch.setattr(time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
        long_text = ("Simulated reply content, several sentences long. " * 10).strip()
        with pytest.raises(KeyboardInterrupt):
            TerminalUI.render_markdown_typewriter(console, long_text, duration=1.0)
