"""
Local/Cloud Model Routing for Sympose (ADR-122).

Routes a SIMPLE message to a persona's cheap local_model instead of their
configured cloud model, without ever making a model judge its own
reliability: the tier is decided by LiteLLM's heuristic ComplexityRouter
before any model is called, and a persona only ever falls back to cloud on
an outright local failure — never on a local model's own self-assessment.
"""

import json
import logging
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

_OLLAMA_BASE = "http://localhost:11434"


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
