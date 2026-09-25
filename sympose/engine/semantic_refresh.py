"""Building the passage vectors in the background (docs/decisions/027): the first index of a
big vault takes a minute or two of the GPU, which a turn must never wait for. Started when the
CLI starts and when the persona changes, like the recaps (docs/decisions/023). It never raises:
a missing embedding model leaves the search on keywords, and a build that failed is not started
again on every turn."""

import logging
import threading
import time
from array import array
from typing import Any

from sympose.engine import embedding_store as store
from sympose.engine import embeddings

log = logging.getLogger(__name__)

# The builds in flight, by `(model, id(index))`, so two turns do not start the same one; and the
# ones that failed, with when, so a down Ollama or an unwritable cache costs one attempt in
# `_RETRY_AFTER_SECONDS`, not one per message.
_BUILDING: set[tuple[str, int]] = set()
_FAILED: dict[tuple[str, int], tuple[float, Any]] = {}  # when, and the index (kept so its id is not reused)
_PROGRESS: dict[tuple[str, int], tuple[int, int]] = {}  # per build: (passages done, passages to do)
_LOCK = threading.Lock()
_RETRY_AFTER_SECONDS = 300.0
_BATCH_SAVE = 64


def pending(index: Any, model: str) -> tuple[list[str], list[str], dict[str, array], list[int]]:
    """`(texts, cache keys, the vectors the cache has, positions with none)` for the passages of `index`."""
    texts = [embeddings.passage_text(p) for p in index.passages]
    keys = [store.key(model, t) for t in texts]
    have = store.load(keys)
    return texts, keys, have, [i for i, k in enumerate(keys) if k not in have]


def _report(token: tuple[str, int] | None, done: int, total: int) -> None:
    if token is not None:
        with _LOCK:
            _PROGRESS[token] = (done, total)


def progress() -> int | None:
    """The whole percent of the passages the running builds had to embed that are done, or `None`
    when no build is running (what the CLI shows as `indexing 40%`)."""
    with _LOCK:
        counted = [_PROGRESS.get(token, (0, 0)) for token in _BUILDING]
    # A build that has not counted its work yet, or found nothing to do (a warm cache), is not "indexing".
    running = [p for p in counted if p[1] > 0]
    if not running:
        return None
    done, total = sum(d for d, _ in running), sum(t for _, t in running)
    return 100 * done // total if total else 0


def build(index: Any, token: tuple[str, int] | None = None) -> bool:
    """Embed every passage of `index` that has no vector yet and save them, a batch at a time so an
    interrupted build keeps what it has done. `False` when the cache could not be written. `token`
    is the build's identity when it runs in the background, so its progress can be shown, and it
    fixes the model: the one the caller keyed the build by."""
    model = token[0] if token is not None else embeddings.model()
    texts, keys, _, todo = pending(index, model)
    _report(token, 0, len(todo))
    for start in range(0, len(todo), _BATCH_SAVE):
        chunk = todo[start : start + _BATCH_SAVE]
        vectors = embeddings.embed([texts[i] for i in chunk], "document", model)
        if not store.save({keys[i]: v for i, v in zip(chunk, vectors)}):
            return False
        _report(token, start + len(chunk), len(todo))
    return True


def _fail(token: tuple[str, int], index: Any, reason: str) -> None:
    now = time.monotonic()
    with _LOCK:
        for old in [t for t, (when, _) in _FAILED.items() if now - when >= _RETRY_AFTER_SECONDS]:
            del _FAILED[old]  # forgotten, so the table does not grow and an old index is let go
        _FAILED[token] = (now, index)
    log.warning("The search index could not be built, searching by keyword (%s)", reason)


def _run(index: Any, token: tuple[str, int]) -> None:
    try:
        if not build(index, token):
            _fail(token, index, "the embedding cache could not be written")
    except embeddings.EmbeddingUnavailable as e:
        _fail(token, index, str(e))
    except Exception:  # a background build must not take the chat down
        log.exception("The search index build failed")
        _fail(token, index, "unexpected error")
    finally:
        with _LOCK:
            _BUILDING.discard(token)
            _PROGRESS.pop(token, None)


def start_build(index: Any, wait: bool = False, model: str | None = None) -> threading.Thread | None:
    """Build `index` in a background thread for `model` (the setting, by default), unless that build
    is already running or failed recently."""
    token = (model or embeddings.model(), id(index))
    with _LOCK:
        failed = _FAILED.get(token)
        if token in _BUILDING or (failed is not None and time.monotonic() - failed[0] < _RETRY_AFTER_SECONDS):
            return None
        _BUILDING.add(token)
    thread = threading.Thread(target=_run, args=(index, token), name="embedding-index", daemon=True)
    thread.start()
    if wait:
        thread.join()
    return thread


def refresh_in_background(handle: str) -> None:
    """Start building the vectors for what `handle` searches (its notes and, if it has them, the
    Sympose library), unless the knob is `keywords`. Returns at once."""
    if embeddings.mode() == embeddings.KEYWORDS:
        return

    def work() -> None:
        # Imported here: these modules import the search, which imports this one.
        from sympose import profile as profile_mod
        from sympose.engine import grounding, reference

        persona = profile_mod.resolve_profile(handle)
        if persona is None:
            return
        for index in (grounding.scope_index(persona), reference.library_index(persona)):
            if index is not None:
                start_build(index, wait=True)

    threading.Thread(target=work, name=f"embeddings-{handle}", daemon=True).start()


def _forget_for_tests() -> None:
    with _LOCK:
        _BUILDING.clear()
        _FAILED.clear()
        _PROGRESS.clear()
