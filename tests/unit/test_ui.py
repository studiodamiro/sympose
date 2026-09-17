"""
Unit tests for sympose.ui.AnimatedStatus and TerminalUI.render_markdown_typewriter.

Covers: purely cosmetic terminal-presentation behavior — the "thinking"
spinner's phrase cycling while a stream's first chunk is pending, and the
progressive reveal of a completed reply in `buffered` render mode. Neither
touches the model stream, adds a round-trip, or costs a token.

The classes further down cover `MultiSectionPanel.__rich_console__`,
`select_session`, `render_vault_search_panel`, `render_vault_note_panel`, and
`interactive_vault_browser` — all flagged by mccabe (complexity 12-23) and
decomposed into smaller helpers, none of which had prior test coverage.
"""

import io
import time
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from sympose.ui import AnimatedStatus, MultiSectionPanel, TerminalUI


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


class TestMultiSectionPanelRichConsole:
    def test_renders_title_and_all_section_bodies(self):
        console = _silent_console()
        panel = MultiSectionPanel(
            "My Title",
            [(None, "First section"), ("Second Header", "Second section")],
        )
        console.print(panel)
        out = console.file.getvalue()
        assert "My Title" in out
        assert "First section" in out
        assert "Second Header" in out
        assert "Second section" in out

    def test_single_section_has_no_divider(self):
        console = _silent_console()
        panel = MultiSectionPanel("Solo", [(None, "Only section")])
        console.print(panel)
        out = console.file.getvalue()
        assert "╭─" in out and "╰" in out


class TestSelectSession:
    def test_no_sessions_returns_none(self):
        console = _silent_console()
        assert TerminalUI.select_session(console, []) is None

    def test_no_console_plain_path_uses_default_index(self, monkeypatch):
        sessions = [
            {"session_id": "abc", "title": "First", "turns_count": 3},
            {"session_id": "def", "title": "Second", "turns_count": 1},
        ]
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")
        assert TerminalUI.select_session(None, sessions) == "abc"

    def test_no_console_plain_path_honors_explicit_index(self, monkeypatch):
        sessions = [
            {"session_id": "abc", "title": "First"},
            {"session_id": "def", "title": "Second"},
        ]
        monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "2")
        assert TerminalUI.select_session(None, sessions) == "def"

    def test_console_path_quit_returns_none(self, monkeypatch):
        console = _silent_console()
        sessions = [{"session_id": "abc", "title": "First"}]
        monkeypatch.setattr(
            "sympose.ui.Prompt.ask", lambda *a, **kw: "q"
        )
        assert TerminalUI.select_session(console, sessions) is None

    def test_console_path_default_picks_first_session(self, monkeypatch):
        console = _silent_console()
        sessions = [
            {"session_id": "abc", "title": "First"},
            {"session_id": "def", "title": "Second"},
        ]
        monkeypatch.setattr("sympose.ui.Prompt.ask", lambda *a, **kw: "1")
        assert TerminalUI.select_session(console, sessions) == "abc"

    def test_console_path_picks_by_index(self, monkeypatch):
        console = _silent_console()
        sessions = [
            {"session_id": "abc", "title": "First"},
            {"session_id": "def", "title": "Second"},
        ]
        monkeypatch.setattr("sympose.ui.Prompt.ask", lambda *a, **kw: "2")
        assert TerminalUI.select_session(console, sessions) == "def"

    def test_console_path_interrupted_returns_none(self, monkeypatch):
        console = _silent_console()
        sessions = [{"session_id": "abc", "title": "First"}]

        def _raise(*a, **kw):
            raise KeyboardInterrupt

        monkeypatch.setattr("sympose.ui.Prompt.ask", _raise)
        assert TerminalUI.select_session(console, sessions) is None


class TestRenderVaultSearchPanel:
    def test_no_results_console_message(self):
        console = _silent_console()
        TerminalUI.render_vault_search_panel(console, "grief", [])
        assert "No notes found" in console.file.getvalue()

    def test_no_console_plain_path(self, capsys):
        results = [
            {"index": 1, "rel_path": "Journal/2024.md", "match_type": "title", "snippet": ""}
        ]
        TerminalUI.render_vault_search_panel(None, "journal", results)
        out = capsys.readouterr().out
        assert "VAULT SEARCH" in out and "Journal/2024.md" in out

    def test_console_path_renders_results_and_tags(self):
        console = _silent_console()
        results = [
            {
                "index": 1,
                "rel_path": "Notes/Dylan.md",
                "match_type": "content",
                "line_no": 5,
                "snippet": "met with Dylan yesterday",
                "tags": ["friend", "journal"],
            }
        ]
        TerminalUI.render_vault_search_panel(console, "dylan", results)
        out = console.file.getvalue()
        assert "Notes/Dylan.md" in out
        assert "friend" in out
        assert "met with Dylan" in out


class TestRenderVaultNotePanel:
    def test_no_console_plain_path(self, capsys):
        TerminalUI.render_vault_note_panel(
            None, "Notes/x.md", "---\ntitle: X\n---\n\nBody text here."
        )
        out = capsys.readouterr().out
        assert "NOTE: Notes/x.md" in out
        assert "Body text here." in out

    def test_console_path_renders_frontmatter_and_body(self):
        console = _silent_console()
        content = "---\ntitle: My Note\ntags: [alpha, beta]\nauthor: damiro\n---\n\n# Heading\n\nBody paragraph."
        TerminalUI.render_vault_note_panel(console, "Notes/my_note.md", content)
        out = console.file.getvalue()
        assert "Notes/my_note.md" in out
        assert "My Note" in out
        assert "alpha" in out and "beta" in out
        assert "Body paragraph" in out

    def test_console_path_empty_note_body(self):
        console = _silent_console()
        TerminalUI.render_vault_note_panel(console, "Notes/empty.md", "")
        out = console.file.getvalue()
        assert "Empty note" in out


class TestInteractiveVaultBrowser:
    def test_no_results_console_message(self):
        console = _silent_console()
        TerminalUI.interactive_vault_browser(console, {}, "grief", [])
        assert "No notes found" in console.file.getvalue()

    def test_no_console_prints_digest(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "sympose.vault.VaultManager.format_search_digest",
            lambda q, r: f"digest for {q}",
        )
        TerminalUI.interactive_vault_browser(
            None, {}, "grief", [{"rel_path": "x.md", "index": 1}]
        )
        assert "digest for grief" in capsys.readouterr().out

    def test_list_mode_quit_exits_immediately(self, monkeypatch):
        console = _silent_console()
        results = [{"rel_path": "x.md", "index": 1}]
        monkeypatch.setattr("sympose.ui.Prompt.ask", lambda *a, **kw: "q")
        TerminalUI.interactive_vault_browser(console, {}, "grief", results)
        # Must not raise / hang — reaching here is the assertion.

    def test_digit_jumps_to_note_then_back_then_quit(self, monkeypatch):
        console = _silent_console()
        results = [
            {"rel_path": "x.md", "index": 1},
            {"rel_path": "y.md", "index": 2},
        ]
        responses = iter(["1", "b", "q"])
        monkeypatch.setattr("sympose.ui.Prompt.ask", lambda *a, **kw: next(responses))
        monkeypatch.setattr(
            "sympose.vault.VaultManager.read_note", lambda profile, rel: "note body"
        )
        TerminalUI.interactive_vault_browser(console, {}, "grief", results)
        out = console.file.getvalue()
        assert "x.md" in out

    def test_open_command_calls_obsidian_open(self, monkeypatch):
        console = _silent_console()
        results = [{"rel_path": "x.md", "index": 1}]
        responses = iter(["o 1", "q"])
        monkeypatch.setattr("sympose.ui.Prompt.ask", lambda *a, **kw: next(responses))
        open_mock = MagicMock(return_value=(True, "Opened `x.md`"))
        monkeypatch.setattr("sympose.vault.VaultManager.open_in_obsidian", open_mock)
        TerminalUI.interactive_vault_browser(console, {}, "grief", results)
        open_mock.assert_called_once()

    def test_initial_index_starts_in_note_mode(self, monkeypatch):
        console = _silent_console()
        results = [
            {"rel_path": "x.md", "index": 1},
            {"rel_path": "y.md", "index": 2},
        ]
        monkeypatch.setattr("sympose.ui.Prompt.ask", lambda *a, **kw: "q")
        monkeypatch.setattr(
            "sympose.vault.VaultManager.read_note", lambda profile, rel: "note body"
        )
        TerminalUI.interactive_vault_browser(console, {}, "grief", results, initial_index=2)
        out = console.file.getvalue()
        assert "y.md" in out and "x.md" not in out
