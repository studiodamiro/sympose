"""Meaning-based search, the parts that do not depend on a vault (docs/decisions/027):
the settings, and the call that turns text into a vector. `keywords` never reaches this
module's model call."""

import logging
import math
import operator
from array import array
from typing import Any, Sequence

import litellm

from sympose import settings_store

log = logging.getLogger(__name__)

# litellm prints a "Give Feedback / Get Help" banner to the terminal when a call fails; the CLI is
# drawing on that terminal, and a missing embedding model is an expected, handled case here.
litellm.suppress_debug_info = True

MODE_SETTING = "grounding_search"
MODEL_SETTING = "embedding_model"
THRESHOLD_SETTING = "embedding_min_similarity"
MARGIN_SETTING = "embedding_margin"
AUTO, KEYWORDS, EMBEDDINGS, HYBRID = "auto", "keywords", "embeddings", "hybrid"
_MODES = (AUTO, KEYWORDS, EMBEDDINGS, HYBRID)
DEFAULT_MODE = AUTO  # the tests set it to KEYWORDS (tests/conftest.py)
DEFAULT_MODEL = "ollama/nomic-embed-text"
DEFAULT_THRESHOLD = 0.72  # for the default model; a different model needs its own number
DEFAULT_MARGIN = 0.02  # a note is kept when its best passage is this close to the best note's
_BATCH = 16
_TIMEOUT_SECONDS = 30  # a hung Ollama must not hold a turn: the search falls back to keywords
_MAX_CHARS = 1500
# The task prefixes `nomic-embed-text` was trained with; another model is sent the text as it is.
_PREFIXES = {"nomic-embed-text": {"document": "search_document: ", "query": "search_query: "}}


class EmbeddingUnavailable(Exception):
    """The embedding model could not be reached or did not answer; the search falls back to keywords."""


def mode() -> str:
    value = settings_store.get(MODE_SETTING)
    return value if value in _MODES else DEFAULT_MODE


def model() -> str:
    value = settings_store.get(MODEL_SETTING)
    return value.strip() if isinstance(value, str) and value.strip() else DEFAULT_MODEL


def min_similarity() -> float:
    """A number strictly between 0 and 1; anything else (a string, a boolean, 0, 7) is the default."""
    value = settings_store.get(THRESHOLD_SETTING)
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value < 1
    return float(value) if ok else DEFAULT_THRESHOLD


def margin() -> float:
    """A number from 0 to 1 (1 keeps every note that reaches the threshold); anything else is the default."""
    value = settings_store.get(MARGIN_SETTING)
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
    return float(value) if ok else DEFAULT_MARGIN


def unavailable_log_level() -> int:
    """How loudly to log that the embedding model is missing: a note in `auto`, where that is the normal
    state of someone who set nothing up, a warning when the user asked for meaning-based search."""
    return logging.INFO if mode() == AUTO else logging.WARNING


def _prefix(kind: str, name: str) -> str:
    return next((p[kind] for key, p in _PREFIXES.items() if key in name), "")


def embed(texts: list[str], kind: str, model_name: str | None = None) -> list[list[float]]:
    """One vector per text. `kind` is `"document"` (a passage) or `"query"` (the message). The caller
    that made the cache keys passes its `model_name`, so a setting edited meanwhile cannot store one
    model's vectors under another's keys."""
    name = model_name or model()
    prefix, vectors = _prefix(kind, name), []
    for start in range(0, len(texts), _BATCH):
        batch = [prefix + text for text in texts[start : start + _BATCH]]
        try:
            response: Any = litellm.embedding(model=name, input=batch, timeout=_TIMEOUT_SECONDS)
            vectors.extend(list(item["embedding"]) for item in response.data)
        except Exception as e:  # litellm raises its own family of errors; all mean "not available"
            raise EmbeddingUnavailable(f"{type(e).__name__}: {e}") from e
    if len(vectors) != len(texts):
        raise EmbeddingUnavailable("the embedding model returned the wrong number of vectors")
    return vectors


def passage_text(passage: Any) -> str:
    """What is embedded for a passage: its note's title and heading with its text, cut to a size the
    embedding model takes whole."""
    return f"{passage.title}\n{passage.heading}\n{passage.text}"[:_MAX_CHARS]


def unit(vector: Sequence[float]) -> array:
    """The vector scaled to length one, kept as 32-bit floats (a vault of ten thousand passages as Python
    lists would take a few hundred megabytes; as this, about thirty)."""
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return array("f", (x / norm for x in vector))


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    """The cosine of two vectors that were made unit length with `unit`."""
    return sum(map(operator.mul, a, b))
