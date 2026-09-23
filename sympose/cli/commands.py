"""The slash-command registry. `/clear` and `/quit` are real, wired to
the actual engine's concurrency state (docs/decisions/008); `/compact`,
`/settings`, and `/history` are still inert mocks — nothing backs them
yet (see `runtime.py`'s `run_command`)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    name: str  # e.g. "/help", matched case-insensitively
    summary: str
    # Color-coded $error in listings — a destructive/reset action, not a
    # neutral one (mirrors `selection.SelectionOption.danger`).
    danger: bool = False


COMMANDS: list[SlashCommand] = [
    SlashCommand("/help", "List available commands"),
    SlashCommand("/model", "Switch the active model"),
    SlashCommand("/persona", "Switch the active persona"),
    SlashCommand("/default", "Make the current persona the default"),
    SlashCommand("/grounding", "Show or hide which notes grounded a reply"),
    SlashCommand("/history", "Browse past conversations (placeholder)"),
    SlashCommand("/compact", "Compact the conversation (mock)"),
    SlashCommand("/clear", "Clear the transcript", danger=True),
    SlashCommand("/settings", "Open settings (not available in the CLI yet)"),
    SlashCommand("/quit", "Exit the CLI"),
]


def matching_commands(prefix: str) -> list[SlashCommand]:
    """Commands whose name starts with `prefix` — feeds the live
    `/`-autocomplete overlay as more of the command is typed."""
    needle = prefix.lower()
    return [c for c in COMMANDS if c.name.startswith(needle)]


def find_command(name: str) -> SlashCommand | None:
    needle = name.lower()
    return next((c for c in COMMANDS if c.name == needle), None)
