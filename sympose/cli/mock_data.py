"""Canned data for the CLI mock. Personas are a real read through
`sympose/profile.py` and `profiles/*.yaml` — the same "functional but
mock" split the dashboard's persona picker uses (real data, just little of
it configured yet). Chat history has no backing store anywhere yet, so that
stays hardcoded. Model ids are now the real litellm-resolvable strings the
engine's `/model` picker override passes straight through (docs/decisions/007)
— the local Ollama model is listed first/default, matching the engine's own
local-first default, not the cloud-first ordering this list used to have."""

import glob
import os
from dataclasses import dataclass

from sympose.engine.model import DEFAULT_LOCAL_MODEL
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
    # `DEFAULT_LOCAL_MODEL`, not a re-typed literal (docs/CODE_QUALITY_STANDARDS.md's
    # "declared once" rule) — the CLI always passes `app.model.id` as
    # `run_turn`'s per-call override, so this picker's own default id is
    # what the CLI actually runs with; a stale duplicate here would
    # silently diverge from `sympose/engine/model.py`'s canonical default.
    ModelOption(id=DEFAULT_LOCAL_MODEL, label="Gemma2:9b — local, default", short="Gemma2:9b"),
    # Real, litellm-resolvable provider-prefixed ids, not placeholders —
    # once the CLI called the real engine, selecting a placeholder id
    # (e.g. bare "claude-sonnet-5") broke every
    # subsequent turn with a confusing error instead of being a harmless
    # mock no-op. These work if the corresponding API key
    # (ANTHROPIC_API_KEY / OPENAI_API_KEY) is set in `.env`; if not,
    # litellm raises its own standard, comprehensible auth error, which
    # `EngineModelError` still surfaces as a friendly in-transcript line —
    # cloud opt-in credential UX beyond that is future scope, not this slice.
    ModelOption(id="anthropic/claude-sonnet-5", label="Claude Sonnet 5 — cloud", short="Claude Sonnet 5"),
    ModelOption(id="openai/gpt-4o-mini", label="GPT-4o mini — cloud", short="GPT-4o mini"),
]

# Visual placeholder only — no session/history data model exists anywhere
# yet (backend or frontend), so this list never changes and selecting a
# row just says so.
MOCK_HISTORY: list[str] = [
    "Q3 roadmap — 12 turns, yesterday",
    "Trash cleanup follow-up — 4 turns, Monday",
]
