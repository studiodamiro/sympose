"""Slash-command handling and applying a picker's selection. `/clear` and
`/quit` are real, concurrency-aware (they check `pending_turns`/
`turn_locks`/`active_reply_timers`, state `turns.py`/`app.py` own);
`/compact`/`/settings`/`/history` are still canned — no session/history
data model exists yet. Persona-switch continuity (`session_id`/
`session_generation` reset in `apply_picker_choice`) is also real state
that `turns.py`'s generation-guard logic depends on, not mock behavior.
The chat-turn dispatch/streaming path itself lives in `turns.py`, split
out to hold the 200-LOC-per-file cap."""

from rich.style import Style

from sympose import engine
from sympose.cli import grounding_line, meter, picker, transcript as transcript_mod
from sympose.cli.commands import COMMANDS
from sympose.cli.mock_data import MOCK_HISTORY, MODEL_OPTIONS, list_personas
from sympose.cli.selection import SelectionOption
from sympose.profile import set_default_persona


async def run_command(app, command) -> None:
    transcript = app.transcript
    if command.name == "/help":
        transcript_mod.mount_line(app, "Commands:", "system")
        for c in COMMANDS:
            color = app.theme_color("error", "red") if c.danger else app.theme_color("primary", "cyan")
            line = transcript_mod.styled_line(f"  {c.name:<10}", Style(color=color, bold=True), c.summary)
            transcript_mod.mount_line(app, line, "system")
    elif command.name == "/model":
        await picker.open_picker(
            app, "model", "Select a model", [SelectionOption(m.label, m.id) for m in MODEL_OPTIONS]
        )
    elif command.name == "/persona":
        await picker.open_picker(
            app,
            "persona",
            "Select a persona",
            [
                SelectionOption(f"{p.name} — {p.title}" if p.title else p.name, p.handle)
                for p in list_personas()
            ],
        )
    elif command.name == "/default":
        if set_default_persona(app.persona.handle):
            line = f"@{app.persona.handle} is now the default persona."
        else:
            line = f"Couldn't save @{app.persona.handle} as the default persona."
        transcript_mod.mount_line(app, line, "system")
    elif command.name == "/grounding":
        turned_on = not grounding_line.enabled()
        if grounding_line.set_enabled(turned_on):
            line = f"Grounded notes are now {'shown' if turned_on else 'hidden'} in reply headers."
        else:
            line = "Couldn't save the grounded-notes setting."
        transcript_mod.mount_line(app, line, "system")
    elif command.name == "/history":
        await picker.open_picker(
            app, "history", "Recent conversations", [SelectionOption(e, e) for e in MOCK_HISTORY]
        )
    elif command.name == "/compact":
        transcript_mod.mount_line(app, "Conversation compacted (mock) — nothing to trim yet.", "system")
    elif command.name == "/clear":
        # A turn that's queued or still running its engine call has no
        # reply widget yet — clearing now would wipe its "You" line, so
        # when that turn later resolves the reply would mount with no
        # visible question above it. `pending_turns`, not a lock's
        # `.locked()`, is what `action_quit` already uses for this same
        # in-flight check (docs/decisions/008); a turn's own streaming
        # reveal (below) only starts after `pending_turns` has already
        # dropped back to 0, so this can't also block a plain clear during
        # an active stream.
        if app.pending_turns > 0:
            transcript_mod.mount_line(
                app, "Can't clear while a reply is queued or in progress.", "system"
            )
        else:
            # A reply may still be mid-stream — stop its timer rather than
            # let it keep ticking against a transcript that was just cleared
            # out from under it. Two or more replies can be streaming at once
            # (docs/decisions/008 — one lock per persona), so every active
            # timer is stopped, not just one slot's worth.
            for timer in app.active_reply_timers:
                timer.stop()
            app.active_reply_timers.clear()
            await transcript.remove_children()
            app.last_speaker = None
    elif command.name == "/settings":
        # No dashboard-style Settings page exists in a terminal, so unlike
        # the dashboard's `/settings` (wired to real navigation), this
        # stays inert-by-default.
        transcript_mod.mount_line(
            app, "Settings aren't available in the CLI yet — this is a mock.", "system"
        )
    elif command.name == "/quit":
        # `app.action_quit` (also Textual's own ctrl+q/command-palette
        # quit route) has the in-flight-aware fast-exit check — one place
        # for it, not duplicated here too.
        await app.action_quit()
        return
    transcript.scroll_end(animate=False)


def apply_picker_choice(app, kind: str, value: str | None) -> None:
    transcript = app.transcript
    if kind == "model":
        model = next((m for m in MODEL_OPTIONS if m.id == value), None)
        if model is not None:
            app.model_override = model
            meter.clear(app)  # the old figure was measured against the previous window
            picker.update_banner(app)
            transcript_mod.mount_line(app, f"Switched model to {model.label}.", "system")
    elif kind == "persona":
        persona = next((p for p in list_personas() if p.handle == value), None)
        if persona is not None and persona.handle != app.persona.handle:
            app.persona = persona
            # Sessions are stored per-handle (sympose/engine/session.py) — an
            # old session_id from the previous persona would resolve to a
            # different persona's directory under the new handle (nothing
            # there, silently empty history) while still writing new turns
            # under the old id, forking/losing history across the switch.
            # A new persona starts a fresh session, same as a fresh process.
            app.session_id = None
            app.session_generation += 1
            meter.clear(app)  # a fresh session starts empty
            picker.update_banner(app)
            engine.refresh_recaps(persona.handle)  # ADR 023
            transcript_mod.mount_line(app, f"Now talking to @{persona.handle}.", "system")
    elif kind == "history":
        transcript_mod.mount_line(
            app, "History browsing isn't wired up yet — this is a placeholder.", "system"
        )
    transcript.scroll_end(animate=False)
