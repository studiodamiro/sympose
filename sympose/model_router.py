"""
Local/Cloud Model Routing for Sympose (ADR-122).

Routes a SIMPLE message to a persona's cheap local_model instead of their
configured cloud model, without ever making a model judge its own
reliability: is_simple_message is a small, deterministic, self-owned
classifier that decides the tier before any model is called, and a persona
only ever falls back to cloud on an outright local failure — never on a
local model's own self-assessment.
"""

import json
import logging
import re
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

_OLLAMA_BASE = "http://localhost:11434"

# LiteLLM routes on a provider prefix (ollama/, ollama_chat/, ...) that
# Ollama's own HTTP API has no concept of — /api/ps and /api/generate report
# and expect the bare model name only. A persona's local_model is stored
# in the litellm-prefixed form (it's passed straight to litellm.completion),
# so anything talking to Ollama's API directly has to strip it first.
_OLLAMA_LITELLM_PREFIXES = ("ollama_chat/", "ollama_completion/", "ollama/")


def _bare_ollama_name(model_name: str) -> str:
    for pfx in _OLLAMA_LITELLM_PREFIXES:
        if model_name.startswith(pfx):
            return model_name[len(pfx) :]
    return model_name


# Deliberately conservative: any doubt routes to cloud. A message earns the
# SIMPLE tier only by being short AND not tripping any signal that it might
# carry real emotional or intellectual weight (ADR-122's core risk).
_MAX_SIMPLE_CHARS = 200
_COMPLEXITY_SIGNS = re.compile(
    r"""
    \b(explain|analyz|compare|argu|design|debug|refactor|
       implement|architect|review|critique|feel|feeling|worried|
       anxious|scared|sad|stress|relationship|remember|forget)\w*\b
    | [?].*[?]          # more than one question in the same message
    | ```                # code fences
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_simple_message(text: str) -> bool:
    """True only for short, low-stakes messages — greetings, quick asides,
    trivial factual questions. Never called with a model in the loop; pure
    string heuristics, same spirit as the vault-query trigger check
    already used elsewhere in Sympose. Biased toward False on any doubt,
    per ADR-122's "message weight" risk: a false negative just costs a
    cloud round-trip; a false positive risks a small local model mangling
    something that mattered."""
    stripped = text.strip()
    if not stripped or len(stripped) > _MAX_SIMPLE_CHARS:
        return False
    if _COMPLEXITY_SIGNS.search(stripped):
        return False
    return True


def resolve_turn_model(
    base_model: str,
    local_model: str,
    message: str,
    keep_alive: str | None = None,
) -> tuple[str, bool]:
    """Decides which model a turn should call. Returns (model_to_use,
    routed_local). Never blocks the turn on a cold local model: if
    local_model is unset, the message isn't SIMPLE, or the local model
    isn't already warm, this returns base_model immediately and — in the
    not-warm case — fires a background warm-up so the *next* SIMPLE
    message can route local. Callers still need their own try/except
    around the actual completion call to fall back to base_model on a
    local failure (ADR-122's Fallback section) — this function only picks
    the model, it doesn't call one."""
    if not local_model or not is_simple_message(message):
        return base_model, False

    bare_name = _bare_ollama_name(local_model)
    if not is_ollama_model_warm(bare_name):
        from sympose.compactor import run_hygiene_task

        run_hygiene_task(warm_ollama_model, bare_name, keep_alive=keep_alive)
        return base_model, False

    return local_model, True


def is_ollama_model_warm(model_name: str) -> bool:
    """Checks Ollama's own /api/ps for whether model_name is currently
    loaded in memory. Free, near-instant, never raises — an unreachable
    Ollama (not running) reads the same as "not warm", the safe default:
    callers should fall back to cloud rather than risk a cold-start wait."""
    req = urllib.request.Request(f"{_OLLAMA_BASE}/api/ps")
    try:
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return any(m.get("name") == model_name for m in data.get("models", []))
    except Exception:
        return False


def warm_ollama_model(
    model_name: str, keep_alive: str | None = None, timeout: float = 120.0
) -> None:
    """Loads model_name into Ollama's memory with a trivial, throwaway
    request (num_predict=1 — real work loading the model, negligible work
    generating). Blocking: a caller on a live turn's critical path should
    run this via compactor.run_hygiene_task, not call it directly.

    keep_alive, if given, is passed straight through to Ollama's own
    residency knob (performance.local_keep_alive / a persona's keep_alive
    override); None defers to Ollama's own default (~5 minutes)."""
    payload: dict[str, Any] = {
        "model": model_name,
        "prompt": "hi",
        "stream": False,
        "options": {"num_predict": 1},
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    req = urllib.request.Request(
        f"{_OLLAMA_BASE}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=timeout)
    except Exception as e:
        log.debug("Ollama warm-up failed for %s: %s", model_name, e)
