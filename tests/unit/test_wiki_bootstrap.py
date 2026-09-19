"""
Unit tests for sympose.wiki_bootstrap.bootstrap_wiki_layer (ADR-132).
"""

from sympose.vault import VaultManager
from sympose.wiki_bootstrap import bootstrap_wiki_layer


def _wiki_config(root="", sources="Sources", schema="WIKI.md", log="log.md"):
    values = {
        "wiki.root": root,
        "wiki.raw_sources_subdir": sources,
        "wiki.schema_file": schema,
        "wiki.log_file": log,
    }
    return lambda key, default=None: values.get(key, default)


class TestBootstrapWikiLayer:
    def test_noop_when_wiki_root_is_unset(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get", _wiki_config(root="")
        )
        bootstrap_wiki_layer({"vault_folders": ["*"]})
        assert list(tmp_path.iterdir()) == []

    def test_seeds_schema_log_and_sources_folder_when_root_is_set(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get", _wiki_config(root="Wiki")
        )
        bootstrap_wiki_layer({"vault_folders": ["*"]})

        schema = tmp_path / "Wiki" / "WIKI.md"
        log = tmp_path / "Wiki" / "log.md"
        sources = tmp_path / "Wiki" / "Sources"
        assert schema.exists()
        assert "LLM Wiki Schema" in schema.read_text()
        assert log.exists()
        assert "Wiki Log" in log.read_text()
        assert sources.is_dir()

    def test_respects_custom_subdir_and_filenames(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get",
            _wiki_config(root="Knowledge", sources="Raw", schema="SCHEMA.md", log="LOG.md"),
        )
        bootstrap_wiki_layer({"vault_folders": ["*"]})

        assert (tmp_path / "Knowledge" / "SCHEMA.md").exists()
        assert (tmp_path / "Knowledge" / "LOG.md").exists()
        assert (tmp_path / "Knowledge" / "Raw").is_dir()

    def test_does_not_overwrite_a_hand_edited_schema_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get", _wiki_config(root="Wiki")
        )
        wiki_dir = tmp_path / "Wiki"
        wiki_dir.mkdir()
        (wiki_dir / "WIKI.md").write_text("# My hand-edited schema\n")

        bootstrap_wiki_layer({"vault_folders": ["*"]})

        assert (wiki_dir / "WIKI.md").read_text() == "# My hand-edited schema\n"

    def test_is_idempotent_across_repeated_calls(self, tmp_path, monkeypatch):
        """bootstrap_missing_artifacts runs on every profile reload — this
        must be a safe no-op the second time, not an error or a duplicate
        write."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get", _wiki_config(root="Wiki")
        )
        profile = {"vault_folders": ["*"]}
        bootstrap_wiki_layer(profile)
        bootstrap_wiki_layer(profile)
        assert (tmp_path / "Wiki" / "WIKI.md").exists()

    def test_persona_scoped_outside_wiki_root_does_not_error(self, tmp_path, monkeypatch):
        """A persona whose sandbox doesn't reach wiki.root harmlessly
        no-ops (NOTE_DENIED under the hood) rather than raising."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get", _wiki_config(root="Wiki")
        )
        bootstrap_wiki_layer({"vault_folders": ["Journal"]})
        assert not (tmp_path / "Wiki").exists()

    def test_root_with_surrounding_slashes_is_normalized(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get", _wiki_config(root="/Wiki/")
        )
        bootstrap_wiki_layer({"vault_folders": ["*"]})
        assert (tmp_path / "Wiki" / "WIKI.md").exists()

    def test_seeded_notes_are_reindexed_and_added_to_manifest(
        self, tmp_path, monkeypatch
    ):
        """Regression: bootstrap used to call vault_write directly, bypassing
        the reindex/manifest hooks every other writer threads through
        VaultManager — a freshly-bootstrapped wiki looked empty to search
        and to wiki_lint's orphan-page check until an unrelated full
        reindex ran."""
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(
            "sympose.wiki_bootstrap.config_manager.get", _wiki_config(root="Wiki")
        )
        reindexed: list[str] = []
        manifested: list[str] = []
        monkeypatch.setattr(
            VaultManager,
            "_reindex_note_if_enabled",
            classmethod(lambda cls, mv, target_file: reindexed.append(target_file)),
        )
        monkeypatch.setattr(
            VaultManager,
            "_update_manifest_if_enabled",
            classmethod(lambda cls, mv, target_file: manifested.append(target_file)),
        )

        bootstrap_wiki_layer({"vault_folders": ["*"]})

        schema = str(tmp_path / "Wiki" / "WIKI.md")
        log = str(tmp_path / "Wiki" / "log.md")
        assert schema in reindexed
        assert log in reindexed
        assert schema in manifested
        assert log in manifested
