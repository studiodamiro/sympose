"""The model call itself (docs/decisions/007). Local-first by default —
`DEFAULT_LOCAL_MODEL` is the literal fallback a fresh checkout runs with, not
an opt-in, per docs/VISION.md's "Lesson from legacy". `ollama_chat/`, not
`ollama/`: it targets Ollama's native structured-chat endpoint (messages sent
as-is) rather than the older raw-completion endpoint litellm would otherwise
hand-assemble a prompt string for."""

import logging

import litellm

from sympose import settings_store

log = logging.getLogger(__name__)

DEFAULT_LOCAL_MODEL = "ollama_chat/gemma2:9b"

_SETTINGS_KEY = "chat_model"

# `sympose/cli/runtime.py` holds one global lock for the duration of a call
# (docs/decisions/006) — a hung request (a stalled local Ollama process, a
# network partition to a cloud endpoint) would otherwise wedge every future
# message behind it forever, with no error and no way out short of killing
# the process, since a thread running a blocking network call can't be
# cancelled. A generous but finite bound turns that into a recoverable
# `EngineModelError` instead.
_REQUEST_TIMEOUT_SECONDS = 120


class EngineModelError(Exception):
    """A model call failed (connection refused, model not pulled, etc.) —
    the CLI/channel layer shows `str(error)` to the user instead of a raw
    traceback."""


def resolve_model() -> str:
    return settings_store.get(_SETTINGS_KEY, DEFAULT_LOCAL_MODEL)


def call_model(messages: list[dict[str, str]], model: str | None = None) -> str:
    """Non-streaming — the CLI's own word-by-word reveal already animates a
    complete reply string client-side, so token-level streaming from the
    model isn't needed here."""
    target_model = model or resolve_model()
    try:
        response = litellm.completion(
            model=target_model,
            messages=messages,
            stream=False,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
    except Exception as e:
        log.warning("Model call to %s failed: %s", target_model, e)
        raise EngineModelError(
            f"Couldn't reach model '{target_model}': {e}"
        ) from e
    if not content:
        raise EngineModelError(f"Model '{target_model}' returned an empty reply.")
    return content
