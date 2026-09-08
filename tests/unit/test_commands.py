"""
Unit tests for sympose.commands.CommandInterceptor — unknown-command helper
and the /commands alias.
"""

from unittest.mock import MagicMock

from sympose.commands import CommandInterceptor


def _run(clean_input: str):
    engine = MagicMock()
    engine.pm.get_profile.return_value = {"handle": "samantha", "name": "Samantha"}
    gen = CommandInterceptor.intercept(engine, "samantha", clean_input)
    return None if gen is None else "".join(gen)


class TestUnknownCommand:
    def test_unknown_slash_returns_helper_not_none(self):
        out = _run("/confi")
        assert out is not None
        assert "Unknown command `/confi`" in out and "/commands" in out

    def test_helper_suggests_near_matches(self):
        out = _run("/co")
        assert "/config" in out and "/compact" in out and "/commands" in out

    def test_unknown_with_no_near_match_still_points_at_commands(self):
        out = _run("/zzz")
        assert out is not None and "Run `/commands`" in out

    def test_non_slash_input_passes_through(self):
        assert _run("what did I write about grief") is None


class TestCommandsAlias:
    def test_commands_shows_the_help_reference(self):
        out = _run("/commands")
        assert out is not None and "SYMPOSE HUB COMMANDS" in out

    def test_help_still_works(self):
        out = _run("/help")
        assert out is not None and "SYMPOSE HUB COMMANDS" in out
