"""
Unit tests for sympose.completer.SymposeCompleter — Tab completion routing.
"""

from unittest.mock import MagicMock

import pytest

from sympose.completer import SymposeCompleter


@pytest.fixture
def comp():
    return SymposeCompleter(MagicMock())


def _c(comp, line, text):
    return comp.get_completions(line, text)


class TestRootCommands:
    @pytest.mark.parametrize("prefix,expected", [
        ("/back", "/backlinks"),
        ("/cl", "/cls"),
        ("/vau", "/vaults"),
    ])
    def test_missing_aliases_now_complete(self, comp, prefix, expected):
        assert expected in _c(comp, prefix, prefix)


class TestConfigCompletion:
    def test_bare_key_prefix_completes_leniently(self, comp):
        """`/config vau<TAB>` — the reported gap: no `set`/`get` typed yet."""
        out = _c(comp, "/config vau", "vau")
        assert out and all(k.startswith("vault.") for k in out)

    def test_first_arg_offers_subcommands(self, comp):
        out = _c(comp, "/config ", "")
        assert "get" in out and "set" in out

    def test_get_then_key(self, comp):
        out = _c(comp, "/config get vault.man", "vault.man")
        assert "vault.manifest.enabled" in out

    def test_set_then_key(self, comp):
        out = _c(comp, "/config set performance.str", "performance.str")
        assert "performance.stream" in out

    def test_value_position_is_not_offered_keys(self, comp):
        assert _c(comp, "/config set performance.stream tr", "tr") == []
