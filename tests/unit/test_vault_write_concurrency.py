"""
Unit tests for sympose.vault_write_concurrency — the ADR-129 optimistic-
concurrency guard's pure helper functions.
"""

import os
import time

from sympose import vault_write_concurrency


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestCurrentMtime:
    def test_returns_none_for_a_missing_file(self, tmp_path):
        assert vault_write_concurrency.current_mtime(str(tmp_path / "ghost.md")) is None

    def test_returns_the_files_actual_mtime(self, tmp_path):
        target = tmp_path / "note.md"
        _write(str(target), "hello")
        expected = os.stat(target).st_mtime
        assert vault_write_concurrency.current_mtime(str(target)) == expected


class TestMtimeMatches:
    def test_no_precondition_always_matches(self, tmp_path):
        assert vault_write_concurrency.mtime_matches(str(tmp_path / "ghost.md"), None) is True

    def test_matching_mtime_passes(self, tmp_path):
        target = tmp_path / "note.md"
        _write(str(target), "hello")
        mtime = vault_write_concurrency.current_mtime(str(target))
        assert vault_write_concurrency.mtime_matches(str(target), mtime) is True

    def test_stale_mtime_fails(self, tmp_path):
        target = tmp_path / "note.md"
        _write(str(target), "hello")
        stale = vault_write_concurrency.current_mtime(str(target))
        time.sleep(0.01)
        _write(str(target), "changed by someone else")
        assert vault_write_concurrency.mtime_matches(str(target), stale) is False

    def test_expecting_an_existing_file_that_was_deleted_is_a_conflict(self, tmp_path):
        target = tmp_path / "note.md"
        _write(str(target), "hello")
        mtime = vault_write_concurrency.current_mtime(str(target))
        os.remove(target)
        assert vault_write_concurrency.mtime_matches(str(target), mtime) is False
