"""Routes `Input`/`OptionList` events to the picker lifecycle
(`picker.py`), real chat turns (`turns.py`), and command handling
(`runtime.py` — real for `/clear`/`/quit`, still mock for `/compact`/
`/settings`/`/history`). Kept as thin routing so none of those modules
has to depend on the others."""

from rich.style import Style
from rich.text import Text
from textual.widgets import OptionList

from sympose.cli import picker, runtime, turns
from sympose.cli import transcript as transcript_mod
from sympose.cli.commands import find_command

CHAT_TURN_WORKER_GROUP = "chat-turn"


def on_input_changed(app, value: str) -> None:
    # `composer.py`'s Tab-cycle already redrew the overlay itself (from
    # the stable `tab_matches` list, not this now-narrower filled-in
    # text) — consume one count and skip the normal live-filter reaction
    # for the `Changed` event that fill produced. A counter, not a
    # boolean: see `composer.py`'s comment on why key-repeat can queue
    # more than one of these before either is processed.
    if app.filling_tab_count > 0:
        app.filling_tab_count -= 1
        return
    if value.startswith("/"):
        picker.show_autocomplete(app, value)
    elif app.panel_kind == "autocomplete":
        picker.close_panel(app)


async def on_input_submitted(app, value: str) -> None:
    value = value.strip()
    if not value:
        return
    app.composer.value = ""
    if value.startswith("/"):
        picker.close_panel(app)
        name = value.split()[0]
        command = find_command(name)
        if command is None:
            transcript_mod.mount_line(
                app,
                Text(
                    f"Unknown command: {name} — try /help",
                    style=Style(color=app.theme_color("error", "red"), bold=True),
                ),
                "system",
            )
            return
        await runtime.run_command(app, command)
    else:
        picker.close_panel(app)
        # Dispatched as a background worker, not awaited directly here —
        # Textual's App processes one bubbled message (a keypress, a
        # picker selection) at a time, fully awaiting this handler before
        # it even looks at the next one. Awaiting `send_message` in place
        # would mean a second Enter press can't be *received* until the
        # first turn's entire engine call has already returned, making
        # message queueing (docs/decisions/008) unreachable through real
        # keypresses even though the underlying lock/queue logic is
        # correct — confirmed live, not by inspection: a diagnostic posted
        # two `Input.Submitted` messages directly and found the second
        # didn't start until the first's engine call had already
        # resolved. `exclusive=False` (the default): multiple turns must
        # be able to run at once (different personas) or wait on their own
        # per-persona lock (same persona) — never cancel each other.
        app.run_worker(turns.send_message(app, value), group=CHAT_TURN_WORKER_GROUP)


async def on_option_selected(app, event: OptionList.OptionSelected) -> None:
    if app.panel is None or event.option_list is not app.panel:
        return
    kind = app.panel_kind
    value = event.option.id
    picker.close_panel(app)
    app.composer.focus()
    if kind == "autocomplete":
        command = find_command(value) if value else None
        if command is not None:
            await runtime.run_command(app, command)
        return
    runtime.apply_picker_choice(app, kind, value)
