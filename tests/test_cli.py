"""Tests for the `sympose/cli/` Textual mock — the slash-command
registry and persona lookup as plain unit tests, and the interactive
behavior (pickers, autocomplete, digit-select scoping) driven through
Textual's headless pilot. `pytest-asyncio` isn't a declared dependency
here, so each async scenario is run via a small `run_async` helper
instead of an `async def` test function."""

import asyncio

import pytest

from sympose.cli import commands, mock_data
from sympose.cli.app import SymposeCLI


def run_async(coro):
    return asyncio.run(coro)


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


# -- commands.py -------------------------------------------------------


def test_matching_commands_filters_by_prefix():
    assert [c.name for c in commands.matching_commands("/mo")] == ["/model"]


def test_matching_commands_no_match_returns_empty():
    assert commands.matching_commands("/nope") == []


def test_find_command_is_case_insensitive():
    assert commands.find_command("/CLEAR") is commands.find_command("/clear")
    assert commands.find_command("/clear").danger is True


def test_find_command_unknown_returns_none():
    assert commands.find_command("/nope") is None


# -- mock_data.py --------------------------------------------------------


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    (base / "samantha.yaml").write_text("name: Samantha\nhandle: samantha\ntitle: Vault Companion\n")
    (base / "aria.yaml").write_text("name: Aria\nhandle: aria\ntitle: Test specialist\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def test_list_personas_reads_real_profile_files(profiles):
    handles = [p.handle for p in mock_data.list_personas()]
    assert handles == ["aria", "samantha"]  # sorted, not config order


def test_list_personas_falls_back_when_no_profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "does-not-exist"))
    personas = mock_data.list_personas()
    assert [p.handle for p in personas] == ["samantha"]
    assert personas[0].name == "Samantha"


def test_list_personas_lowercases_a_capitalized_filename(tmp_path, monkeypatch):
    """A `Samantha.yaml` filename (plausible: an OS file picker or editor
    that auto-capitalizes, or a copied template) must still resolve to
    handle "samantha" — `get_profile` already lowercases before building
    its file path, so a mismatched case here would silently drop the
    persona's real config and, in `app.py`, break default-persona
    selection too."""
    base = tmp_path / "profiles"
    base.mkdir()
    (base / "Samantha.yaml").write_text("name: Samantha\nhandle: samantha\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    personas = mock_data.list_personas()
    assert [p.handle for p in personas] == ["samantha"]


# -- app.py / dispatch.py / picker.py / runtime.py, via the headless pilot --


def test_default_persona_is_samantha_not_alphabetically_first(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.persona.handle == "samantha"

    run_async(scenario())


def test_autocomplete_populates_matching_options(profiles):
    """Regression test: `SelectionPanel.__init__` used to store its
    options on `self._options`, which `OptionList.__init__` silently
    clobbers with its own same-named private list — every panel rendered
    its border with zero rows until that was renamed."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/", "m", "o", "d")
            await pilot.pause()
            assert app.panel_kind == "autocomplete"
            assert app.panel.option_count == 1
            assert "/model" in app.panel.get_option_at_index(0).prompt.plain

    run_async(scenario())


def test_digit_keys_type_literally_during_autocomplete(profiles):
    """Numbers are reserved for the model/persona/history pickers —
    typing a digit while the `/`-autocomplete overlay is showing must
    type into the input, not select a row, since the overlay is never
    focused (only Tab/Shift+Tab cycle it)."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/", "2")
            await pilot.pause()
            assert app.composer.value == "/2"
            assert app.focused is app.composer

    run_async(scenario())


def test_tab_cycles_and_fills_matching_commands(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/")
            await pilot.pause()
            expected = [c.name for c in commands.matching_commands("/")]
            first_match, second_match = expected[0], expected[1]
            await pilot.press("tab")
            await pilot.pause()
            assert app.composer.value == first_match
            assert app.focused is app.composer  # Tab never moves focus
            await pilot.press("tab")
            await pilot.pause()
            assert app.composer.value == second_match
            # Shift+Tab walks back to the first match.
            await pilot.press("shift+tab")
            await pilot.pause()
            assert app.composer.value == first_match

    run_async(scenario())


def test_down_up_also_cycle_the_autocomplete(profiles):
    """Down/Up are the more instinctive equivalent of Tab/Shift+Tab for
    cycling the `/`-command overlay — same fill-the-input behavior,
    still without ever moving focus off the composer."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/")
            await pilot.pause()
            expected = [c.name for c in commands.matching_commands("/")]
            await pilot.press("down")
            await pilot.pause()
            assert app.composer.value == expected[0]
            assert app.focused is app.composer
            await pilot.press("down")
            await pilot.pause()
            assert app.composer.value == expected[1]
            await pilot.press("up")
            await pilot.pause()
            assert app.composer.value == expected[0]

    run_async(scenario())


def test_back_to_back_tab_cycles_survive_key_repeat(profiles):
    """Regression test: key-repeat (holding Tab down) can queue a second
    `Key(tab)` before the first fill's `Changed` message is delivered, so
    `ComposerInput.action_cycle_command` runs twice before
    `dispatch.on_input_changed` runs once. A plain boolean guard flag
    gets consumed by the first `Changed` and leaves the second wrongly
    treated as real typing, which resets `tab_matches` mid-cycle and
    traps the cycle on whatever command that second fill landed on."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/")
            await pilot.pause()
            expected = [c.name for c in commands.matching_commands("/")]
            # Two cycles back-to-back, no `pilot.pause()` (no trip
            # through the message pump) between them — the scenario the
            # boolean flag couldn't survive.
            app.composer.action_cycle_command(1)
            app.composer.action_cycle_command(1)
            await pilot.pause()
            assert app.composer.value == expected[1]
            assert [c.name for c in app.tab_matches] == expected  # not collapsed to 1 match
            assert app.panel.option_count == len(expected)

    run_async(scenario())


def test_enter_after_tab_fill_runs_the_command(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/", "c", "l")
            await pilot.pause()
            await pilot.press("tab")  # only match for "/cl" is "/clear"
            await pilot.pause()
            assert app.composer.value == "/clear"
            await pilot.press("enter")
            await pilot.pause()
            assert len(list(app.transcript.children)) == 0  # /clear ran
            assert app.composer.value == ""

    run_async(scenario())


def test_model_picker_digit_select_updates_model_and_banner(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/model", "enter")
            await pilot.pause()
            assert app.panel_kind == "model"
            await pilot.press("2")
            await pilot.pause()
            assert app.model.id == "gemma2:9b"
            assert app.panel is None  # closed after selection
            banner = plain_text(app.query_one("#banner"))
            assert "Gemma2:9b" in banner

    run_async(scenario())


def test_persona_picker_selection_updates_persona(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/persona", "enter")
            await pilot.pause()
            assert app.panel_kind == "persona"
            await pilot.press("1")  # sorted: aria is option 1
            await pilot.pause()
            assert app.persona.handle == "aria"

    run_async(scenario())


def test_digit_keys_type_literally_with_no_panel_open(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("2")
            await pilot.pause()
            assert app.composer.value == "2"

    run_async(scenario())


def test_clear_empties_transcript(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            assert len(list(app.transcript.children)) > 2
            await pilot.press(*"/clear", "enter")
            await pilot.pause()
            assert len(list(app.transcript.children)) == 0

    run_async(scenario())


def test_unknown_command_shows_error(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/bogus", "enter")
            await pilot.pause()
            lines = [plain_text(child) for child in app.transcript.children]
            assert any("Unknown command: /bogus" in line for line in lines)

    run_async(scenario())


def test_escape_closes_autocomplete_and_keeps_typed_text(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/his")
            await pilot.pause()
            assert app.panel is not None
            await pilot.press("escape")
            await pilot.pause()
            assert app.panel is None
            assert app.composer.value == "/his"
            assert app.focused is app.composer

    run_async(scenario())


def test_quit_command_exits_the_app(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/quit", "enter")
            await pilot.pause()
            assert app._exit is True

    run_async(scenario())


def test_composer_loses_its_top_margin_only_while_a_panel_is_open(profiles):
    """Regression test: the fix for the composer's top margin used a
    more-specific selector overriding just `margin-top`, which Textual's
    CSS doesn't merge with the base rule's other three sides the way
    plain CSS cascading would — it silently reset them to 0 too, so a
    picker being open would leave the composer with no left/right/bottom
    margin either, not just no top margin."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.composer.styles.margin == (1, 1, 1, 1)
            app.composer.focus()
            await pilot.press("/")
            await pilot.pause()
            assert app.composer.styles.margin == (0, 1, 1, 1)
            await pilot.press("escape")
            await pilot.pause()
            assert app.composer.styles.margin == (1, 1, 1, 1)

    run_async(scenario())


def test_menu_lines_never_get_a_gap(profiles):
    """The gap is a chat-message thing, not a general transcript thing —
    `/help`'s listing and the startup hints (all "system") never get it,
    including at the system/user boundary, since a menu-like block
    shouldn't pick up the chat's own breathing room."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            hint_lines = list(app.transcript.children)
            assert len(hint_lines) == 2
            assert "turn-gap" not in hint_lines[0].classes
            assert "turn-gap" not in hint_lines[1].classes  # same speaker
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            you_line = list(app.transcript.children)[2]
            assert "turn-gap" not in you_line.classes  # system -> user: no gap

    run_async(scenario())


def test_gap_appears_between_user_and_persona_turns(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            children = list(app.transcript.children)
            you_line, reply_line = children[2], children[3]
            assert "turn-gap" not in you_line.classes  # system -> user: no gap
            assert "turn-gap" in reply_line.classes  # user -> persona: gap

    run_async(scenario())
