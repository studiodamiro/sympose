"""Picker lifecycle: the banner, and mounting/closing a `SelectionPanel`
— either focused (the `/model`/`/persona`/`/history` pickers, where digit
keys should select a row) or unfocused (the live `/`-autocomplete preview,
where the `Input` keeps focus so the user can keep typing). Split out of
`dispatch.py`/`runtime.py` so both can depend on this without depending on
each other."""

from textual.widgets import Static

from sympose.cli.commands import matching_commands
from sympose.cli.selection import SelectionOption, SelectionPanel


def update_banner(app) -> None:
    banner = app.query_one("#banner", Static)
    banner.update(
        f"[bold]Sympose[/] — talking to [bold]@{app.persona.handle}[/] "
        f"· [dim]{app.model.label}[/]"
    )


def close_panel(app) -> None:
    if app.panel is not None:
        app.panel.remove()
    app.panel = None
    app.panel_kind = None


async def open_picker(app, kind: str, title: str, options: list[SelectionOption]) -> None:
    """Mounts a focused picker — digit-key selection applies while it
    holds focus, per `selection.py`'s scoping rule."""
    close_panel(app)
    panel = SelectionPanel(title, options)
    app.panel = panel
    app.panel_kind = kind
    await app.mount(panel, before="#composer")
    panel.focus()


def show_autocomplete(app, value: str) -> None:
    """Live `/`-command preview, filtered as more is typed. The `Input`
    keeps focus throughout, so digit keys still type into it rather than
    selecting a row — the same scoping rule `open_picker` relies on."""
    matches = matching_commands(value)
    if not matches:
        if app.panel_kind == "autocomplete":
            close_panel(app)
        return
    close_panel(app)
    options = [
        SelectionOption(f"{c.name} — {c.summary}", c.name, danger=c.danger) for c in matches
    ]
    panel = SelectionPanel("Commands", options)
    app.panel = panel
    app.panel_kind = "autocomplete"
    app.mount(panel, before="#composer")
