"""The reference-library eval: questions a user might ask about Sympose itself,
with what must reach the model, and ordinary chat that must not attach any of
the library. Written before the library's notes, so the notes are not shaped to
fit the questions. Deterministic, no model.

The library (sympose/reference/) is searched by the same retriever as a
vault (docs/decisions/014); this only measures it against its own notes. The
questions are worded the way a person asks, not the way a note is titled."""

import os
from dataclasses import dataclass
from typing import Any

from grounding_cases import CASES

from sympose.engine.grounding import retrieve
from sympose.engine.grounding_index import build_index
from sympose.vault_snapshot import get_vault_snapshot

REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "sympose", "reference")


@dataclass(frozen=True)
class RefCase:
    id: str
    message: str
    # Every substring must appear in the text the model would receive.
    find: tuple[str, ...] = ()
    # The top hit must be this note (file name), when set.
    first: str | None = None
    # Nothing at all should be grounded from the library.
    none: bool = False
    known_gap: str | None = None


REF_CASES: list[RefCase] = [
    # What it is, who made it, where it came from
    RefCase("what-is-it", "what is Sympose?", find=("Obsidian",), first="What is Sympose.md"),
    RefCase(
        "why-cheap",
        "how does Sympose keep the cost of talking to my notes down?",
        find=("model",),
        first="What is Sympose.md",
    ),
    RefCase("author", "who made Sympose?", find=("damiro",), first="What is Sympose.md"),
    RefCase(
        "when-started",
        "when was Sympose started?",
        find=("22 September 2026",),
        first="History and author.md",
    ),
    RefCase(
        "earlier-version",
        "was there an earlier version before this one?",
        find=("24 August 2026",),
        first="History and author.md",
    ),
    # Obsidian
    RefCase(
        "works-with-obsidian",
        "does Sympose work with Obsidian?",
        find=("plain markdown files",),
        first="Obsidian.md",
    ),
    RefCase(
        "obsidian-open",
        "do I have to keep Obsidian running to use it?",
        find=("does not need Obsidian",),
        first="Obsidian.md",
    ),
    RefCase(
        "skipped-folders",
        "does it read my attachments folder?",
        find=("Attachments",),
        first="Obsidian.md",
    ),
    # Setting up
    RefCase(
        "start-chatting",
        "how do I start chatting with it in the terminal?",
        find=("python -m sympose.cli",),
        first="Getting started.md",
    ),
    RefCase(
        "needs-ollama",
        "it says it can't connect to the model, what do I do?",
        find=("Ollama",),
        first="Troubleshooting.md",
    ),
    RefCase(
        "first-reply-slow",
        "why is the first reply so slow?",
        find=("loads",),
        first="Troubleshooting.md",
    ),
    RefCase(
        "add-second-vault",
        "how do I add a second vault?",
        find=("VAULT_PATHS",),
        first="Add or switch vaults.md",
    ),
    RefCase(
        "switch-vault-in-terminal",
        "can I change vault from the terminal?",
        find=("dashboard",),
        first="Add or switch vaults.md",
    ),
    # Personas
    RefCase(
        "create-persona",
        "how do I create a new persona?",
        find=("persona.yaml",),
        first="Personas.md",
    ),
    RefCase(
        "soul-file",
        "what goes in a soul file?",
        find=("voice",),
        first="Personas.md",
    ),
    RefCase(
        "default-persona",
        "how do I make a different persona the default?",
        find=("/default",),
        first="Personas.md",
        known_gap="The right passage is returned, but a model note ranks first: 'different' "
        "and 'default' both appear under 'How do I switch to a different model?'. A ranking "
        "weakness of shared ordinary words, not a missing answer.",
    ),
    RefCase(
        "persona-folders",
        "can I stop a persona from seeing some of my folders?",
        find=("vault_folders",),
        first="Personas.md",
    ),
    # Models
    RefCase(
        "default-model",
        "which model does it use out of the box?",
        find=("gemma2:9b",),
        first="Choosing a model.md",
    ),
    RefCase(
        "change-model",
        "how do I switch to a different model?",
        find=("/model",),
        first="Choosing a model.md",
    ),
    # Commands and settings
    RefCase(
        "list-commands",
        "what commands can I type in the chat?",
        find=("/quit",),
        first="Chat commands.md",
    ),
    RefCase(
        "settings-file",
        "where are my settings stored?",
        find=("settings.json",),
        first="Settings.md",
    ),
    RefCase(
        "turn-off-followups",
        "how do I turn off the extra search she does for follow-up questions?",
        find=("grounding_followups",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "context-window-setting",
        "what does the context_window setting do?",
        find=("context_window",),
        first="Settings.md",
    ),
    # How it uses notes, the header, the meter
    RefCase(
        "header-from",
        "what does the from part in the reply header mean?",
        find=("grounded",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "hide-notes-line",
        "how do I hide which notes she used?",
        find=("/grounding",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "meter",
        "what does the percentage under the chat box mean?",
        find=("older turns",),
        first="The context meter.md",
    ),
    RefCase(
        "older-turns-out",
        "what does 'older turns out of context' mean?",
        find=("older turns",),
        first="The context meter.md",
    ),
    # Privacy, storage
    RefCase(
        "where-conversations",
        "where are my conversations stored?",
        find=("sessions",),
        first="Privacy and data.md",
    ),
    RefCase(
        "leaves-computer",
        "does anything I write leave my computer?",
        find=("Ollama",),
        first="Privacy and data.md",
    ),
    # The dashboard
    RefCase(
        "nebula",
        "what is the Knowledge Nebula?",
        find=("graph",),
        first="The dashboard.md",
    ),
    RefCase(
        "deleted-note",
        "how do I get back a note I deleted?",
        find=("trash",),
        first="The dashboard.md",
    ),
    # What it cannot do: an honest "not yet" is part of the library
    RefCase(
        "slack",
        "does Sympose work in Slack?",
        find=("Slack",),
        first="Not built yet.md",
    ),
    RefCase(
        "session-logs-review",
        "arent you supposed to review our session logs?",
        find=("never reads them",),
        first="Not built yet.md",
    ),
    RefCase(
        "history-and-logs-pressed",
        "theres history and session logs for you to know what we talked last time. arent you aware of that?",
        find=("never reads them",),
        first="Not built yet.md",
    ),
    RefCase(
        "remembers-last-conversation",
        "does Samantha remember our last conversation?",
        find=("recaps",),
        first="Not built yet.md",
    ),
    RefCase(
        "where-recaps-live",
        "where are the recaps of my conversations kept?",
        find=("profiles/<handle>/recaps/",),
        first="Privacy and data.md",
    ),
    RefCase(
        "turn-off-recaps",
        "how do I turn off the recaps?",
        find=("session_recaps",),  # the setting's own section and the privacy answer both say it
    ),
    RefCase(
        "writes-notes",
        "can Samantha write or edit my notes for me in the chat?",
        find=("cannot",),
        first="Not built yet.md",
    ),
    # Ordinary chat must attach nothing from the library
    RefCase("small-talk", "hey, how are you today?", none=True),
    RefCase("rough-day", "hey. rough day, my brain is completely fried", none=True),
    RefCase("thanks", "thanks, that helps!", none=True),
    RefCase("about-a-word-in-both", "which flights did I book for Lisbon?", none=True),
    RefCase("topic-change", "ok let's talk about something else", none=True),
    # Two words of a note's title in ordinary chat are one signal, not two.
    RefCase("title-words-in-chat", "I'm getting started on my taxes", none=True),
]

# Every message the vault eval already uses must attach nothing from the
# library, except the one that really is about Sympose.
_ABOUT_SYMPOSE = {"a-request-matching-only-ordinary-words-grounds-nothing"}
VAULT_QUESTIONS_MUST_NOT_ATTACH: list[RefCase] = [
    RefCase(f"vault-{c.id}", c.message, none=True)
    for c in CASES
    if c.id not in _ABOUT_SYMPOSE
]


def ground_reference(message: str) -> list[dict[str, Any]]:
    root = os.path.abspath(REFERENCE_DIR)
    return retrieve(build_index(get_vault_snapshot(root, [root])), message, strict=True)


def run_ref_case(case: RefCase) -> str | None:
    """`None` when the case passes, else a one-line reason."""
    hits = ground_reference(case.message)
    names = [os.path.basename(h["rel_path"]) for h in hits]
    if case.none:
        return None if not hits else f"expected nothing, got {names}"
    blob = "\n".join(h["text"] for h in hits)
    for needle in case.find:
        if needle not in blob:
            return f"missing {needle!r} in what the model would see ({names})"
    if case.first and (not names or names[0] != case.first):
        return f"top hit was {names[:1]}, wanted {case.first!r}"
    return None
