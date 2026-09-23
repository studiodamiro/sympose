"""Tests for the `sympose/cli/` Textual mock — the slash-command
registry and persona lookup as plain unit tests, and the interactive
behavior (pickers, autocomplete, digit-select scoping) driven through
Textual's headless pilot. `pytest-asyncio` isn't a declared dependency
here, so each async scenario is run via a small `run_async` helper
instead of an `async def` test function."""

import asyncio
import threading

import pytest

from sympose import engine
from sympose.cli import commands, mock_data, runtime, turns
from sympose.cli.app import SymposeCLI


def run_async(coro):
    return asyncio.run(coro)


def plain_text(static) -> str:
    content = static.content
    return content.plain if hasattr(content, "plain") else str(content)


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
            # The local model is index 0 (default) since the picker's
            # ordering must match the engine's own local-first default
            # (docs/decisions/007) — pick option 2 to actually switch.
            app.composer.focus()
            await pilot.press(*"/model", "enter")
            await pilot.pause()
            assert app.panel_kind == "model"
            await pilot.press("2")
            await pilot.pause()
            assert app.model.id == "anthropic/claude-sonnet-5"
            assert app.panel is None  # closed after selection
            banner = plain_text(app.query_one("#banner"))
            assert "Claude Sonnet 5" in banner

    run_async(scenario())


def test_default_model_is_the_local_one(profiles):
    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.model.id == mock_data.MOCK_MODELS[0].id
            assert app.model.id.startswith("ollama_chat/")

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
            assert calls == [("samantha", "hello", None, app.model.id)]
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


def test_quit_while_a_call_is_in_flight_force_exits_instead_of_hanging(profiles, monkeypatch):
    """Regression test, confirmed live before this fix: `/quit` calling
    graceful `app.exit()` while a model call is still in flight doesn't
    hang the app, it hangs the whole *process* — a thread already running
    a blocking network call can't be cancelled
    (`concurrent.futures.Future.cancel()` only works before a worker
    picks the work up), so the coroutine awaiting it blocks until that
    thread naturally finishes or times out before asyncio's own shutdown
    can even proceed, up to `model._REQUEST_TIMEOUT_SECONDS`. `/quit`
    must instead call `_force_exit` (an immediate, un-gracefully process
    exit) whenever `app.turn_locks` is held, skipping the graceful path
    entirely rather than waiting on it."""
    release = threading.Event()
    force_exit_called = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="late reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)
    monkeypatch.setattr(turns, "_force_exit", force_exit_called.set)

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

            assert force_exit_called.is_set()
            assert app._exit is not True  # the graceful path was skipped, not taken

            release.set()
            await task  # must not raise

    run_async(scenario())


def test_app_exit_while_a_call_is_in_flight_does_not_crash_on_resume(profiles, monkeypatch):
    """`send_message`'s own `if app._exit: return` guards, kept as
    defense-in-depth even though `/quit` itself now always routes a
    locked-lock quit through `_force_exit` instead (see the test above) —
    this exercises what happens if `app.exit()` is ever reached some other
    way (a future keybinding, Textual's own default quit handling) while a
    call is still in flight: the resuming coroutine must notice and bail
    out instead of touching the transcript/timer of an already-exiting
    app, not raise the `MountError` this was originally written to fix."""
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

            app.exit()  # bypassing /quit's own pending_turns check entirely
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


def test_ctrl_q_while_a_call_is_in_flight_also_force_exits(profiles, monkeypatch):
    """Regression test: Textual's default ctrl+q binding (and its
    command-palette Quit entry) both call `App.action_quit` directly,
    bypassing `/quit`'s own pending_turns check entirely — reintroducing
    the exact hang that check exists to prevent, through a different exit
    route this app never overrode until now."""
    release = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="late reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)
    force_exit_called = threading.Event()
    monkeypatch.setattr(turns, "_force_exit", force_exit_called.set)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.composer.focus()

            task = asyncio.create_task(turns.send_message(app, "hello"))
            await asyncio.sleep(0.05)
            assert app.turn_locks["samantha"].locked()

            await app.action_quit()  # what ctrl+q/the command palette call

            assert force_exit_called.is_set()
            assert app._exit is not True

            release.set()
            await task

    run_async(scenario())


def test_quit_while_a_second_message_is_queued_but_not_yet_started_force_exits(
    profiles, monkeypatch
):
    """Distinct from the test above: here a second message for the same
    persona is queued (waiting on the lock, never yet dispatched to the
    engine at all) when `/quit` fires. `action_quit`'s `pending_turns`
    check must still catch this, generalizing correctly to a multi-queued
    case rather than only the single in-flight call it was originally
    written against."""
    release = threading.Event()
    force_exit_called = threading.Event()

    def fake_run_turn(handle, user_message, session_id=None, model=None):
        release.wait(timeout=2)
        return engine.TurnResult(reply="late reply", session_id="sess-x", grounding=[])

    monkeypatch.setattr(turns.engine, "run_turn", fake_run_turn)
    monkeypatch.setattr(turns, "_force_exit", force_exit_called.set)

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

            assert force_exit_called.is_set()

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


def test_action_quit_reads_pending_turns_not_lock_state(profiles, monkeypatch):
    """Directly exercises `action_quit`'s own decision, independent of any
    real lock: sets `pending_turns` by hand with every `turn_locks` entry
    left unlocked, and confirms `_force_exit` still fires. A test that only
    drives this through a genuinely in-flight `send_message` call (as the
    other quit tests do) can't distinguish `action_quit` reading
    `pending_turns` from it reading `any(lock.locked() ...)` — both happen
    to agree whenever nothing is mid-release. This one pins the actual
    check `action_quit` makes."""
    force_exit_called = threading.Event()
    monkeypatch.setattr(turns, "_force_exit", force_exit_called.set)

    async def scenario():
        app = SymposeCLI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not any(lock.locked() for lock in app.turn_locks.values())

            app.pending_turns = 1  # no real lock held anywhere
            await app.action_quit()

            assert force_exit_called.is_set()
            assert app._exit is not True

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
