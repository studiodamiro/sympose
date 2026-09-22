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
        f"[bold]<S> Sympose[/] — talking to [bold]@{app.persona.handle}[/] "
        f"· [dim]{app.model.label}[/]"
    )


def _sync_composer_spacing(app) -> None:
    # The composer's top margin (breathing room above the input) only
    # belongs there when the transcript is what's directly above it — an
    # open picker/autocomplete panel should read as part of the same
    # input interaction, not a separate block with a gap before the
    # input like the transcript gets.
    app.composer.set_class(app.panel is None, "composer-spaced")


def close_panel(app) -> None:
    if app.panel is not None:
        app.panel.remove()
    app.panel = None
    app.panel_kind = None
    _sync_composer_spacing(app)


async def open_picker(app, kind: str, title: str, options: list[SelectionOption]) -> None:
    """Mounts a focused picker — digit-key selection applies while it
    holds focus, per `selection.py`'s scoping rule."""
    close_panel(app)
    panel = SelectionPanel(title, options)
    app.panel = panel
    app.panel_kind = kind
    await app.mount(panel, before="#composer")
    panel.focus()
    _sync_composer_spacing(app)


def show_autocomplete(app, value: str) -> None:
    """Live `/`-command preview, filtered on every real keystroke. The
    `Input` keeps focus throughout — unnumbered (see `selection.py`),
    cycled with Tab/Shift+Tab (`composer.py`) rather than digits, and
    with no row highlighted yet since nothing's been cycled to."""
    app.tab_matches = None
    app.tab_index = -1
    matches = matching_commands(value)
    if not matches:
        if app.panel_kind == "autocomplete":
            close_panel(app)
        return
    _render_commands(app, matches, highlighted=-1)


def render_tab_cycle(app) -> None:
    """Redraws the autocomplete overlay from `app.tab_matches`/
    `app.tab_index` (owned by `composer.py`'s cycle action) rather than
    recomputing from the input's current text — the text now holds
    whichever command Tab just filled in, which is narrower than the
    original typed prefix and would otherwise collapse the list to just
    that one command instead of letting Tab keep cycling through all of
    them."""
    _render_commands(app, app.tab_matches, highlighted=app.tab_index)


def _render_commands(app, matches, highlighted: int) -> None:
    close_panel(app)
    options = [
        SelectionOption(f"{c.name} — {c.summary}", c.name, danger=c.danger) for c in matches
    ]
    panel = SelectionPanel("Commands", options, numbered=False, initial_highlight=highlighted)
    app.panel = panel
    app.panel_kind = "autocomplete"
    app.mount(panel, before="#composer")
    _sync_composer_spacing(app)
