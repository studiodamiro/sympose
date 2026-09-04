"""
Unit tests for sympose.vault_index — the ADR-070.5 sqlite_fts search tier.
"""

import os
import sqlite3
import pytest

from sympose import vault_index


def _entry(rel_path, file_name, title, body, tags=None):
    return {
        "rel_path": rel_path, "file_name": file_name,
        "meta": {"title": title, "tags": tags or []}, "body": body,
    }


class TestIndexPath:
    def test_deterministic_per_vault(self, tmp_path):
        p1 = vault_index.index_path(str(tmp_path / "ws"), "/some/vault")
        p2 = vault_index.index_path(str(tmp_path / "ws"), "/some/vault")
        assert p1 == p2

    def test_different_vaults_get_different_paths(self, tmp_path):
        p1 = vault_index.index_path(str(tmp_path / "ws"), "/vault/a")
        p2 = vault_index.index_path(str(tmp_path / "ws"), "/vault/b")
        assert p1 != p2

    def test_lives_under_workspace_not_vault(self, tmp_path):
        ws = str(tmp_path / "ws")
        p = vault_index.index_path(ws, "/some/vault")
        assert p.startswith(ws)


class TestEnsureFreshAndQuery:
    def test_rebuild_indexes_snapshot(self, tmp_path):
        ws, vault = str(tmp_path / "ws"), str(tmp_path / "vault")
        os.makedirs(vault)
        snapshot = [_entry("Thoughts/creativity.md", "creativity.md", "Creativity", "Vanilla CSS keeps things simple.")]
        assert vault_index.ensure_fresh(ws, vault, lambda: snapshot) is True

        results = vault_index.query(ws, vault, "vanilla css", [vault], 10)
        assert results is not None
        assert any("creativity.md" in r["rel_path"] for r in results)

    def test_no_match_returns_empty_list(self, tmp_path):
        ws, vault = str(tmp_path / "ws"), str(tmp_path / "vault")
        os.makedirs(vault)
        vault_index.ensure_fresh(ws, vault, lambda: [_entry("a.md", "a.md", "A", "unrelated content")])
        results = vault_index.query(ws, vault, "nonexistent_zzz_term", [vault], 10)
        assert results == []

    def test_scope_filters_by_directory_prefix(self, tmp_path):
        ws, vault = str(tmp_path / "ws"), str(tmp_path / "vault")
        os.makedirs(os.path.join(vault, "Grace"))
        os.makedirs(os.path.join(vault, "Anais"))
        snapshot = [
            _entry("Grace/roadmap.md", "roadmap.md", "Roadmap", "shipping the sqlite index"),
            _entry("Anais/journal.md", "journal.md", "Journal", "shipping feelings today"),
        ]
        vault_index.ensure_fresh(ws, vault, lambda: snapshot)

        grace_only = vault_index.query(ws, vault, "shipping", [os.path.join(vault, "Grace")], 10)
        rel_paths = [r["rel_path"] for r in grace_only]
        assert "Grace/roadmap.md" in rel_paths
        assert "Anais/journal.md" not in rel_paths

    def test_second_call_without_drift_skips_rebuild(self, tmp_path, monkeypatch):
        ws, vault = str(tmp_path / "ws"), str(tmp_path / "vault")
        os.makedirs(vault)
        calls = {"n": 0}
        def snapshot_provider():
            calls["n"] += 1
            return [_entry("a.md", "a.md", "A", "content")]
        vault_index.ensure_fresh(ws, vault, snapshot_provider)
        vault_index.ensure_fresh(ws, vault, snapshot_provider)
        assert calls["n"] == 1, "second ensure_fresh call should skip rebuild when mtime hasn't drifted"


class TestUpsertNote:
    def test_upserted_note_is_immediately_queryable(self, tmp_path):
        ws, vault = str(tmp_path / "ws"), str(tmp_path / "vault")
        os.makedirs(vault)
        vault_index.ensure_fresh(ws, vault, lambda: [])
        vault_index.upsert_note(ws, vault, "New/idea.md", "idea.md", {"title": "Idea"}, "A fresh incremental note.")
        results = vault_index.query(ws, vault, "incremental", [vault], 10)
        assert results is not None
        assert any(r["rel_path"] == "New/idea.md" for r in results)

    def test_upsert_replaces_previous_content(self, tmp_path):
        ws, vault = str(tmp_path / "ws"), str(tmp_path / "vault")
        os.makedirs(vault)
        vault_index.upsert_note(ws, vault, "a.md", "a.md", {"title": "A"}, "original body")
        vault_index.upsert_note(ws, vault, "a.md", "a.md", {"title": "A"}, "updated body")
        stale = vault_index.query(ws, vault, "original", [vault], 10)
        fresh = vault_index.query(ws, vault, "updated", [vault], 10)
        assert stale == []
        assert any(r["rel_path"] == "a.md" for r in fresh)


class TestVaultManagerSqliteFtsWiring:
    """End-to-end through VaultManager.search_structured/write_note/append_note
    with `vault.search_mode: sqlite_fts` active — not just the vault_index
    module in isolation."""

    @pytest.fixture
    def fts_workspace(self, tmp_path, monkeypatch):
        vault, ws = tmp_path / "vault", tmp_path / "ws"
        vault.mkdir()
        ws.mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(vault))

        from sympose.config import config_manager
        orig_config_path = config_manager.config_path
        orig_search_mode = config_manager.get("vault.search_mode")
        config_manager.config_path = str(ws / "config.yaml")
        config_manager.set("vault.search_mode", "sqlite_fts")
        try:
            yield vault, ws
        finally:
            config_manager.config_path = orig_config_path
            config_manager.set("vault.search_mode", orig_search_mode)

    def test_write_note_is_immediately_searchable(self, fts_workspace):
        vault, ws = fts_workspace
        from sympose.vault import VaultManager
        profile = {"handle": "test-fts", "vault_folder": "", "vault_folders": ["*"]}

        VaultManager.write_note(profile, "Thoughts/second.md", "Prefers vanilla CSS over Tailwind.")
        results = VaultManager.search_structured(profile, "vanilla css")
        assert any("second.md" in r["rel_path"] for r in results)
        assert os.path.isdir(ws / ".vault_index"), "index should live under the workspace"
        assert not os.path.isdir(vault / ".vault_index"), "index must never be written inside the vault itself"

    def test_pre_existing_note_found_via_full_rebuild(self, fts_workspace):
        vault, ws = fts_workspace
        (vault / "Thoughts").mkdir()
        (vault / "Thoughts" / "creativity.md").write_text("---\ntitle: Creativity\n---\nVanilla CSS keeps things simple.")

        from sympose.vault import VaultManager
        profile = {"handle": "test-fts-2", "vault_folder": "", "vault_folders": ["*"]}
        results = VaultManager.search_structured(profile, "vanilla css")
        assert any("creativity.md" in r["rel_path"] for r in results)

    def test_append_note_reindexes_full_current_content(self, fts_workspace):
        vault, ws = fts_workspace
        from sympose.vault import VaultManager
        profile = {"handle": "test-fts-3", "vault_folder": "", "vault_folders": ["*"]}

        VaultManager.write_note(profile, "log.md", "Initial entry.")
        VaultManager.append_note(profile, "log.md", "Second entry about kayaking.")
        results = VaultManager.search_structured(profile, "kayaking")
        assert any("log.md" in r["rel_path"] for r in results)

    def test_direct_mode_still_used_by_default_config(self, tmp_path, monkeypatch):
        """Sanity check the fixture itself: without the sqlite_fts override,
        search_structured never touches vault_index at all."""
        vault, ws = tmp_path / "vault2", tmp_path / "ws2"
        vault.mkdir()
        ws.mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(vault))
        (vault / "note.md").write_text("Hello world content.")

        from sympose.config import config_manager
        orig_config_path = config_manager.config_path
        orig_search_mode = config_manager.get("vault.search_mode")
        config_manager.config_path = str(ws / "config.yaml")
        config_manager.set("vault.search_mode", "direct")
        try:
            from sympose.vault import VaultManager
            profile = {"handle": "test-direct", "vault_folder": "", "vault_folders": ["*"]}
            results = VaultManager.search_structured(profile, "hello world")
            assert any("note.md" in r["rel_path"] for r in results)
            assert not os.path.isdir(ws / ".vault_index")
        finally:
            config_manager.config_path = orig_config_path
            config_manager.set("vault.search_mode", orig_search_mode)


class TestFTS5Unavailable:
    def test_degrades_cleanly_when_fts5_missing(self, tmp_path, monkeypatch):
        """Simulates a Python build whose sqlite3 lacks the FTS5 extension."""
        real_connect = sqlite3.connect

        class _NoFTS5Conn:
            def __init__(self, real):
                self._real = real
            def execute(self, sql, *a):
                if "VIRTUAL TABLE" in sql:
                    raise sqlite3.OperationalError("no such module: fts5")
                return self._real.execute(sql, *a)
            def __getattr__(self, name):
                return getattr(self._real, name)

        def fake_connect(path, timeout=5.0):
            return _NoFTS5Conn(real_connect(path, timeout=timeout))

        monkeypatch.setattr(sqlite3, "connect", fake_connect)
        vault_index._FTS5_OK.clear()

        ws, vault = str(tmp_path / "ws"), str(tmp_path / "vault")
        os.makedirs(vault)
        assert vault_index.ensure_fresh(ws, vault, lambda: []) is False
        assert vault_index.query(ws, vault, "anything", [vault], 10) is None
        vault_index.upsert_note(ws, vault, "a.md", "a.md", {}, "body")  # must not raise
