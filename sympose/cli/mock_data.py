"""Canned data for the CLI mock. Personas are a real read through
`sympose/profile.py` and `profiles/*.yaml` — the same "functional but
mock" split the web app's persona picker uses (real data, just little of
it configured yet). Chat history has no backing store anywhere yet, so that
stays hardcoded. Model ids are now the real litellm-resolvable strings the
engine's `/model` picker override passes straight through (docs/decisions/007)
— the local Ollama model is listed first/default, matching the engine's own
local-first default, not the cloud-first ordering this list used to have."""

from dataclasses import dataclass

from sympose.engine.model import DEFAULT_LOCAL_MODEL, resolve_model
from sympose.profile import list_profiles


@dataclass(frozen=True)
class PersonaOption:
    handle: str
    name: str
    title: str
    # The persona's own `model` from its profile, or `None` (docs/decisions/010).
    model: str | None = None


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    # Short name for the streamed-reply header (`runtime.py`) — a
    # dedicated field rather than parsing it back out of `label`, which
    # is free-form display text with no guaranteed structure.
    short: str


def list_personas() -> list[PersonaOption]:
    """The CLI's narrower projection of `profile.list_profiles()` — the
    one canonical roster the web app's `GET /api/personas` also builds
    on (docs/decisions/009), so a malformed/unsafe profile file is
    already handled and handles are already lowercased/deduped there."""
    return [
        PersonaOption(
            handle=p["handle"], name=p["name"], title=p["title"], model=p["model"]
        )
        for p in list_profiles()
    ]


MODEL_OPTIONS: list[ModelOption] = [
    # `DEFAULT_LOCAL_MODEL`, not a re-typed literal (docs/CODE_QUALITY_STANDARDS.md's
    # "declared once" rule) — a stale duplicate here would silently diverge
    # from `sympose/engine/model.py`'s canonical default.
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
    # The `-latest` aliases, not a dated name: Google retires named versions
    # (the 2.x ones already answer "no longer available"), an alias follows.
    # Needs `GEMINI_API_KEY` in `.env` (docs/decisions/007).
    ModelOption(id="gemini/gemini-flash-latest", label="Gemini Flash — cloud", short="Gemini Flash"),
    ModelOption(id="gemini/gemini-pro-latest", label="Gemini Pro — cloud", short="Gemini Pro"),
    # One `OPENROUTER_API_KEY` for models from other makers; any other OpenRouter
    # model works by name in `chat_model` (docs/decisions/007).
    ModelOption(id="openrouter/anthropic/claude-haiku-4.5", label="Claude Haiku 4.5 — OpenRouter", short="Claude Haiku 4.5"),
    ModelOption(id="openrouter/meta-llama/llama-3.3-70b-instruct", label="Llama 3.3 70B — OpenRouter", short="Llama 3.3 70B"),
    ModelOption(id="openrouter/meta-llama/llama-3.1-8b-instruct", label="Llama 3.1 8B — OpenRouter", short="Llama 3.1 8B"),
    ModelOption(id="openrouter/deepseek/deepseek-v4-flash", label="DeepSeek V4 Flash — OpenRouter", short="DeepSeek V4 Flash"),
]

def model_option_for(model_id: str) -> ModelOption:
    """The picker entry for `model_id`, or a synthesized one for an id the
    picker doesn't list (a persona's own `model`, or the `chat_model`
    setting, can name anything litellm resolves)."""
    known = next((m for m in MODEL_OPTIONS if m.id == model_id), None)
    return known or ModelOption(id=model_id, label=model_id, short=model_id.split("/")[-1])


def active_model(persona: PersonaOption, override: ModelOption | None) -> ModelOption:
    """What actually runs for `persona`: the user's explicit `/model` pick if
    there is one, else the persona's model / setting / default, in the
    engine's own order (`resolve_model`, docs/decisions/010) — the same
    function `run_turn` uses, so the header can't show something else."""
    return override or model_option_for(resolve_model(persona.model))


# Visual placeholder only — no session/history data model exists anywhere
# yet (backend or frontend), so this list never changes and selecting a
# row just says so.
MOCK_HISTORY: list[str] = [
    "Q3 roadmap — 12 turns, yesterday",
    "Trash cleanup follow-up — 4 turns, Monday",
]
