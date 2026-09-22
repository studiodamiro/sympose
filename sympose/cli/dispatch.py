"""Routes `Input`/`OptionList` events to the picker lifecycle
(`picker.py`) and the actual mock behavior (`runtime.py`). Kept as thin
routing so neither of those two modules has to depend on the other."""

from rich.style import Style
from rich.text import Text
from textual.widgets import OptionList, Static

from sympose.cli import picker, runtime
from sympose.cli.commands import find_command


def on_input_changed(app, value: str) -> None:
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
            app.transcript.mount(
                Static(
                    Text(
                        f"Unknown command: {name} — try /help",
                        style=Style(color=app.theme_color("error", "red"), bold=True),
                    )
                )
            )
            return
        await runtime.run_command(app, command)
    else:
        picker.close_panel(app)
        runtime.send_message(app, value)


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
