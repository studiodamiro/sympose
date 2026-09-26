"""What a cloud model may receive, in the CLI (docs/decisions/031): the `/share` picker, the
notice when a cloud model is in use, and the reply header's `cloud:` and `withheld:` segments.
What is allowed lives in `sympose.engine.sharing`; this only asks and shows."""

from sympose.cli import picker, transcript as transcript_mod
from sympose.cli.mock_data import ModelOption, active_model
from sympose.cli.selection import SelectionOption
from sympose.engine import sharing

PICKER_KIND = "share"


def is_cloud(model: ModelOption) -> bool:
    return not sharing.is_local(model.id)


def options() -> list[SelectionOption]:
    """One row per category, with whether cloud models may receive it now; choosing a row flips it."""
    chosen = sharing.approved()
    return [
        SelectionOption(
            f"{name} — {'shared' if name in chosen else 'not shared'}: {sharing.DESCRIPTIONS[name]}", name
        )
        for name in sharing.CATEGORIES
    ]


async def open_picker(app) -> None:
    await picker.open_picker(app, PICKER_KIND, "Cloud models may receive (Esc when done)", options())


def toggle(app, category: str) -> None:
    """Flip `category` and say what it is now."""
    turned_on = category not in sharing.approved()
    if sharing.set_approved(category, turned_on):
        line = f"Cloud models {'may now' if turned_on else 'may no longer'} receive {sharing.DESCRIPTIONS[category]}."
    else:
        line = "Couldn't save the cloud-sharing setting."
    transcript_mod.mount_line(app, line, "system")


def notice(model: ModelOption) -> str:
    """What `model`, a cloud model, receives: always the messages, and from the vault what is allowed."""
    allowed = [name for name in sharing.CATEGORIES if name in sharing.approved()]
    vault = ", ".join(allowed) if allowed else "nothing"
    return (
        f"{model.short} is a cloud model: it receives your messages and this conversation. "
        f"From your vault it may receive: {vault}. Change this with /share."
    )


def announce(app) -> None:
    """Say what the model in use may receive, when it is a cloud model (at start-up, and when a
    persona with a cloud model of its own is chosen)."""
    model = active_model(app.persona, app.model_override)
    if is_cloud(model):
        transcript_mod.mount_line(app, notice(model), "system")


def should_ask(app) -> bool:
    """A cloud model is in use and some category has not been approved: offer the choice."""
    return is_cloud(active_model(app.persona, app.model_override)) and len(sharing.approved()) < len(sharing.CATEGORIES)


def header_segment(cloud: list[str], withheld: list[str]) -> str:
    """` · cloud: notes, recaps · withheld: properties` for a cloud turn, `""` when the turn was local or
    nothing of the vault was involved."""
    parts = [f"{label}: {', '.join(names)}" for label, names in (("cloud", cloud), ("withheld", withheld)) if names]
    return "".join(f" · {part}" for part in parts)
