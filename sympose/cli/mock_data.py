"""Canned data for the CLI mock. Personas are a real read through
`sympose/profile.py` and `profiles/*.yaml` — the same "functional but
mock" split the dashboard's persona picker uses (real data, just little of
it configured yet). Models, chat history, and reply text have no backing
store anywhere yet, so those stay hardcoded until the engine exists."""

import glob
import os
from dataclasses import dataclass

from sympose.profile import get_profile, profiles_dir


@dataclass(frozen=True)
class PersonaOption:
    handle: str
    name: str
    title: str


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    # Short name for the streamed-reply header (`runtime.py`) — a
    # dedicated field rather than parsing it back out of `label`, which
    # is free-form display text with no guaranteed structure.
    short: str


def list_personas() -> list[PersonaOption]:
    """Every configured `profiles/*.yaml` handle, loaded through
    `profile.get_profile` rather than read directly, so a malformed or
    unsafe file is handled the same way the vault routes already handle
    it. Falls back to just "samantha" if the profiles directory doesn't
    exist yet, matching `get_profile`'s own fallback.

    Handles are lowercased — `get_profile` itself lowercases the handle
    before building a file path, so a `Samantha.yaml` on disk is still
    read as "samantha"; without lowering it here too, the two would
    disagree (this picker showing "Samantha", the default-persona lookup
    in `app.py` comparing against the lowercase literal and missing)."""
    base = profiles_dir()
    handles = sorted(
        {
            os.path.splitext(os.path.basename(path))[0].lower()
            for path in glob.glob(os.path.join(base, "*.yaml"))
        }
    )
    if not handles:
        handles = ["samantha"]
    options = []
    for handle in handles:
        profile = get_profile(handle)
        options.append(
            PersonaOption(
                handle=handle,
                name=profile.get("name", handle.title()),
                title=profile.get("title", ""),
            )
        )
    return options


MOCK_MODELS: list[ModelOption] = [
    ModelOption(id="claude-sonnet-5", label="Claude Sonnet 5 — cloud, default", short="Claude Sonnet 5"),
    ModelOption(id="gemma2:9b", label="Gemma2:9b — local, frugal", short="Gemma2:9b"),
    ModelOption(id="gpt-4o-mini", label="GPT-4o mini — cloud", short="GPT-4o mini"),
]

# Visual placeholder only — no session/history data model exists anywhere
# yet (backend or frontend), so this list never changes and selecting a
# row just says so.
MOCK_HISTORY: list[str] = [
    "Q3 roadmap — 12 turns, yesterday",
    "Trash cleanup follow-up — 4 turns, Monday",
]

MOCK_REPLIES: list[str] = [
    "Got it — I checked the vault and that note doesn't exist yet. Want me to create it?",
    "That's already in Projects/Q3-roadmap.md — I can append to it or open it for you.",
    "No matches for that in the vault. Want me to search a broader folder scope?",
]
