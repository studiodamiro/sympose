"""Tests for the `sympose/cli/` Textual mock — the slash-command
registry and persona lookup as plain unit tests, and the interactive
behavior (pickers, autocomplete, digit-select scoping) driven through
Textual's headless pilot. `pytest-asyncio` isn't a declared dependency
here, so each async scenario is run via a small `run_async` helper
instead of an `async def` test function."""

from helpers import write_persona
import asyncio
import threading

import pytest

from sympose import engine
from sympose.cli import commands, grounding_line, meter, mock_data, runtime, trim_notice, turns
from sympose.cli.app import SymposeCLI


def run_async(coro):
    return asyncio.run(coro)


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


@pytest.fixture(autouse=True)
def isolated_settings_store(tmp_path, monkeypatch):
    # `/default` writes the settings file and every turn's header reads
    # `chat_model` from it — never the real one in the working directory.
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture(autouse=True)
def stub_engine(monkeypatch):
    """No test in this file should ever reach a real model — `send_message`
    now calls `engine.run_turn` for every non-slash-command message sent
    through the pilot, so this stub stands in for it everywhere, fast and
    network-free, unless a test overrides it to assert on the call itself."""

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        return engine.TurnResult(
            reply="Mock engine reply.", session_id=session_id or "test-session", grounding=[]
        )

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)


class RecapCalls(list):
    """The handles recaps were refreshed for; `models` holds the model each was asked to use."""

    def __init__(self):
        super().__init__()
        self.models: list = []


@pytest.fixture(autouse=True)
def recap_calls(monkeypatch):
    """Recaps (docs/decisions/023) are written by a background model call at launch
    and on a persona switch: never a real one here. The handles it was asked for."""
    calls = RecapCalls()

    def refresh_recaps(handle, model=None):
        calls.append(handle)
        calls.models.append(model)

    monkeypatch.setattr(engine, "refresh_recaps", refresh_recaps)
    monkeypatch.setattr(engine, "refresh_embeddings", lambda handle: None)  # docs/decisions/027: never a real build
    return calls


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
    write_persona(base, "samantha", "name: Samantha\nhandle: samantha\ntitle: Vault Companion\n")
    write_persona(base, "aria", "name: Aria\nhandle: aria\ntitle: Test specialist\n")
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
    write_persona(base, "Samantha", "name: Samantha\nhandle: samantha\n")
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


def test_on_mount_raises_a_clear_error_on_an_empty_roster(tmp_path, monkeypatch):
    """Regression test (`/code-review` finding): list_profiles() now
    deliberately returns [] for an existing-but-empty profiles/ dir
    (docs/decisions/009) -- `next((...), personas[0])` used to evaluate
    `personas[0]` eagerly even when the generator matched, raising a
    cryptic IndexError instead of a legible error. Called directly
    (not through the full pilot lifecycle) since the guard runs before
    any widget is touched."""
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "profiles"))
    (tmp_path / "profiles").mkdir()

    app = SymposeCLI()
    with pytest.raises(RuntimeError, match="No personas configured"):
        app.on_mount()


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


def test_autocomplete_overlay_click_does_not_steal_focus(profiles):
    """Regression test for a `/code-review` finding: the `/`-autocomplete
    overlay never set `can_focus = False`, so a mouse click on it (even
    the border, not just an option row) stole focus from the composer and
    silently swallowed the next keystroke — contradicting the documented
    "Input keeps focus throughout" guarantee."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/", "m", "o", "d")
            await pilot.pause()
            assert app.panel_kind == "autocomplete"
            clicked = await pilot.click("SelectionPanel", offset=(3, 0))
            await pilot.pause()
            assert clicked
            assert app.focused is app.composer
            await pilot.press("1")
            await pilot.pause()
            assert app.composer.value == "/mod1"

    run_async(scenario())


def test_autocomplete_selection_clears_the_composer(profiles):
    """Regression test for a `/code-review` finding: selecting a command
    from the autocomplete overlay via `OptionList.OptionSelected` (the
    real selection path, not just Tab-fill-then-Enter) never cleared
    `app.composer.value`, unlike `on_input_submitted`'s explicit clear —
    the just-typed prefix stayed in the composer after the command
    already ran."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press("/", "h", "e", "l", "p")
            await pilot.pause()
            assert app.panel_kind == "autocomplete"
            app.panel.highlighted = 0
            app.panel.action_select()
            await pilot.pause()
            assert app.composer.value == ""

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
            # The local model is index 0 (default) since the picker's
            # ordering must match the engine's own local-first default
            # (docs/decisions/007) — pick option 2 to actually switch.
            app.composer.focus()
            await pilot.press(*"/model", "enter")
            await pilot.pause()
            assert app.panel_kind == "model"
            await pilot.press("2")
            await pilot.pause()
            assert app.model_override.id == "anthropic/claude-sonnet-5"
            assert app.panel is None  # closed after selection
            banner = plain_text(app.query_one("#banner"))
            assert "Claude Sonnet 5" in banner

    run_async(scenario())


def test_no_model_is_preselected_and_the_default_is_the_local_one(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.model_override is None
            active = mock_data.active_model(app.persona, app.model_override)
            assert active.id == mock_data.MODEL_OPTIONS[0].id
            assert active.id.startswith("ollama_chat/")

    run_async(scenario())


def test_send_message_calls_the_engine_and_streams_the_reply(profiles, monkeypatch):
    calls = []

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        calls.append((handle, user_message, session_id, model))
        return engine.TurnResult(reply="hi there", session_id="sess-1", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            # No explicit /model pick -> None, so the engine applies the
            # persona's own model / the setting / the default itself.
            assert calls == [("samantha", "hello", None, None)]
            assert app.session_id == "sess-1"
            lines = [plain_text(child) for child in app.transcript.children]
            assert any("hi there" in line for line in lines)

    run_async(scenario())


def test_concurrent_sends_do_not_race_the_engine_call(profiles, monkeypatch):
    """Regression test: nothing serialized `engine.run_turn` calls, so a
    second message submitted before the first's reply lands could run
    concurrently with it and race the session read-modify-write
    (docs/decisions/006). `app.turn_locks` must make the second call wait
    for the first to actually finish before it starts."""
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    call_count = {"n": 0}

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            first_started.set()
            assert release_first.wait(timeout=2), "test never released the first call"
        else:
            second_started.set()
        return engine.TurnResult(
            reply=f"reply {call_count['n']}", session_id="sess-x", grounding=[]
        )

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Calling `turns.send_message` directly (not via
            # `pilot.press`/`on_input_submitted`) — this is a
            # runtime-level concurrency property of `send_message` itself,
            # isolated from key-press/dispatch timing. Real keypresses can
            # also genuinely overlap now that dispatch fires `send_message`
            # via `app.run_worker` instead of awaiting it in the message
            # handler (docs/decisions/008) — see
            # `test_queued_marker_is_reachable_through_a_real_second_keypress`
            # for that path specifically.
            task1 = asyncio.create_task(turns.send_message(app, "first"))
            await asyncio.sleep(0.05)
            assert first_started.wait(timeout=2)

            task2 = asyncio.create_task(turns.send_message(app, "second"))
            await asyncio.sleep(0.1)
            assert not second_started.is_set()  # still waiting on the lock

            release_first.set()
            await asyncio.gather(task1, task2)
            assert second_started.wait(timeout=2)

    run_async(scenario())


def test_queued_message_shows_a_queued_marker_until_it_starts(profiles, monkeypatch):
    """docs/decisions/008: a message sent while its persona's lock is
    already held must be visibly marked as queued, not silently waiting
    with no indication anything happened."""
    first_started = threading.Event()
    release_first = threading.Event()
    call_count = {"n": 0}

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            first_started.set()
            assert release_first.wait(timeout=2)
        return engine.TurnResult(
            reply=f"reply {call_count['n']}", session_id="sess-x", grounding=[]
        )

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()

            task1 = asyncio.create_task(turns.send_message(app, "first"))
            await asyncio.sleep(0.05)
            assert first_started.wait(timeout=2)

            task2 = asyncio.create_task(turns.send_message(app, "second"))
            await asyncio.sleep(0.05)

            lines = [plain_text(child) for child in app.transcript.children]
            assert any("second" in line and "queued" in line for line in lines)

            release_first.set()
            await asyncio.gather(task1, task2)

            lines = [plain_text(child) for child in app.transcript.children]
            assert not any("queued" in line for line in lines)

    run_async(scenario())


def test_queued_marker_is_reachable_through_a_real_second_keypress(profiles, monkeypatch):
    """Regression test for a bug live verification caught (not code
    reading): `dispatch.on_input_submitted` used to `await
    turns.send_message` directly, so Textual's `App` — which fully awaits
    one bubbled message's handler before even looking at the next —
    couldn't *receive* a second real Enter press until the first message's
    entire engine call had already returned. The queueing logic above was
    correct, but unreachable through actual user interaction: two
    `send_message` calls could never genuinely overlap when triggered by
    real keypresses, only when a test called `send_message` directly
    (as every test above this one does). Fixed by dispatching via
    `app.run_worker` (docs/decisions/008) so the App's message queue is
    freed immediately, confirmed here via `pilot.press` for both messages —
    the actual real-user path, not a direct function call."""
    first_started = threading.Event()
    release_first = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        if user_message == "first":
            first_started.set()
            assert release_first.wait(timeout=2)
        return engine.TurnResult(
            reply=f"reply to {user_message}", session_id="sess-x", grounding=[]
        )

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()

            await pilot.press(*"first", "enter")
            assert first_started.wait(timeout=2)

            # The real regression: a second genuine keypress, sent while
            # the first is still blocked in its engine call.
            await pilot.press(*"second", "enter")

            lines = [plain_text(child) for child in app.transcript.children]
            assert any("second" in line and "queued" in line for line in lines)

            release_first.set()
            await app.workers.wait_for_complete()
            # `wait_for_complete` only waits for both `send_message` calls
            # to return, i.e. for `_stream_reply` to have *started* each
            # timer — not for the word-by-word reveal itself, which is a
            # separately scheduled `set_interval` tick. A short real sleep,
            # not `pilot.pause()`, since the timers have had ~0 wall-clock
            # time to fire yet at this exact point and `pilot.pause()`'s
            # idle-detection can return before the first 0.05s tick lands.
            await asyncio.sleep(0.3)

            lines = [plain_text(child) for child in app.transcript.children]
            assert any("reply to first" in line for line in lines)
            assert any("reply to second" in line for line in lines)
            assert not any("queued" in line for line in lines)

    run_async(scenario())


def test_different_personas_can_generate_concurrently(profiles, monkeypatch):
    """docs/decisions/008: sessions are stored one file per persona
    (sympose/engine/session.py), so a message to a different persona must
    not wait behind another persona's in-flight call — only two turns for
    the *same* persona need to queue behind each other."""
    a_started = threading.Event()
    release_a = threading.Event()
    b_started = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        if handle == "samantha":
            a_started.set()
            assert release_a.wait(timeout=2)
            return engine.TurnResult(reply="reply a", session_id="sess-a", grounding=[])
        b_started.set()
        return engine.TurnResult(reply="reply b", session_id="sess-b", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()

            task_a = asyncio.create_task(turns.send_message(app, "hello a"))
            await asyncio.sleep(0.05)
            assert a_started.wait(timeout=2)

            aria = next(p for p in mock_data.list_personas() if p.handle == "aria")
            runtime.apply_picker_choice(app, "persona", aria.handle)

            task_b = asyncio.create_task(turns.send_message(app, "hello b"))
            await asyncio.sleep(0.1)
            assert b_started.wait(timeout=2)  # not blocked behind samantha's in-flight call

            lines = [plain_text(child) for child in app.transcript.children]
            assert not any("queued" in line for line in lines)

            release_a.set()
            await asyncio.gather(task_a, task_b)

    run_async(scenario())


def test_queued_message_for_same_persona_continues_predecessors_session_despite_intervening_switches(
    profiles, monkeypatch
):
    """Regression test for the bug docs/decisions/006 flagged and left
    unfixed: a second message queued behind an in-flight call for the same
    persona used to read `app.session_id` live once it finally started —
    which an unrelated persona switch-away-and-back in between could reset
    to `None`, orphaning it onto a brand-new session instead of continuing
    the first call's. Fixed by resolving `session_id` from
    `session_by_generation`, keyed by the generation captured at
    *submission* time, not by re-reading the live (and by then stale)
    `app.session_id` slot (docs/decisions/008)."""
    release_first = threading.Event()
    calls = []

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        calls.append((user_message, session_id))
        if user_message == "first":
            assert release_first.wait(timeout=2)
            return engine.TurnResult(reply="reply 1", session_id="real-session", grounding=[])
        return engine.TurnResult(reply="reply 2", session_id="real-session", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            samantha = app.persona
            assert samantha.handle == "samantha"

            task1 = asyncio.create_task(turns.send_message(app, "first"))
            await asyncio.sleep(0.05)

            task2 = asyncio.create_task(turns.send_message(app, "second"))
            await asyncio.sleep(0.05)

            aria = next(p for p in mock_data.list_personas() if p.handle == "aria")
            runtime.apply_picker_choice(app, "persona", aria.handle)
            runtime.apply_picker_choice(app, "persona", samantha.handle)  # switch back

            release_first.set()
            await asyncio.gather(task1, task2)

            # task2 must see task1's *real* resolved session_id, not `None`
            # (which the intervening switches reset `app.session_id` to).
            assert calls == [("first", None), ("second", "real-session")]

    run_async(scenario())


def test_three_queued_messages_for_the_same_persona_process_in_submission_order(
    profiles, monkeypatch
):
    release = {"first": threading.Event(), "second": threading.Event(), "third": threading.Event()}
    order = []

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        assert release[user_message].wait(timeout=2)
        order.append(user_message)
        return engine.TurnResult(reply=f"reply {user_message}", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            task1 = asyncio.create_task(turns.send_message(app, "first"))
            await asyncio.sleep(0.02)
            task2 = asyncio.create_task(turns.send_message(app, "second"))
            await asyncio.sleep(0.02)
            task3 = asyncio.create_task(turns.send_message(app, "third"))
            await asyncio.sleep(0.02)

            # Set out of order — only one call is ever actually dispatched
            # to the engine at a time (the others are still waiting on the
            # lock), so release order can't affect processing order.
            release["third"].set()
            release["second"].set()
            release["first"].set()
            await asyncio.gather(task1, task2, task3)

            assert order == ["first", "second", "third"]

    run_async(scenario())


def test_two_concurrent_streaming_replies_each_get_their_own_timer(profiles, monkeypatch):
    """docs/decisions/008: `app.reply_timer`'s single slot used to get
    clobbered by whichever of two overlapping streams started or finished
    second. Two different personas' replies can now genuinely stream at
    once, and each must own its own stoppable timer."""

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        return engine.TurnResult(
            reply="a fairly long reply with several words in it to be safe",
            session_id="sess-x",
            grounding=[],
        )

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()

            task_a = asyncio.create_task(turns.send_message(app, "hello a"))
            await asyncio.sleep(0.1)

            aria = next(p for p in mock_data.list_personas() if p.handle == "aria")
            runtime.apply_picker_choice(app, "persona", aria.handle)
            task_b = asyncio.create_task(turns.send_message(app, "hello b"))
            await asyncio.sleep(0.1)

            assert len(app.active_reply_timers) == 2

            await runtime.run_command(app, commands.find_command("/clear"))
            assert app.active_reply_timers == set()
            assert len(list(app.transcript.children)) == 0

            await asyncio.gather(task_a, task_b)

    run_async(scenario())


def test_engine_model_error_shows_a_friendly_message_not_a_crash(profiles, monkeypatch):
    def failing_run_turn(handle, user_message, session_id=None, model=None):
        raise engine.EngineModelError("Couldn't reach model 'x': connection refused")

    monkeypatch.setattr(turns.engine, "run_turn", failing_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            lines = [plain_text(child) for child in app.transcript.children]
            assert any("couldn't reply" in line.lower() for line in lines)

    run_async(scenario())


@pytest.mark.xfail(
    strict=True,
    reason="an error text is shown as Textual markup, so one with brackets that look like a closing tag "
    "(`[/foo]`) raises MarkupError when it is drawn and the app stops; the line also says `Sam` for any persona",
)
def test_an_error_message_with_brackets_is_shown_as_text_not_parsed(profiles, monkeypatch):
    def failing_run_turn(handle, user_message, session_id=None, model=None):
        raise engine.EngineModelError("the server said: bad [/foo] request")

    monkeypatch.setattr(turns.engine, "run_turn", failing_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            lines = [plain_text(child) for child in app.transcript.children]
            assert any("bad [/foo] request" in line for line in lines)

    run_async(scenario())


def test_quit_while_a_call_is_in_flight_exits_the_app_the_normal_way(profiles, monkeypatch):
    """`/quit` with a model call still running exits through Textual's own teardown, which is what
    puts the terminal back (the screen, the cursor, mouse reporting): it used to `os._exit` at once,
    which left the shell broken (#65). The call cannot be cancelled, but the process no longer waits
    for it: `main()` ends with `os._exit` after `run()` returns. What a real terminal gets is checked
    in `test_cli_pty.py`."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="late reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()

            task = asyncio.create_task(turns.send_message(app, "hello"))
            await asyncio.sleep(0.05)
            assert app.turn_locks["samantha"].locked()

            await pilot.press(*"/quit", "enter")
            await pilot.pause()

            assert app._exit is True

            release.set()
            await task  # must not raise

    run_async(scenario())

def test_main_ends_the_process_with_the_apps_own_exit_status(monkeypatch):
    """#66: a start that failed (no persona to talk to) set the app's return code to 1, and the
    process exited 0 anyway. The real terminal is checked in `test_cli_pty.py`."""
    from sympose.cli import __main__ as entry

    class FailedApp:
        return_code = 1

        def run(self):
            pass

    class QuitApp(FailedApp):
        return_code = None  # a normal quit leaves no code

    exits = []
    monkeypatch.setattr(entry.os, "_exit", exits.append)
    for app in (FailedApp, QuitApp):
        monkeypatch.setattr(entry, "SymposeCLI", app)
        entry.main()

    assert exits == [1, 0]


def test_app_exit_while_a_call_is_in_flight_does_not_crash_on_resume(profiles, monkeypatch):
    """`send_message`'s own `if app._exit: return` guards: once the app is exiting, a call that
    resumes afterwards (any way of quitting: `/quit`, ctrl+q, the command palette) must notice
    and bail out instead of touching the transcript/timer of an already-exiting app, not raise
    the `MountError` this was originally written to fix."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="late reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()

            task = asyncio.create_task(turns.send_message(app, "hello"))
            await asyncio.sleep(0.05)

            app.exit()
            assert app._exit is True

            release.set()
            await task  # must not raise

    run_async(scenario())


def test_unexpected_engine_exception_shows_a_friendly_message_not_a_crash(profiles, monkeypatch):
    """Regression test: `send_message` used to catch only
    `engine.EngineModelError` — a bug anywhere else in the engine pipeline
    (grounding/prompt/session, none of which existed before this slice)
    would propagate uncaught out of the Textual event handler instead of
    degrading to an in-transcript line like every other failure path."""

    def buggy_run_turn(handle, user_message, session_id=None, model=None):
        raise KeyError("something the engine didn't expect")

    monkeypatch.setattr(turns.engine, "run_turn", buggy_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()

            lines = [plain_text(child) for child in app.transcript.children]
            assert any("couldn't reply" in line.lower() for line in lines)

    run_async(scenario())  # must not raise out of the pilot


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


def test_switching_persona_resets_session_id(profiles):
    """Regression test: sessions are stored per-handle
    (sympose/engine/session.py), so carrying the old session_id into a new
    persona would resolve to that persona's own (empty) session directory —
    silently dropping history while still writing under the stale id."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            assert app.session_id is not None

            await pilot.press(*"/persona", "enter")
            await pilot.pause()
            await pilot.press("1")  # sorted: aria is option 1
            await pilot.pause()

            assert app.session_id is None

    run_async(scenario())


def test_recaps_are_refreshed_at_launch_and_when_another_persona_is_picked(profiles, recap_calls):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert recap_calls == ["samantha"]
            app.composer.focus()
            await pilot.press(*"/persona", "enter")
            await pilot.pause()
            await pilot.press("1")  # sorted: aria is option 1
            await pilot.pause()
            assert recap_calls == ["samantha", "aria"]
            await pilot.press(*"/persona", "enter")
            await pilot.pause()
            await pilot.press("1")  # the persona already talked to: nothing switches
            await pilot.pause()
            assert recap_calls == ["samantha", "aria"]

    run_async(scenario())


def test_a_model_picked_with_slash_model_is_the_one_a_persona_switch_writes_recaps_with(profiles, recap_calls):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert recap_calls.models == [None]  # at launch nothing is picked: the persona's own model applies
            app.composer.focus()
            await pilot.press(*"/model", "enter")
            await pilot.pause()
            await pilot.press("2")
            await pilot.pause()
            await pilot.press(*"/persona", "enter")
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            assert recap_calls == ["samantha", "aria"]
            assert recap_calls.models == [None, "anthropic/claude-sonnet-5"]

    run_async(scenario())


def test_reselecting_the_current_persona_does_not_reset_the_session(profiles):
    """Regression test: `/persona` unconditionally reset `session_id` even
    when the user picked the persona they're already talking to — silently
    discarding an in-progress conversation they never asked to restart."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.persona.handle == "samantha"
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            sid = app.session_id
            assert sid is not None

            await pilot.press(*"/persona", "enter")
            await pilot.pause()
            await pilot.press("2")  # sorted: samantha is option 2
            await pilot.pause()

            assert app.persona.handle == "samantha"
            assert app.session_id == sid  # unchanged

    run_async(scenario())


def test_ctrl_q_while_a_call_is_in_flight_also_exits_the_normal_way(profiles, monkeypatch):
    """Textual's default ctrl+q binding (and its command-palette Quit entry) call `App.action_quit`
    directly, not `/quit`: both routes end the same way."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="late reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()

            task = asyncio.create_task(turns.send_message(app, "hello"))
            await asyncio.sleep(0.05)
            assert app.turn_locks["samantha"].locked()

            await app.action_quit()  # what ctrl+q/the command palette call

            assert app._exit is True

            release.set()
            await task

    run_async(scenario())

def test_quit_while_a_second_message_is_queued_but_not_yet_started_exits_the_normal_way(
    profiles, monkeypatch
):
    """A second message for the same persona is queued (waiting on the lock, never yet dispatched to
    the engine at all) when the quit comes: the app still exits and both calls end without raising."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="late reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()

            task1 = asyncio.create_task(turns.send_message(app, "first"))
            await asyncio.sleep(0.05)
            task2 = asyncio.create_task(turns.send_message(app, "second"))  # queued, not started
            await asyncio.sleep(0.05)

            await app.action_quit()

            assert app._exit is True

            release.set()
            await asyncio.gather(task1, task2)

    run_async(scenario())

def test_pending_turns_counts_queued_and_in_flight_calls_for_quit_detection(
    profiles, monkeypatch
):
    """Regression test from a `/code-review` finding: `action_quit` used to
    check `any(lock.locked() ...)`, but `Lock.locked()` is a point-in-time
    snapshot — it can briefly read `False` in the gap between one queued
    call releasing its persona's lock and the next one resuming to
    re-acquire it, a real (if narrow) window where `/quit` could wrongly
    take the graceful path and reproduce the exact hang this mechanism
    exists to prevent. `app.pending_turns` instead covers a call's whole
    lifetime — queued or running — with no such gap: it's incremented the
    instant `send_message` starts and only decremented once it's fully
    done, so it stays correctly non-zero for as long as *any* call for any
    persona is still outstanding, distinct from what any single lock's
    `.locked()` reports at any one instant."""
    release_first = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        if user_message == "first":
            assert release_first.wait(timeout=2)
        return engine.TurnResult(
            reply=f"reply to {user_message}", session_id="sess-x", grounding=[]
        )

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.pending_turns == 0

            task1 = asyncio.create_task(turns.send_message(app, "first"))
            await asyncio.sleep(0.05)
            assert app.pending_turns == 1

            task2 = asyncio.create_task(turns.send_message(app, "second"))
            await asyncio.sleep(0.05)
            assert app.pending_turns == 2  # queued, not yet started -- still counted

            release_first.set()
            await asyncio.gather(task1, task2)
            assert app.pending_turns == 0

    run_async(scenario())


def test_persona_switch_during_in_flight_call_is_not_overwritten(profiles, monkeypatch):
    """Regression test: `send_message` used to unconditionally write
    `app.session_id = result.session_id` after its engine call returned,
    with no check for whether the persona had changed while that call was
    still in flight — a persona switch's `app.session_id = None` reset
    (see the test above) could be silently clobbered back to the old
    persona's session_id the moment the in-flight call for the *previous*
    persona finally resolved."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="reply for samantha", session_id="stale-session", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.persona.handle == "samantha"

            task = asyncio.create_task(turns.send_message(app, "hello"))
            await asyncio.sleep(0.05)

            aria = next(p for p in mock_data.list_personas() if p.handle == "aria")
            runtime.apply_picker_choice(app, "persona", aria.handle)
            assert app.persona.handle == "aria"
            assert app.session_id is None

            release.set()
            await task
            await asyncio.sleep(0.1)  # let the reply's first streaming tick fire
            await pilot.pause()

            # Must still be None — not clobbered back to "stale-session" by
            # the samantha call that was in flight when the switch happened.
            assert app.session_id is None
            assert app.persona.handle == "aria"
            # The reply itself must stay attributed to samantha, who it was
            # actually generated for, not aria, who's current by the time
            # it streams in.
            lines = [plain_text(child) for child in app.transcript.children]
            assert any("@samantha" in line for line in lines)
            assert not any("@aria · " in line for line in lines)

    run_async(scenario())


def test_switching_back_to_same_persona_during_in_flight_call_still_wins(profiles, monkeypatch):
    """Regression test: guarding the session_id write-back by persona
    handle alone isn't enough. Switch away and back to the *same* persona
    while a call for it is still in flight, and a plain handle comparison
    matches again by the time that stale call resolves — clobbering the
    second switch's fresh-session reset with the first call's stale
    session_id even though no cross-persona mixup ever happens. Only a
    generation counter bumped on every reset (not just a handle mismatch)
    catches this."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="stale reply", session_id="stale-session", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            samantha = app.persona
            assert samantha.handle == "samantha"

            task = asyncio.create_task(turns.send_message(app, "hello"))
            await asyncio.sleep(0.05)

            aria = next(p for p in mock_data.list_personas() if p.handle == "aria")
            runtime.apply_picker_choice(app, "persona", aria.handle)
            runtime.apply_picker_choice(app, "persona", samantha.handle)  # switch back
            assert app.persona.handle == "samantha"
            assert app.session_id is None

            release.set()
            await task
            await asyncio.sleep(0.1)
            await pilot.pause()

            # The handle matches again ("samantha" == "samantha"), but the
            # second switch's reset must still win over the stale call.
            assert app.session_id is None

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


def test_clear_blocked_while_turn_pending(profiles, monkeypatch):
    """Regression test for a `/code-review` finding: `/clear` used to wipe
    the transcript unconditionally, including the "You" line of a turn
    that hadn't reached its reply yet (queued behind another turn's lock,
    or still running in the engine executor). When that turn's reply
    landed, it mounted into the now-empty transcript with nothing above
    it. `/clear` now checks `pending_turns` (the same signal
    `action_quit` uses) and refuses instead."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        assert release.wait(timeout=2)
        return engine.TurnResult(reply="the reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()

            task = asyncio.create_task(turns.send_message(app, "hello"))
            await asyncio.sleep(0.05)
            assert app.pending_turns == 1
            before = len(list(app.transcript.children))
            assert before > 0  # the "You" line is already mounted

            await runtime.run_command(app, commands.find_command("/clear"))

            # Refused: the "You" line survives, plus the new system message.
            assert len(list(app.transcript.children)) == before + 1

            release.set()
            await task
            # The reply mounts normally once the pending turn resolves.
            assert len(list(app.transcript.children)) == before + 2

    run_async(scenario())


def test_help_lists_every_command(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/help", "enter")
            await pilot.pause()
            lines = [plain_text(child) for child in app.transcript.children]
            assert any("Commands:" in line for line in lines)
            for command in commands.COMMANDS:
                assert any(command.name in line for line in lines)

    run_async(scenario())


def test_compact_shows_a_mock_placeholder(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/compact", "enter")
            await pilot.pause()
            lines = [plain_text(child) for child in app.transcript.children]
            assert any("compacted" in line.lower() for line in lines)

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
    margin either, not just no top margin. (The bottom side is 0: the
    context meter's line, ADR 018, takes the gap that used to be there.)"""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.composer.styles.margin == (1, 1, 0, 1)
            app.composer.focus()
            await pilot.press("/")
            await pilot.pause()
            assert app.composer.styles.margin == (0, 1, 0, 1)
            await pilot.press("escape")
            await pilot.pause()
            assert app.composer.styles.margin == (1, 1, 0, 1)

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


def test_system_lines_are_muted_and_chat_lines_are_not(profiles):
    """Hints, confirmations and errors are "system" lines and must not look like a
    reply: they carry `system-line` (a muted color); the user's and the persona's
    lines do not (docs/decisions/005)."""

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = list(app.transcript.children)[0]
            assert "system-line" in hint.classes
            app.composer.focus()
            await pilot.press(*"hello", "enter")
            await pilot.pause()
            you_line, reply_line = list(app.transcript.children)[2:4]
            assert "system-line" not in you_line.classes
            assert "system-line" not in reply_line.classes
            assert hint.styles.color == app.query_one(meter.ContextMeter).styles.color  # the theme's muted text
            assert hint.styles.color != reply_line.styles.color

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


def test_a_personas_own_model_is_shown_and_no_override_is_sent(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    write_persona(base, "aria", 
        "name: Aria\nhandle: aria\nmodel: ollama_chat/aria-pick\n"
    )
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    calls = []

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        calls.append(model)
        return engine.TurnResult(reply="ok", session_id="s", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.persona.handle == "aria"
            assert "ollama_chat/aria-pick" in plain_text(app.query_one("#banner"))
            app.composer.focus()
            await pilot.press(*"hi", "enter")
            await pilot.pause()
            assert calls == [None]  # the engine, not the CLI, applies aria's model

    run_async(scenario())


def test_an_explicit_model_pick_beats_the_personas_own_model(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    write_persona(base, "aria", 
        "name: Aria\nhandle: aria\nmodel: ollama_chat/aria-pick\n"
    )
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/model", "enter")
            await pilot.pause()
            await pilot.press("2")
            await pilot.pause()
            banner = plain_text(app.query_one("#banner"))
            assert "Claude Sonnet 5" in banner
            assert "aria-pick" not in banner

    run_async(scenario())


def test_default_command_persists_the_current_persona(profiles):
    from sympose import profile

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/persona", "enter")
            await pilot.pause()
            await pilot.press("1")  # aria (sorted first)
            await pilot.pause()
            assert app.persona.handle == "aria"
            await pilot.press(*"/default", "enter")
            await pilot.pause()
            assert profile.resolve_default_persona() == "aria"
            lines = [plain_text(c) for c in app.transcript.children]
            assert any("@aria is now the default persona" in line for line in lines)

    run_async(scenario())


# -- TTFT beside the model (docs/decisions/013) --


def test_format_ttft_uses_ms_under_a_second_and_seconds_above():
    assert turns._format_ttft(0) == "0 ms"
    assert turns._format_ttft(734) == "734 ms"
    assert turns._format_ttft(999) == "999 ms"
    assert turns._format_ttft(1000) == "1.0s"
    assert turns._format_ttft(2349) == "2.3s"


def test_the_reply_header_shows_ttft_beside_the_model(profiles, monkeypatch):
    def fake_run_turn(handle, user_message, session_id=None, model=None):
        return engine.TurnResult(reply="ok", session_id="s", grounding=[], ttft_ms=1840, model="m")

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hi", "enter")
            await pilot.pause(0.5)
            lines = [plain_text(c) for c in app.transcript.children]
            header = next(line for line in lines if line.startswith("@samantha"))
            assert "Gemma2:9b · TTFT 1.8s" in header

    run_async(scenario())


def test_the_reply_header_omits_ttft_when_the_engine_gave_none(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hi", "enter")
            await pilot.pause(0.5)
            lines = [plain_text(c) for c in app.transcript.children]
            header = next(line for line in lines if line.startswith("@samantha"))
            assert "TTFT" not in header

    run_async(scenario())


# -- grounded notes in the reply header (docs/decisions/016) --


def _hit(path: str) -> dict:
    return {"rel_path": path, "title": "t", "heading": "", "text": "x", "tags": [], "score": 1.0, "index": 1}


def test_grounding_segment_is_empty_when_nothing_matched():
    assert grounding_line.format_grounding([], 40) == ""
    assert grounding_line.header_segment("@samantha · m", [], 100) == ""


def test_grounding_segment_names_the_top_note_and_counts_the_others():
    hits = [_hit("Projects/Atlas.md"), _hit("Projects/Atlas.md"), _hit("Work/Budget.md"), _hit("Work/Plan.md")]
    # Two passages from one note are one note, not two.
    assert grounding_line.format_grounding(hits, 60) == "from Projects/Atlas.md +2"
    assert grounding_line.format_grounding(hits[:1], 60) == "from Projects/Atlas.md"


def test_grounding_segment_cuts_a_long_path_from_the_front_so_the_filename_shows():
    hits = [_hit("Deep/Nested/Folder/Structure/Atlas.md"), _hit("Other.md")]
    # room 28, minus "from " (5) and " +1" (3), leaves 20 cells: the ellipsis and the last 19.
    assert grounding_line.format_grounding(hits, 28) == "from …/Structure/Atlas.md +1"


def test_grounding_segment_never_cuts_a_path_to_nothing_in_a_tiny_terminal():
    segment = grounding_line.format_grounding([_hit("Projects/Atlas.md")], 3)
    assert segment == "from …Atlas.md"


def test_grounding_floor_is_eight_cells_for_a_short_filename():
    # "A.md" is 4 cells; the floor of 8 binds, so 7 path cells + the ellipsis.
    assert grounding_line.format_grounding([_hit("Some/Long/Folder/A.md")], 3) == "from …er/A.md"


def test_grounding_keeps_at_most_32_cells_of_a_huge_filename():
    name = "x" * 60 + ".md"
    segment = grounding_line.format_grounding([_hit(f"Dir/{name}")], 3)
    assert segment == "from …" + name[-31:]


def test_grounding_header_segment_keeps_the_whole_line_within_the_terminal():
    header = "@samantha · Gemma2:9b · TTFT 8.3s"
    hits = [_hit("Deep/Nested/Folder/Structure/Atlas.md"), _hit("Other.md")]
    for width in (60, 72, 80, 100):
        line = header + grounding_line.header_segment(header, hits, width)
        # 4 cells stay free for the transcript's own padding and scrollbar.
        assert grounding_line.cell_len(line) <= width - 4, width


def test_a_follow_ups_rewritten_query_follows_the_note_and_is_cut_at_its_end():
    header = "@samantha · Gemma2:9b · TTFT 8.3s"
    hits = [_hit("Projects/Atlas.md")]
    line = grounding_line.header_segment(header, hits, 120, "why did we pick SQLite for Atlas")
    assert line == ' · from Projects/Atlas.md · searched "why did we pick SQLite for Atlas"'
    narrow = grounding_line.header_segment(header, hits, 100, "why did we pick SQLite for Atlas")
    assert narrow.startswith(" · from Projects/Atlas.md · searched \"why did")
    assert narrow.endswith('…"')
    assert grounding_line.cell_len(header + narrow) <= 100 - 4


def test_the_rewritten_query_is_left_out_when_there_is_no_room_and_never_shown_alone():
    header = "@samantha · Gemma2:9b · TTFT 8.3s"
    hits = [_hit("Projects/Atlas.md")]
    assert grounding_line.header_segment(header, hits, 66, "why did we pick SQLite") == " · from Projects/Atlas.md"
    assert grounding_line.header_segment(header, [], 200, "why did we pick SQLite") == ""
    from sympose import settings_store

    settings_store.set(grounding_line.SETTING, False)
    assert grounding_line.header_segment(header, hits, 200, "why did we pick SQLite") == ""


def test_the_rewritten_query_line_stays_within_the_terminal_at_any_width():
    header = "@samantha · Gemma2:9b · TTFT 8.3s"
    hits = [_hit("Deep/Nested/Folder/Structure/Atlas.md"), _hit("Other.md")]
    for width in range(40, 140):
        line = header + grounding_line.header_segment(header, hits, width, "why did we pick SQLite for the Atlas prototype")
        assert grounding_line.cell_len(line) <= max(width - 4, grounding_line.cell_len(header) + 30), width


def test_grounding_fits_wide_characters_by_cell_width_not_character_count():
    hit = _hit("プロジェクト/アトラスの決定メモ.md")
    segment = grounding_line.format_grounding([hit], 32)
    assert segment.startswith("from …") and segment.endswith("メモ.md")
    assert grounding_line.cell_len(segment) <= 32  # by characters it would be far under, by cells it is not


def test_grounding_ignores_hits_without_a_path_instead_of_failing():
    assert grounding_line.format_grounding([{"text": "x"}, {"rel_path": ""}], 40) == ""
    assert grounding_line.format_grounding([{"text": "x"}, _hit("A.md")], 40) == "from A.md"


def test_grounding_display_is_on_unless_explicitly_turned_off():
    from sympose import settings_store

    assert grounding_line.enabled() is True
    for malformed in ("false", 0, None, ""):  # hand-edited junk must not hide it
        settings_store.set(grounding_line.SETTING, malformed)
        assert grounding_line.enabled() is True
    settings_store.set(grounding_line.SETTING, False)
    assert grounding_line.enabled() is False


def _run_and_get_header(monkeypatch, grounding) -> str:
    def fake_run_turn(handle, user_message, session_id=None, model=None):
        return engine.TurnResult(
            reply="ok", session_id="s", grounding=grounding, ttft_ms=1840, model="m"
        )

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)
    header = {}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hi", "enter")
            for _ in range(100):  # wait for the reveal's first tick, however slow the machine
                await pilot.pause(0.1)
                lines = [plain_text(c) for c in app.transcript.children]
                replies = [line for line in lines if line.startswith("@samantha")]
                if replies:
                    header["text"] = replies[0].split("\n")[0]  # the header, not the reply body
                    return
            raise AssertionError("no reply header appeared")

    run_async(scenario())
    return header["text"]


def test_the_reply_header_shows_the_grounded_note_after_the_ttft(profiles, monkeypatch):
    header = _run_and_get_header(monkeypatch, [_hit("Projects/Atlas.md"), _hit("Work/Budget.md")])
    assert "TTFT 1.8s · from Projects/Atlas.md +1" in header


def test_the_reply_header_shows_nothing_when_nothing_grounded(profiles, monkeypatch):
    header = _run_and_get_header(monkeypatch, [])
    assert header.endswith("TTFT 1.8s")
    assert "no notes" not in header and "from" not in header


def test_the_reply_header_hides_grounding_when_the_knob_is_off(profiles, monkeypatch):
    from sympose import settings_store

    settings_store.set(grounding_line.SETTING, False)
    header = _run_and_get_header(monkeypatch, [_hit("Projects/Atlas.md")])
    assert header.endswith("TTFT 1.8s")


def test_grounding_command_toggles_and_persists_the_setting(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"/grounding", "enter")
            await pilot.pause()
            assert grounding_line.enabled() is False
            await pilot.press(*"/grounding", "enter")
            await pilot.pause()
            assert grounding_line.enabled() is True
            lines = [plain_text(c) for c in app.transcript.children]
            assert any("now hidden" in line for line in lines)
            assert any("now shown" in line for line in lines)

    run_async(scenario())


# -- the context-trim notice (docs/decisions/015) --


def test_trim_notice_names_how_many_turns_were_left_out():
    assert trim_notice.segment(3) == " · 3 older turns out of context"
    assert trim_notice.segment(1) == " · 1 older turn out of context"


def test_trim_notice_is_silent_when_nothing_was_left_out_or_when_turned_off():
    from sympose import settings_store

    assert trim_notice.segment(0) == ""
    settings_store.set(trim_notice.SETTING, False)
    assert trim_notice.segment(3) == ""
    settings_store.set(trim_notice.SETTING, "false")  # malformed: the notice stays on
    assert trim_notice.segment(3) != ""


def _run_with_result(monkeypatch, **fields) -> str:
    def fake_run_turn(handle, user_message, session_id=None, model=None):
        return engine.TurnResult(reply="ok", session_id="s", ttft_ms=1840, model="m", **fields)

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)
    header = {}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hi", "enter")
            for _ in range(100):
                await pilot.pause(0.1)
                replies = [plain_text(c) for c in app.transcript.children if plain_text(c).startswith("@samantha")]
                if replies:
                    header["text"] = replies[0].split("\n")[0]
                    return
            raise AssertionError("no reply header appeared")

    run_async(scenario())
    return header["text"]


def test_the_reply_header_shows_the_trim_notice_before_the_grounded_note(profiles, monkeypatch):
    header = _run_with_result(
        monkeypatch, history_dropped=3, grounding=[_hit("Projects/Atlas.md")]
    )
    # The notice comes first and takes its room; the grounded path then keeps only what fits.
    assert "TTFT 1.8s · 3 older turns out of context · from " in header
    assert header.endswith("Atlas.md")


def test_the_reply_header_shows_the_query_a_follow_up_was_rewritten_into(profiles, monkeypatch):
    header = _run_with_result(
        monkeypatch, grounding=[_hit("Projects/Atlas.md")], searched="why we picked SQLite"
    )
    # An 80-column line: the path gives up room, keeping its filename, so the query shows too.
    assert header.endswith(' · from …Atlas.md · searched "why we pick…"')


def test_the_reply_header_has_no_trim_notice_when_nothing_was_dropped(profiles, monkeypatch):
    assert "out of context" not in _run_with_result(monkeypatch, history_dropped=0)


def test_a_window_too_small_for_the_persona_is_shown_as_a_failure_line(profiles, monkeypatch):
    from sympose.engine import budget

    def too_small(handle, user_message, session_id=None, model=None):
        raise budget.ContextTooSmallError("Raise `context_window` in the settings file.")

    monkeypatch.setattr(turns.engine, "run_turn", too_small)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hi", "enter")
            await pilot.pause(0.5)
            lines = [plain_text(c) for c in app.transcript.children]
            assert any("couldn't reply" in line and "context_window" in line for line in lines)

    run_async(scenario())


def test_trim_notice_also_says_when_a_reply_was_cut_at_the_length_limit():
    assert trim_notice.segment(0, truncated=True) == " · reply cut at the length limit"
    assert trim_notice.segment(2, truncated=True) == (
        " · 2 older turns out of context · reply cut at the length limit"
    )
    assert trim_notice.segment(0, truncated=False) == ""


def test_the_reply_header_shows_a_reply_cut_at_the_length_limit(profiles, monkeypatch):
    assert "reply cut at the length limit" in _run_with_result(monkeypatch, truncated=True)


# --- the context meter (docs/decisions/018) ---


def test_the_meter_draws_a_bar_and_a_percentage_of_the_prompt_budget():
    assert meter.format_meter(0, 5000, "yellow", "red").plain == "context ░░░░░░░░░░ 0%"
    assert meter.format_meter(3100, 5000, "yellow", "red").plain == "context ██████░░░░ 62%"
    assert meter.format_meter(5000, 5000, "yellow", "red").plain == "context ██████████ 100%"


def test_the_meter_never_shows_more_than_full_or_less_than_empty():
    assert meter.format_meter(9000, 5000, "yellow", "red").plain == "context ██████████ 100%"
    assert meter.format_meter(-1000, 5000, "yellow", "red").plain == "context ░░░░░░░░░░ 0%"


def test_the_meter_reads_100_only_once_the_budget_is_reached():
    assert meter.percent(4980, 5000) == 99  # 99.6 rounds up, but the next turn still fits
    assert meter.percent(4999, 5000) == 99
    assert meter.percent(5000, 5000) == 100
    assert meter.percent(5001, 5000) == 100


def test_the_meter_rounds_to_the_nearest_percent_and_bar_cell():
    assert meter.percent(3130, 5000) == 63  # 62.6, not cut down to 62
    assert meter.format_meter(3130, 5000, "yellow", "red").plain == "context ██████░░░░ 63%"  # 6.3 cells
    assert meter.format_meter(3300, 5000, "yellow", "red").plain == "context ███████░░░ 66%"  # 6.6 cells


def _colours(text):
    return [span.style.color.name for span in text.spans]


def test_the_meter_turns_to_the_warning_colour_at_70_and_the_error_colour_at_90():
    # The colour follows the percentage as displayed.
    assert _colours(meter.format_meter(3450, 5000, "yellow", "red")) == []  # 69%
    assert _colours(meter.format_meter(3500, 5000, "yellow", "red")) == ["yellow"]  # 70%
    assert _colours(meter.format_meter(4450, 5000, "yellow", "red")) == ["yellow"]  # 89%
    assert _colours(meter.format_meter(4500, 5000, "yellow", "red")) == ["red"]  # 90%


def test_the_meter_knob_is_on_unless_explicitly_false():
    from sympose import settings_store

    assert meter.enabled() is True
    for malformed in ("false", 0, None, ""):
        settings_store.set(meter.SETTING, malformed)
        assert meter.enabled() is True
    settings_store.set(meter.SETTING, False)
    assert meter.enabled() is False


def _meter_text(app) -> str:
    return plain_text(app.query_one(meter.ContextMeter))


def _run_meter_scenario(monkeypatch, results, then=None):
    """Sends one message per entry of `results` (a TurnResult, or an exception
    to raise) and returns the meter's text after the last, plus what `then(app)` returned."""
    queue = list(results)

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)
    seen = {}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            seen["start"] = _meter_text(app)
            app.composer.focus()
            for _ in results:
                before = len([c for c in app.transcript.children])
                await pilot.press(*"hi", "enter")
                for _ in range(100):
                    await pilot.pause(0.1)
                    if len(app.transcript.children) >= before + 2 and app.pending_turns == 0:
                        break
            await pilot.pause(0.2)
            seen["text"] = _meter_text(app)
            if then:
                seen["then"] = await then(app, pilot)

    run_async(scenario())
    return seen


def _result(used, limit):
    return engine.TurnResult(reply="ok", session_id="s", ttft_ms=100, model="m", context_used=used, context_limit=limit)


def test_the_meter_is_empty_before_the_first_reply_and_filled_after_it(profiles, monkeypatch):
    seen = _run_meter_scenario(monkeypatch, [_result(3100, 5000)])
    assert seen["start"] == ""
    assert seen["text"] == "context ██████░░░░ 62%"


def test_the_meter_follows_the_latest_reply(profiles, monkeypatch):
    seen = _run_meter_scenario(monkeypatch, [_result(1000, 5000), _result(4600, 5000)])
    assert seen["text"] == "context █████████░ 92%"


def test_the_meter_stays_empty_when_the_knob_is_off_or_the_window_is_unknown(profiles, monkeypatch):
    from sympose import settings_store

    assert _run_meter_scenario(monkeypatch, [_result(None, None)])["text"] == ""
    settings_store.set(meter.SETTING, False)
    assert _run_meter_scenario(monkeypatch, [_result(3100, 5000)])["text"] == ""


def test_a_zero_budget_is_treated_as_unknown_not_divided_by(profiles, monkeypatch):
    assert _run_meter_scenario(monkeypatch, [_result(100, 0)])["text"] == ""


def test_a_failed_turn_leaves_the_meter_as_it_was(profiles, monkeypatch):
    seen = _run_meter_scenario(monkeypatch, [_result(3100, 5000), engine.EngineModelError("down")])
    assert seen["text"] == "context ██████░░░░ 62%"


def test_switching_the_model_or_the_persona_clears_the_meter(profiles, monkeypatch):
    async def switch_model(app, pilot):
        runtime.apply_picker_choice(app, "model", mock_data.MODEL_OPTIONS[1].id)
        return _meter_text(app)

    assert _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then=switch_model)["then"] == ""

    async def switch_persona(app, pilot):
        other = next(p for p in mock_data.list_personas() if p.handle != app.persona.handle)
        runtime.apply_picker_choice(app, "persona", other.handle)
        return _meter_text(app)

    write_persona(profiles, "grace", "name: Grace\nvault_folders: '*'\n")
    assert _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then=switch_persona)["then"] == ""


def _switched_while_in_flight(profiles, monkeypatch, switch):
    """Sends a message, runs `switch(app)` while its reply is still being
    produced, lets it land, and returns the meter's text."""
    write_persona(profiles, "grace", "name: Grace\nvault_folders: '*'\n")
    release = threading.Event()

    def slow_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(5)
        return _result(3100, 5000)

    monkeypatch.setattr(turns.engine, "run_turn", slow_run_turn)
    seen = {}

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()
            await pilot.press(*"hi", "enter")
            await pilot.pause(0.2)
            switch(app)
            release.set()
            for _ in range(50):
                await pilot.pause(0.1)
                if app.pending_turns == 0:
                    break
            await pilot.pause(0.2)
            seen["text"] = _meter_text(app)

    run_async(scenario())
    return seen["text"]


def test_a_reply_that_lands_after_a_persona_switch_does_not_fill_the_new_conversations_meter(
    profiles, monkeypatch
):
    def to_other_persona(app):
        other = next(p for p in mock_data.list_personas() if p.handle != app.persona.handle)
        runtime.apply_picker_choice(app, "persona", other.handle)

    assert _switched_while_in_flight(profiles, monkeypatch, to_other_persona) == ""


def test_a_reply_that_lands_after_a_model_switch_does_not_show_the_old_models_percentage(
    profiles, monkeypatch
):
    def to_other_model(app):
        runtime.apply_picker_choice(app, "model", mock_data.MODEL_OPTIONS[1].id)

    assert _switched_while_in_flight(profiles, monkeypatch, to_other_model) == ""


def test_a_reply_with_no_switch_meanwhile_does_fill_the_meter(profiles, monkeypatch):
    assert _switched_while_in_flight(profiles, monkeypatch, lambda app: None) == "context ██████░░░░ 62%"


# -- the search-index notice at the far right of the meter line (docs/decisions/027) --


def _progress(monkeypatch, value):
    from sympose.engine import semantic_refresh

    monkeypatch.setattr(semantic_refresh, "progress", lambda: value)


def test_the_notice_is_a_label_and_a_number_or_nothing(monkeypatch):
    _progress(monkeypatch, None)
    assert meter.build_notice() == ""
    _progress(monkeypatch, 0)
    assert meter.build_notice() == "indexing 0%"
    _progress(monkeypatch, 40)
    assert meter.build_notice() == "indexing 40%"


def test_with_no_reply_yet_the_notice_sits_alone_at_the_far_right(profiles, monkeypatch):
    async def then(app, pilot):
        _progress(monkeypatch, 40)
        app.query_one(meter.ContextMeter).refresh_notice()
        width = app.query_one(meter.ContextMeter).size.width
        return _meter_text(app), width

    text, width = _run_meter_scenario(monkeypatch, [], then)["then"]

    assert text.endswith("indexing 40%") and text.strip() == "indexing 40%"
    assert len(text) == width  # padded out to the right edge of the line


def test_the_notice_shares_the_line_with_the_meter_and_ends_at_the_right_edge(profiles, monkeypatch):
    async def then(app, pilot):
        _progress(monkeypatch, 40)
        app.query_one(meter.ContextMeter).refresh_notice()
        return _meter_text(app), app.query_one(meter.ContextMeter).size.width

    seen = _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then)
    text, width = seen["then"]

    assert seen["text"] == "context ██████░░░░ 62%"  # before the notice
    assert text.startswith("context ██████░░░░ 62%") and text.endswith("indexing 40%")
    assert len(text) == width and "\n" not in text


def test_the_notice_shows_even_when_the_meter_is_turned_off(profiles, monkeypatch):
    from sympose import settings_store

    settings_store.set(meter.SETTING, False)

    async def then(app, pilot):
        _progress(monkeypatch, 40)
        app.query_one(meter.ContextMeter).refresh_notice()
        return _meter_text(app)

    seen = _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then)

    assert seen["text"] == "" and seen["then"].strip() == "indexing 40%"


def test_the_notice_goes_when_the_build_ends_and_the_meter_stays(profiles, monkeypatch):
    async def then(app, pilot):
        widget = app.query_one(meter.ContextMeter)
        _progress(monkeypatch, 40)
        widget.refresh_notice()
        _progress(monkeypatch, None)
        widget.refresh_notice()
        return _meter_text(app)

    assert _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then)["then"] == "context ██████░░░░ 62%"


def test_a_reply_after_the_notice_appeared_keeps_the_notice(profiles, monkeypatch):
    async def then(app, pilot):
        widget = app.query_one(meter.ContextMeter)
        _progress(monkeypatch, 60)
        widget.refresh_notice()
        meter.show(app, 4600, 5000, meter.epoch(app))  # a later reply
        return _meter_text(app)

    text = _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then)["then"]

    assert text.startswith("context █████████░ 92%") and text.endswith("indexing 60%")


def test_the_notice_is_looked_at_on_a_timer_without_anyone_calling_it(profiles, monkeypatch):
    monkeypatch.setattr(meter, "_POLL_SECONDS", 0.05)
    _progress(monkeypatch, None)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert _meter_text(app) == ""
            _progress(monkeypatch, 25)
            await pilot.pause(0.4)
            shown = _meter_text(app).strip()
            _progress(monkeypatch, None)
            await pilot.pause(0.4)
            return shown, _meter_text(app)

    assert run_async(scenario()) == ("indexing 25%", "")


def test_in_a_terminal_too_narrow_for_both_they_stay_apart(profiles, monkeypatch):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test(size=(30, 24)) as pilot:
            await pilot.pause()
            meter.show(app, 3100, 5000, meter.epoch(app))
            _progress(monkeypatch, 40)
            app.query_one(meter.ContextMeter).refresh_notice()
            return _meter_text(app)

    assert run_async(scenario()) == "context ██████░░░░ 62%  indexing 40%"


def test_the_notice_moves_to_the_new_right_edge_when_the_terminal_is_resized(profiles, monkeypatch):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test(size=(60, 24)) as pilot:
            await pilot.pause()
            _progress(monkeypatch, 40)
            widget = app.query_one(meter.ContextMeter)
            widget.refresh_notice()
            before = (len(_meter_text(app)), widget.size.width)
            await pilot.resize_terminal(100, 24)
            await pilot.pause(0.2)
            return before, (len(_meter_text(app)), widget.size.width)

    before, after = run_async(scenario())

    assert before[0] == before[1] and after[0] == after[1] and after[1] > before[1]


def test_the_notice_has_its_own_knob_and_only_an_explicit_false_turns_it_off(monkeypatch):
    from sympose import settings_store

    _progress(monkeypatch, 40)
    assert meter.NOTICE_SETTING == "show_index_notice"
    assert meter.build_notice() == "indexing 40%"
    for malformed in ("false", 0, None, "no"):
        settings_store.set(meter.NOTICE_SETTING, malformed)
        assert meter.build_notice() == "indexing 40%"
    settings_store.set(meter.NOTICE_SETTING, False)
    assert meter.build_notice() == ""


def test_turning_the_notice_off_leaves_the_meter_and_turning_the_meter_off_leaves_the_notice(profiles, monkeypatch):
    from sympose import settings_store

    async def then(app, pilot):
        widget = app.query_one(meter.ContextMeter)
        _progress(monkeypatch, 40)
        settings_store.set(meter.NOTICE_SETTING, False)
        widget.refresh_notice()
        return _meter_text(app)

    assert _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then)["then"] == "context ██████░░░░ 62%"
    # (the reverse, the meter off and the notice on, is `test_the_notice_shows_even_when_the_meter_is_turned_off`)


def test_a_notice_already_showing_goes_when_its_knob_is_turned_off(profiles, monkeypatch):
    from sympose import settings_store

    async def then(app, pilot):
        widget = app.query_one(meter.ContextMeter)
        _progress(monkeypatch, 40)
        widget.refresh_notice()
        settings_store.set(meter.NOTICE_SETTING, False)
        widget.refresh_notice()  # what the once-a-second timer does
        return _meter_text(app)

    assert _run_meter_scenario(monkeypatch, [_result(3100, 5000)], then)["then"] == "context ██████░░░░ 62%"
