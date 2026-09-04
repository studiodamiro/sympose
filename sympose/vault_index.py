"""
sqlite3 FTS5-backed vault search index (ADR-070.5).

Stdlib only, BM25-ranked full-text search — the long-promised `sqlite_fts`
`vault.search_mode` tier (ADR-003). `direct` (the existing full-Python-walk
mode) stays the zero-state default; this only activates when a workspace
opts in.

One index file per master vault, cached under the *workspace* (never inside
the user's actual Obsidian vault folder) at `.vault_index/<hash>.sqlite3`.
Kept fresh two ways: an exact single-row upsert called directly from
write_note/append_note (searchable on the very next query, independent of
mtime timing), and a full rebuild whenever the tracked directory-mtime
watermark drifts — catches edits made outside Sympose. Same directory-mtime
tradeoff as `_VAULT_SNAPSHOT_CACHE` (vault.py): a write several levels below
a watched directory only bubbles up as far as its immediate parent's mtime.

If this Python's sqlite3 wasn't built with FTS5, every function here
degrades to "index unusable" so callers fall back to `direct` with no
visible error.
"""

import os
import re
import sqlite3
import hashlib
import logging
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

# db_path -> whether CREATE VIRTUAL TABLE succeeded on this Python's sqlite3
_FTS5_OK: Dict[str, bool] = {}


def index_path(workspace_dir: str, mv: str) -> str:
    digest = hashlib.sha1(os.path.abspath(mv).encode("utf-8")).hexdigest()[:16]
    index_dir = os.path.join(workspace_dir, ".vault_index")
    os.makedirs(index_dir, exist_ok=True)
    return os.path.join(index_dir, f"{digest}.sqlite3")


def _connect(db_path: str) -> Optional[sqlite3.Connection]:
    """Opens the index db, creating its FTS5 table on first use. Never raises —
    returns None if this Python's sqlite3 lacks the FTS5 extension."""
    if _FTS5_OK.get(db_path) is False:
        return None
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS notes USING fts5("
            "rel_path UNINDEXED, file_name, title, body, tags, "
            "tokenize=\"porter unicode61\")"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        _FTS5_OK[db_path] = True
        return conn
    except sqlite3.OperationalError:
        _FTS5_OK[db_path] = False
        log.warning("[vault_index] sqlite3 FTS5 extension unavailable; `vault.search_mode: sqlite_fts` will fall back to `direct`.")
        return None
    except Exception:
        log.debug("[vault_index] failed to open index db %s", db_path, exc_info=True)
        return None


def _title_of(meta: Dict[str, Any], file_name: str) -> str:
    return str(meta.get("title") or meta.get("name") or os.path.splitext(file_name)[0])


def _tags_of(meta: Dict[str, Any]) -> str:
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        return tags
    if isinstance(tags, list):
        return " ".join(str(t) for t in tags)
    return ""


def upsert_note(workspace_dir: str, mv: str, rel_path: str, file_name: str, meta: Dict[str, Any], body: str) -> None:
    """Single-row insert/replace, called right after a Sympose-driven write so
    the note is searchable on the very next query. Best-effort: never raises."""
    conn = _connect(index_path(workspace_dir, mv))
    if conn is None:
        return
    try:
        conn.execute("DELETE FROM notes WHERE rel_path = ?", (rel_path,))
        conn.execute(
            "INSERT INTO notes (rel_path, file_name, title, body, tags) VALUES (?, ?, ?, ?, ?)",
            (rel_path, file_name, _title_of(meta, file_name), body, _tags_of(meta)),
        )
        conn.commit()
    except Exception:
        log.debug("[vault_index] upsert failed for %s", rel_path, exc_info=True)
    finally:
        conn.close()


def ensure_fresh(workspace_dir: str, mv: str, snapshot_provider: Callable[[], List[Dict[str, Any]]]) -> bool:
    """Full rebuild if the tracked mtime watermark drifted since the last
    rebuild. `snapshot_provider()` returns VaultManager._get_vault_snapshot's
    flat note list — the caller already knows how to walk the vault; this
    just owns freshness and storage. Returns whether the index is usable
    (False => caller should fall back to `direct`)."""
    db_path = index_path(workspace_dir, mv)
    conn = _connect(db_path)
    if conn is None:
        return False

    try:
        watched = [mv] + [
            os.path.join(mv, d) for d in os.listdir(mv)
            if os.path.isdir(os.path.join(mv, d)) and not d.startswith(".")
        ]
    except OSError:
        watched = [mv]
    current_mtime = 0.0
    for d in watched:
        try:
            current_mtime = max(current_mtime, os.path.getmtime(d))
        except OSError:
            pass

    row = conn.execute("SELECT value FROM meta WHERE key = 'watermark'").fetchone()
    if row is not None and float(row[0]) == current_mtime:
        conn.close()
        return True

    try:
        snapshot = snapshot_provider()
        conn.execute("DELETE FROM notes")
        conn.executemany(
            "INSERT INTO notes (rel_path, file_name, title, body, tags) VALUES (?, ?, ?, ?, ?)",
            [
                (e["rel_path"], e["file_name"], _title_of(e["meta"], e["file_name"]), e["body"], _tags_of(e["meta"]))
                for e in snapshot
            ],
        )
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('watermark', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(current_mtime),),
        )
        conn.commit()
        return True
    except Exception:
        log.debug("[vault_index] full rebuild failed for %s", mv, exc_info=True)
        return False
    finally:
        conn.close()


def query(workspace_dir: str, mv: str, query_text: str, scope_dirs: List[str], max_results: int) -> Optional[List[Dict[str, Any]]]:
    """BM25-ranked full-text search, prefix-matched per query token, title
    weighted above body. Returns None if the index isn't usable (caller falls
    back to `direct`); returns [] for zero matches."""
    conn = _connect(index_path(workspace_dir, mv))
    if conn is None:
        return None

    tokens = [t for t in re.findall(r"\w+", query_text.lower()) if t]
    if not tokens:
        conn.close()
        return []
    match_expr = " ".join(f"{t}*" for t in tokens)

    rel_prefixes = [os.path.relpath(d, mv) for d in scope_dirs]
    full_vault_access = any(p in (".", "") for p in rel_prefixes)

    try:
        rows = conn.execute(
            # Column weights: rel_path(unindexed, 0), file_name, title, body, tags
            "SELECT rel_path, file_name, title, snippet(notes, 3, '', '', ' … ', 10) "
            "FROM notes WHERE notes MATCH ? ORDER BY bm25(notes, 0.0, 2.0, 5.0, 1.0, 1.5) LIMIT ?",
            (match_expr, max_results * 4),
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return None
    finally:
        conn.close()

    results: List[Dict[str, Any]] = []
    for rel_path, file_name, title, snip in rows:
        if not full_vault_access and not any(
            rel_path == p or rel_path.startswith(p.rstrip("/") + "/") for p in rel_prefixes
        ):
            continue
        results.append({
            "file_name": file_name,
            "rel_path": rel_path,
            "title": title,
            "snippet": (snip or "").strip() or "Match found",
        })
        if len(results) >= max_results:
            break
    return results
