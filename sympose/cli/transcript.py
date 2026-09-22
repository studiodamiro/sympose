"""Mounts a line into the transcript with speaker-aware spacing:
consecutive lines from the same "chatter" (user / persona / system) sit
close together, and a blank-line gap only appears when the chatter
changes — the grouped-messages convention ordinary chat apps use,
rather than a flat gap after every single line regardless of who's
talking."""

from textual.widgets import Static


def mount_line(app, content, speaker: str) -> Static:
    # `app.last_speaker` starts `None` (no prior turn), so the very
    # first line ever mounted must not get a gap above it even though
    # `speaker != None` — there's nothing above it to separate from.
    changed = app.last_speaker is not None and speaker != app.last_speaker
    widget = Static(content, classes="turn-gap" if changed else "")
    app.transcript.mount(widget)
    app.last_speaker = speaker
    return widget
