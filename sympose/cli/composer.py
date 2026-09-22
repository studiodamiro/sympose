"""The composer `Input` — a thin subclass adding Tab/Shift+Tab as the
`/`-command cycle-and-fill shortcut. A plain `Input` doesn't bind Tab
itself, so without this the key falls through to the Screen's default
focus-cycling binding — which is what sent focus wandering off into the
transcript before this existed, since Textual checks a focused widget's
own bindings before walking up to its ancestors'."""

from textual.binding import Binding
from textual.widgets import Input

from sympose.cli import picker
from sympose.cli.commands import matching_commands


class ComposerInput(Input):
    BINDINGS = [
        Binding("tab", "cycle_command(1)", show=False),
        Binding("shift+tab", "cycle_command(-1)", show=False),
    ]

    def action_cycle_command(self, direction: int) -> None:
        if not self.value.startswith("/"):
            return
        app = self.app
        if app.tab_matches is None:
            matches = matching_commands(self.value)
            if not matches:
                return
            app.tab_matches = matches
            app.tab_index = -1
        app.tab_index = (app.tab_index + direction) % len(app.tab_matches)
        target = app.tab_matches[app.tab_index]
        if target.name != self.value:
            # A *counter*, not a boolean — key-repeat (holding Tab down)
            # can queue a second `Key(tab)` before this fill's `Changed`
            # message is delivered, so `action_cycle_command` runs twice
            # before `dispatch.on_input_changed` runs once. A boolean
            # would be reset by the first `Changed` and leave the second
            # one wrongly treated as real typing — which resets
            # `tab_matches` mid-cycle and traps the cycle on one command.
            # Only incrementing when the value actually changes keeps
            # this in lockstep with the number of `Changed` messages
            # Textual will actually post (a same-value assignment posts
            # none).
            app.filling_tab_count += 1
            self.value = target.name
            self.cursor_position = len(target.name)
        picker.render_tab_cycle(app)
