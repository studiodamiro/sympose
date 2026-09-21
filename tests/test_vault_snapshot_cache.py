"""Regression test for the empty-scope mtime cache — an allowed_dirs scope
with zero notes/folders must still be served from cache on an unchanged
mtime, not re-walked on every call (see vault_snapshot.py / vault_graph.py)."""

from sympose import vault_graph
from sympose.vault_defaults import IGNORE_FOLDERS
from sympose.vault_snapshot import _VAULT_SNAPSHOT_CACHE, get_vault_snapshot

_IGNORE_KEY = tuple(sorted({d.lower() for d in IGNORE_FOLDERS}))


def test_empty_snapshot_scope_is_cached(tmp_path):
    vault = str(tmp_path)
    dirs = [vault]

    first = get_vault_snapshot(vault, dirs)
    assert first == []

    # A second call with nothing on disk changed must hit the cache — if it
    # didn't, the cache entry written by the first call would simply be
    # overwritten with the same (mtime, []) pair, which this test can't
    # observe directly, so instead assert the cache actually holds an entry
    # for this scope (proving the empty result was stored, not skipped).
    cache_key = (tuple(sorted(dirs)), _IGNORE_KEY)
    assert cache_key in _VAULT_SNAPSHOT_CACHE
    assert get_vault_snapshot(vault, dirs) == []


def test_empty_real_folders_scope_is_cached(tmp_path):
    vault = str(tmp_path)
    dirs = [vault]

    first = vault_graph._list_real_folders(vault, dirs)
    assert first == []

    cache_key = (tuple(sorted(dirs)), _IGNORE_KEY)
    assert cache_key in vault_graph._REAL_FOLDERS_CACHE
    assert vault_graph._list_real_folders(vault, dirs) == []
