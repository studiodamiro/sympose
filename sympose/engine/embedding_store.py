"""The cache of passage vectors (docs/decisions/027): one small SQLite file beside the
settings file, so a note is embedded once and again only when its text (or the model)
changes. It holds nothing that cannot be rebuilt, so any problem with it means "no cache"."""

import hashlib
import logging
import os
import sqlite3
from array import array
from typing import Sequence

from sympose import settings_store

log = logging.getLogger(__name__)

_FILE = "embedding_cache.sqlite"


def path() -> str:
    return os.path.join(os.path.dirname(settings_store.settings_path()) or ".", _FILE)


def key(model: str, text: str) -> str:
    return hashlib.sha1(f"{model}\0{text}".encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path()) or ".", exist_ok=True)
    conn = sqlite3.connect(path(), timeout=30)
    conn.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vec BLOB NOT NULL)")
    return conn


def load(keys: list[str]) -> dict[str, array]:
    """The vectors stored for `keys`; a key with none is simply absent."""
    found: dict[str, array] = {}
    try:
        conn = _connect()
        try:
            for start in range(0, len(keys), 500):  # SQLite limits how many `?` one query may hold
                chunk = keys[start : start + 500]
                marks = ",".join("?" * len(chunk))
                for k, blob in conn.execute(f"SELECT key, vec FROM vectors WHERE key IN ({marks})", chunk):
                    vec = array("f")
                    try:
                        vec.frombytes(blob)
                    except ValueError:  # a truncated or hand-edited row: as if it were not there
                        continue
                    found[k] = vec
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        log.warning("Could not read the embedding cache %s: %s", path(), e)
    return found


def save(vectors: dict[str, Sequence[float]]) -> bool:
    """Whether the vectors are now in the cache (`False`: the file could not be written, so a build
    that relied on it would start again on every turn)."""
    if not vectors:
        return True
    try:
        conn = _connect()
        try:
            with conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO vectors (key, vec) VALUES (?, ?)",
                    [(k, array("f", v).tobytes()) for k, v in vectors.items()],
                )
        finally:
            conn.close()
        return True
    except (sqlite3.Error, OSError) as e:
        log.warning("Could not write the embedding cache %s: %s", path(), e)
        return False
