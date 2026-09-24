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

from sympose.engine import followup

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
        known_gap="'plan' is half of the two-word title Training Plan, so it grounds that note "
        "while 'dinner' is nowhere in the vault. A rare word could be told from an ordinary one "
        "only by how many notes use it, which was measured not to separate them (ADR 021).",
    ),
    Case(
        "a-long-general-request-sharing-ordinary-words-grounds-nothing",
        "please suggest a good name for my new project and something to do over the next few weeks",
        none=True,
    ),
    Case(
        "lexical-ceiling",
        "what storage engine did we pick?",
        find=("SQLite",),
        known_gap="No shared words with the note: the wall that only meaning-based "
        "matching (embeddings) would cross. Kept to show where the ceiling is.",
    ),
]


@dataclass(frozen=True)
class FollowupCase:
    """A bare follow-up after some chat (docs/decisions/017). `rewrite` is what
    a fake rewriter answers (`None`: no query), so retrieval is tested without
    a model; what the real model writes is measured separately."""

    id: str
    history: tuple[tuple[str, str], ...]
    message: str
    rewrite: str | None
    find: tuple[str, ...] = ()
    # The query the turn should report as having grounded it, when it is not the message.
    searched: str | None = None
    none: bool = False


_ATLAS_CHAT = (
    (
        "what did we decide about the database for Atlas?",
        "You decided on SQLite for the Atlas prototype because it needs zero setup.",
    ),
)

FOLLOWUP_CASES: list[FollowupCase] = [
    FollowupCase(
        "why-did-we-pick-it",
        _ATLAS_CHAT,
        "why did we pick it?",
        "why did we pick SQLite for the Atlas prototype",
        find=("SQLite",),
        searched="why did we pick SQLite for the Atlas prototype",
    ),
    FollowupCase(
        "expand-on-that",
        (("how did we go over budget?", "Q3 spend ran 12k over plan, mostly cloud costs."),),
        "can you expand on that?",
        "Q3 cloud costs",
        find=("staging servers",),
        searched="Q3 cloud costs",
    ),
    FollowupCase(
        "go-on",
        (("explain tacking and jibing", "Tacking turns the bow through the wind; jibing turns the stern."),),
        "go on",
        "tacking and jibing risks in strong breeze",
        find=("boom swings across",),
        searched="tacking and jibing risks in strong breeze",
    ),
    FollowupCase("thanks-attaches-nothing-old", _ATLAS_CHAT, "thanks, that helps!", followup.NO_TOPIC_QUERY, none=True),
    FollowupCase("small-talk-attaches-nothing-old", _ATLAS_CHAT, "how are you today?", followup.NO_TOPIC_QUERY, none=True),
    # Weak evidence (one matched word) is put to the rewrite, with no earlier chat too:
    # 'trip' alone attaches the Lisbon Trip note to a request to plan a trip.
    FollowupCase(
        "a-lone-title-word-in-chatter-is-dropped-when-the-model-says-no-topic",
        (),
        "can you help me plan a trip",
        followup.NO_TOPIC_QUERY,
        none=True,
    ),
    # ... but a lone name that is a real topic survives, on the model's own query.
    FollowupCase(
        "a-lone-name-that-is-a-topic-survives-the-check",
        (),
        "who is Priya?",
        "Priya",
        find=("Priya",),
        searched="Priya",
    ),
    FollowupCase(
        "a-query-about-something-the-vault-lacks-grounds-nothing",
        _ATLAS_CHAT,
        "what about that?",
        "tax filing deadline",
        none=True,
    ),
]


def run_followup_case(
    case: FollowupCase, persona: dict[str, Any], model: str = "ollama_chat/gemma2:9b"
) -> str | None:
    """`None` when the follow-up case passes, else a one-line reason."""
    history = [
        {"role": role, "content": text}
        for user, assistant in case.history
        for role, text in (("user", user), ("assistant", assistant))
    ]
    hits, searched = followup.ground(
        persona, case.message, history, model, None, rewriter=lambda *_: case.rewrite
    )
    blob = "\n".join(_texts(hits))
    if case.none:
        return None if not hits and searched is None else f"expected nothing, got {[h['rel_path'] for h in hits]}"
    for needle in case.find:
        if needle not in blob:
            return f"missing {needle!r} in what the model would see"
    if searched != case.searched:
        return f"reported query {searched!r}, wanted {case.searched!r}"
    return None


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
