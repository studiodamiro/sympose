"""The model call itself (docs/decisions/007). Local-first by default —
`DEFAULT_LOCAL_MODEL` is the literal fallback a fresh checkout runs with, not
an opt-in, per docs/VISION.md's "Lesson from legacy". `ollama_chat/`, not
`ollama/`: it targets Ollama's native structured-chat endpoint (messages sent
as-is) rather than the older raw-completion endpoint litellm would otherwise
hand-assemble a prompt string for."""

import logging
import time
from dataclasses import dataclass

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


@dataclass(frozen=True)
class ModelReply:
    """The complete reply plus how long the model took to start producing
    it (docs/decisions/013)."""

    text: str
    # Milliseconds from just before the request to the first generated
    # token; `None` only if the stream ended without producing one.
    ttft_ms: int | None


class EngineModelError(Exception):
    """A model call failed (connection refused, model not pulled, etc.) —
    the CLI/channel layer shows `str(error)` to the user instead of a raw
    traceback."""


def resolve_model(persona_model: str | None = None) -> str:
    """The model a turn runs on when the caller made no explicit choice:
    the persona's own `model`, else the `chat_model` setting, else the
    built-in local default (docs/decisions/010). An explicit per-call
    model (`call_model`'s `model` argument) sits above all of these."""
    return persona_model or settings_store.get(_SETTINGS_KEY, DEFAULT_LOCAL_MODEL)


def _read(chunk) -> tuple[str, str | None]:
    """`(reply_text, finish_reason)` carried by one streamed chunk — the
    text may be empty, and a chunk with no choices (a keep-alive or
    usage-only frame) carries neither."""
    if not chunk.choices:
        return "", None
    choice = chunk.choices[0]
    return (
        getattr(choice.delta, "content", None) or "",
        getattr(choice, "finish_reason", None),
    )


def call_model(messages: list[dict[str, str]], model: str | None = None) -> ModelReply:
    """Streamed internally so time to first token can be measured (ADR 013),
    but the complete reply is still returned as one string — the CLI's own
    word-by-word reveal animates it client-side, so nothing downstream sees
    a stream. TTFT is time to the first *reply* text: a reasoning model's
    thinking is not counted, since that is not what the user is waiting to
    read. A stream that ends without a finish signal was cut off, and
    raises instead of being saved as if it were a whole reply."""
    target_model = model or resolve_model()
    parts: list[str] = []
    ttft_ms: int | None = None
    finished = False
    started = time.perf_counter()
    try:
        for chunk in litellm.completion(
            model=target_model,
            messages=messages,
            stream=True,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        ):
            text, finish_reason = _read(chunk)
            if text:
                if ttft_ms is None:
                    ttft_ms = round((time.perf_counter() - started) * 1000)
                parts.append(text)
            if finish_reason:
                finished = True
    except Exception as e:
        log.warning("Model call to %s failed: %s", target_model, e)
        raise EngineModelError(
            f"Couldn't reach model '{target_model}': {e}"
        ) from e
    content = "".join(parts)
    if not content:
        raise EngineModelError(f"Model '{target_model}' returned an empty reply.")
    if not finished:
        raise EngineModelError(
            f"The reply from '{target_model}' was cut off before it finished."
        )
    return ModelReply(text=content, ttft_ms=ttft_ms)
