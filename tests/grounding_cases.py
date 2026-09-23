"""The grounding retrieval eval: a synthetic vault (tests/fixtures/grounding_vault)
and a table of chat messages with what must, and must not, reach the model.

Retrieval is deterministic, so this needs no model. The vault is read through
the real `get_vault_snapshot` / `resolve_sandbox`, the same loader the nebula's
manifest build and search use, so a passing case exercises the real path.
Synthetic on purpose: nothing here is tuned to anyone's real notes.

`run_case` works against any `ground(profile, message)` that returns hits with
either a `text` (passage) or a `snippet`, so the same table measures the old
and the new retriever."""

import os
from dataclasses import dataclass, field
from typing import Any, Callable

FIXTURE_VAULT = os.path.join(os.path.dirname(__file__), "fixtures", "grounding_vault")

WHOLE = {"vault_folders": ["*"]}


@dataclass(frozen=True)
class Case:
    id: str
    message: str
    profile: dict[str, Any] = field(default_factory=lambda: WHOLE)
    # Every substring must appear in the text the model would receive.
    find: tuple[str, ...] = ()
    # The top hit must be this note (rel_path), when set.
    first: str | None = None
    # None of these notes may appear at all.
    forbid: tuple[str, ...] = ()
    # Nothing at all should be grounded (an honest "no notes matched").
    none: bool = False
    # A documented limit rather than a bug to fix now.
    known_gap: str | None = None


CASES: list[Case] = [
    Case(
        "decision-by-topic",
        "what did we decide about the database for Atlas?",
        find=("SQLite",),
        first="Projects/Atlas.md",
    ),
    Case(
        "opinion-brings-the-decision",
        "should I switch Atlas over to Postgres?",
        find=("SQLite", "Postgres was rejected"),
        first="Projects/Atlas.md",
    ),
    Case(
        "title-hit-brings-content-not-just-the-heading",
        "tell me one thing about the Atlas project",
        find=("SQLite",),
        first="Projects/Atlas.md",
    ),
    Case(
        "similar-names",
        "why is it called Atlas?",
        find=("Meridian",),
    ),
    Case(
        "generic-words-only-ground-nothing",
        "hey, how are you today?",
        none=True,
    ),
    Case(
        "chatty-message-with-one-ordinary-body-word-grounds-nothing",
        "hey. rough day, my brain is completely fried",
        none=True,
    ),
    Case(
        "a-request-matching-only-ordinary-words-grounds-nothing",
        "can you create a new persona for me called Grace?",
        none=True,
    ),
    Case(
        "one-word-message-about-a-name",
        "who is Priya?",
        find=("Priya",),
        first="Work/Meeting 2026-09-18.md",
    ),
    Case(
        "absent-topic-grounds-nothing",
        "what does my note about tax filing say?",
        none=True,
    ),
    Case(
        "specific-detail",
        "how long do I bake the sourdough?",
        find=("230C",),
        forbid=("Recipes/Pasta Carbonara.md",),
    ),
    Case(
        "rare-word",
        "what goes in a carbonara? I only remember guanciale",
        find=("guanciale",),
        first="Recipes/Pasta Carbonara.md",
    ),
    Case(
        "frontmatter-title-differs-from-filename",
        "what's my training plan?",
        find=("Run three times",),
    ),
    Case(
        "tag-only-match-brings-content",
        "any baking notes?",
        find=("starter",),
        first="Recipes/Sourdough.md",
    ),
    Case(
        "answer-deep-in-a-long-note",
        "what are the four rules of deep work?",
        find=("embrace boredom",),
        first="Reading/Deep Work.md",
    ),
    Case(
        "middle-of-a-paragraph",
        "explain tacking and jibing",
        find=("bow of the boat",),
        first="Reading/Sailing Basics.md",
    ),
    Case(
        "who-owns-it",
        "who owns the dark mode decision?",
        find=("Priya",),
    ),
    Case(
        "budget",
        "how did we go over budget?",
        find=("cloud costs",),
        first="Work/Budget.md",
    ),
    Case(
        "dates",
        "when are the Lisbon flights?",
        find=("first week of May",),
        first="Travel/Lisbon Trip.md",
    ),
    Case(
        "sandbox-respected",
        "what did we decide about the Atlas database?",
        profile={"vault_folders": ["Recipes"]},
        none=True,
    ),
    Case(
        "common-word-attaches-notes-when-the-distinctive-word-is-absent",
        "can you help me plan dinner",
        none=True,
        known_gap="'plan' matches the Fitness Plan and Budget notes while 'dinner' "
        "is nowhere in the vault. In a real vault 'plan' is common enough to be "
        "ignored or weak; in this 17-note fixture it stands out. Kept to show the class.",
    ),
    Case(
        "lexical-ceiling",
        "what storage engine did we pick?",
        find=("SQLite",),
        known_gap="No shared words with the note: the wall that only meaning-based "
        "matching (embeddings) would cross. Kept to show where the ceiling is.",
    ),
]


def _texts(hits: list[dict[str, Any]]) -> list[str]:
    return [h.get("text") or h.get("snippet") or "" for h in hits]


def run_case(case: Case, ground: Callable[[dict[str, Any], str], list[dict[str, Any]]]) -> str | None:
    """`None` when the case passes, else a one-line reason."""
    hits = ground(case.profile, case.message)
    rel_paths = [h["rel_path"] for h in hits]
    blob = "\n".join(_texts(hits))

    if case.none:
        return None if not hits else f"expected nothing, got {rel_paths}"
    for needle in case.find:
        if needle not in blob:
            return f"missing {needle!r} in what the model would see ({rel_paths})"
    if case.first and (not rel_paths or rel_paths[0] != case.first):
        return f"top hit was {rel_paths[:1]}, wanted {case.first!r}"
    for path in case.forbid:
        if path in rel_paths:
            return f"{path!r} should not have been grounded ({rel_paths})"
    return None


def setup_env(monkeypatch_or_environ: Any, settings_path: str) -> None:
    """Points the backend at the fixture vault. Accepts a pytest
    `monkeypatch` (has `setenv`) or `os.environ` (a plain dict)."""
    if hasattr(monkeypatch_or_environ, "setenv"):
        monkeypatch_or_environ.setenv("VAULT_PATHS", FIXTURE_VAULT)
        monkeypatch_or_environ.setenv("SYMPOSE_SETTINGS_PATH", settings_path)
    else:
        monkeypatch_or_environ["VAULT_PATHS"] = FIXTURE_VAULT
        monkeypatch_or_environ["SYMPOSE_SETTINGS_PATH"] = settings_path
