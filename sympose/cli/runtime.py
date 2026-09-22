"""What actually happens once a command or message is dispatched: mock
slash-command behavior, and the canned chat reply "streaming" into the
transcript via a repeating timer — the one piece worth previewing live
above all else, since it's the thing legacy's blocking input loop
couldn't do. No engine underneath yet, so all of this is canned."""

from rich.style import Style
from rich.text import Text

from sympose.cli import picker, transcript as transcript_mod
from sympose.cli.commands import COMMANDS
from sympose.cli.mock_data import MOCK_HISTORY, MOCK_MODELS, MOCK_REPLIES, list_personas
from sympose.cli.selection import SelectionOption


async def run_command(app, command) -> None:
    transcript = app.transcript
    if command.name == "/help":
        transcript_mod.mount_line(app, "Commands:", "system")
        for c in COMMANDS:
            color = app.theme_color("error", "red") if c.danger else app.theme_color("primary", "cyan")
            line = Text()
            line.append(f"  {c.name:<10}", style=Style(color=color, bold=True))
            line.append(c.summary)
            transcript_mod.mount_line(app, line, "system")
    elif command.name == "/model":
        await picker.open_picker(
            app, "model", "Select a model", [SelectionOption(m.label, m.id) for m in MOCK_MODELS]
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
    elif command.name == "/history":
        await picker.open_picker(
            app, "history", "Recent conversations", [SelectionOption(e, e) for e in MOCK_HISTORY]
        )
    elif command.name == "/compact":
        transcript_mod.mount_line(app, "Conversation compacted (mock) — nothing to trim yet.", "system")
    elif command.name == "/clear":
        # A reply may still be mid-stream — stop its timer rather than
        # let it keep ticking against a transcript that was just
        # cleared out from under it (it would otherwise keep updating
        # a detached widget and scrolling the transcript for up to the
        # rest of the reply's length).
        if app.reply_timer is not None:
            app.reply_timer.stop()
            app.reply_timer = None
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
        app.exit()
        return
    transcript.scroll_end(animate=False)


def apply_picker_choice(app, kind: str, value: str | None) -> None:
    transcript = app.transcript
    if kind == "model":
        model = next((m for m in MOCK_MODELS if m.id == value), None)
        if model is not None:
            app.model = model
            picker.update_banner(app)
            transcript_mod.mount_line(app, f"Switched model to {model.label}.", "system")
    elif kind == "persona":
        persona = next((p for p in list_personas() if p.handle == value), None)
        if persona is not None:
            app.persona = persona
            picker.update_banner(app)
            transcript_mod.mount_line(app, f"Now talking to @{persona.handle}.", "system")
    elif kind == "history":
        transcript_mod.mount_line(
            app, "History browsing isn't wired up yet — this is a placeholder.", "system"
        )
    transcript.scroll_end(animate=False)


def send_message(app, value: str) -> None:
    transcript = app.transcript
    line = Text()
    line.append("You  ", style=Style(bold=True, dim=True))
    line.append(value)
    transcript_mod.mount_line(app, line, "user")
    transcript.scroll_end(animate=False)
    reply = MOCK_REPLIES[app.reply_count % len(MOCK_REPLIES)]
    app.reply_count += 1
    _stream_reply(app, reply)


def _stream_reply(app, reply: str) -> None:
    transcript = app.transcript
    accent = app.theme_color("accent", "cyan")
    header = f"@{app.persona.handle} · {app.model.short}"
    reply_widget = transcript_mod.mount_line(app, "", "persona")
    words = reply.split(" ")
    shown = {"count": 0}

    def tick() -> None:
        # Defensive: the widget can be gone before the timer is (e.g. a
        # teardown path that doesn't go through `/clear`'s explicit
        # `app.reply_timer.stop()`), so bail rather than update/scroll a
        # detached widget.
        if not reply_widget.is_mounted:
            timer.stop()
            return
        shown["count"] += 1
        body = " ".join(words[: shown["count"]])
        done = shown["count"] >= len(words)
        text = Text()
        text.append(header + "\n", style=Style(color=accent, bold=True))
        text.append(body + ("" if done else " ▋"))
        reply_widget.update(text)
        transcript.scroll_end(animate=False)
        if done:
            timer.stop()
            app.reply_timer = None

    timer = app.set_interval(0.05, tick)
    app.reply_timer = timer
