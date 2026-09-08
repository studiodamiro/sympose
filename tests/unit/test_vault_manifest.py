"""
Unit tests for sympose.vault_manifest — the ADR-078 materialized structural map.
"""

import os
import time
import json
import pytest

from sympose import vault_manifest as vm


@pytest.fixture(autouse=True)
def _clean_module_state():
    vm._mem_cache.clear()
    vm._last_check.clear()
    vm._locks.clear()
    yield
    vm._mem_cache.clear()
    vm._last_check.clear()
    vm._locks.clear()


def _entry(rel_path, content="", tags=None, title=None):
    meta = {}
    if tags is not None:
        meta["tags"] = tags
    if title is not None:
        meta["title"] = title
    return {"rel_path": rel_path, "full_content": content, "meta": meta, "abs_path": ""}


def _bump_mtime(path, delta=10):
    t = time.time() + delta
    os.utime(path, (t, t))


# ---------------------------------------------------------------------------
# manifest_path
# ---------------------------------------------------------------------------

class TestManifestPath:
    def test_deterministic_per_vault(self, tmp_path):
        a = vm.manifest_path(str(tmp_path / "ws"), "/some/vault")
        b = vm.manifest_path(str(tmp_path / "ws"), "/some/vault")
        assert a == b and a.endswith(".manifest.json")

    def test_different_vaults_differ(self, tmp_path):
        a = vm.manifest_path(str(tmp_path / "ws"), "/vault/a")
        b = vm.manifest_path(str(tmp_path / "ws"), "/vault/b")
        assert a != b

    def test_lives_under_workspace_not_vault(self, tmp_path):
        ws = str(tmp_path / "ws")
        assert vm.manifest_path(ws, "/some/vault").startswith(ws)


# ---------------------------------------------------------------------------
# build — pure projection
# ---------------------------------------------------------------------------

class TestBuild:
    def test_one_real_node_per_note(self, tmp_path):
        m = vm.build(str(tmp_path), [_entry("a.md"), _entry("Sub/b.md")])
        real = [n for n in m["nodes"] if n["exists"]]
        assert sorted(n["id"] for n in real) == ["a", "b"]
        assert m["meta"]["note_count"] == 2

    def test_folder_is_top_level_segment(self, tmp_path):
        m = vm.build(str(tmp_path), [_entry("Daily/2026/09/2026-09-01.md")])
        assert m["nodes"][0]["folder"] == "Daily"

    def test_folders_map_counts_every_depth(self, tmp_path):
        m = vm.build(str(tmp_path), [_entry("Daily/2026/09/x.md"), _entry("Daily/2026/08/y.md")])
        assert m["folders"]["Daily"] == 2
        assert m["folders"]["Daily/2026"] == 2
        assert m["folders"]["Daily/2026/09"] == 1

    def test_tags_parsed_from_list_and_string(self, tmp_path):
        m = vm.build(str(tmp_path), [
            _entry("a.md", tags=["jour", "#grief"]),
            _entry("b.md", tags="quote, not-mine"),
        ])
        by_id = {n["id"]: n for n in m["nodes"]}
        assert by_id["a"]["tags"] == ["jour", "grief"]
        assert by_id["b"]["tags"] == ["quote", "not-mine"]

    def test_nodes_carry_no_body(self, tmp_path):
        m = vm.build(str(tmp_path), [_entry("a.md", "secret body text")])
        node = m["nodes"][0]
        assert set(node) == {"id", "rel_path", "folder", "tags", "title", "bytes", "mtime", "exists"}
        assert "secret body text" not in json.dumps(m)
        assert node["bytes"] == len("secret body text")

    def test_wikilinks_become_links(self, tmp_path):
        m = vm.build(str(tmp_path), [_entry("a.md", "see [[Other]] and [[Third]]"), _entry("Other.md")])
        pairs = {(l["source"], l["target"]) for l in m["links"]}
        assert ("a", "Other") in pairs and ("a", "Third") in pairs

    def test_alias_and_heading_wikilinks_resolve_to_stem(self, tmp_path):
        m = vm.build(str(tmp_path), [_entry("a.md", "[[Note#Heading|the alias]]")])
        assert m["links"][0]["target"] == "Note"

    def test_unresolved_target_is_ghost_resolved_is_not(self, tmp_path):
        m = vm.build(str(tmp_path), [_entry("a.md", "[[Ghost]] [[Real]]"), _entry("Real.md")])
        by_id = {n["id"]: n for n in m["nodes"]}
        assert by_id["Ghost"]["exists"] is False
        assert by_id["Real"]["exists"] is True
        assert "Real" not in [n["id"] for n in m["nodes"] if not n["exists"]]


# ---------------------------------------------------------------------------
# ensure_fresh — access-triggered freshness
# ---------------------------------------------------------------------------

class TestEnsureFresh:
    def _vault(self, tmp_path):
        v = tmp_path / "vault"
        (v / "Notes").mkdir(parents=True)
        return str(v), str(tmp_path / "ws")

    def test_cold_build_writes_file(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        m = vm.ensure_fresh(ws, mv, lambda: [_entry("Notes/a.md", "[[b]]")], debounce=0)
        assert m is not None and m["nodes"][0]["id"] == "a"
        assert os.path.exists(vm.manifest_path(ws, mv))

    def test_unchanged_watermark_skips_rebuild(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return [_entry("Notes/a.md")]

        vm.ensure_fresh(ws, mv, provider, debounce=0)
        vm.ensure_fresh(ws, mv, provider, debounce=0)
        assert calls["n"] == 1

    def test_mtime_drift_triggers_rebuild(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return [_entry("Notes/a.md")] if calls["n"] == 1 else [_entry("Notes/a.md"), _entry("Notes/c.md")]

        vm.ensure_fresh(ws, mv, provider, debounce=0)
        _bump_mtime(mv)
        m = vm.ensure_fresh(ws, mv, provider, debounce=0)
        assert calls["n"] == 2
        assert {n["id"] for n in m["nodes"]} == {"a", "c"}

    def test_debounce_serves_cache_without_rescan(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return [_entry("Notes/a.md")]

        vm.ensure_fresh(ws, mv, provider, debounce=100)
        _bump_mtime(mv)
        vm.ensure_fresh(ws, mv, provider, debounce=100)  # within debounce window
        assert calls["n"] == 1

    def test_max_nodes_truncates(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        snap = [_entry(f"Notes/n{i}.md") for i in range(10)]
        m = vm.ensure_fresh(ws, mv, lambda: snap, debounce=0, max_nodes=4)
        assert len(m["nodes"]) == 4 and m["meta"]["truncated"] is True

    def test_provider_failure_returns_prior_manifest(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        vm.ensure_fresh(ws, mv, lambda: [_entry("Notes/a.md")], debounce=0)
        _bump_mtime(mv)

        def boom():
            raise RuntimeError("walk failed")

        m = vm.ensure_fresh(ws, mv, boom, debounce=0)
        assert m is not None and m["nodes"][0]["id"] == "a"


# ---------------------------------------------------------------------------
# patch_note — write-through
# ---------------------------------------------------------------------------

class TestPatchNote:
    def _vault(self, tmp_path):
        v = tmp_path / "vault"
        v.mkdir()
        return str(v), str(tmp_path / "ws")

    def test_noop_when_no_manifest_exists(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        vm.patch_note(ws, mv, "a.md", {}, "body")
        assert vm.load(ws, mv) is None

    def test_patch_upserts_node_and_links(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        vm.ensure_fresh(ws, mv, lambda: [_entry("a.md")], debounce=0)
        vm.patch_note(ws, mv, "b.md", {"tags": ["new"]}, "links to [[a]]")
        m = vm.load(ws, mv)
        by_id = {n["id"]: n for n in m["nodes"]}
        assert by_id["b"]["tags"] == ["new"]
        assert ("b", "a") in {(l["source"], l["target"]) for l in m["links"]}
        assert m["meta"]["note_count"] == 2

    def test_patch_replaces_prior_links_for_that_note(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        vm.ensure_fresh(ws, mv, lambda: [_entry("a.md", "[[old]]")], debounce=0)
        vm.patch_note(ws, mv, "a.md", {}, "now points [[new]]")
        targets = {l["target"] for l in vm.load(ws, mv)["links"] if l["source"] == "a"}
        assert targets == {"new"}

    def test_patch_promotes_a_ghost_to_a_real_node(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        vm.ensure_fresh(ws, mv, lambda: [_entry("a.md", "[[b]]")], debounce=0)
        assert [n for n in vm.load(ws, mv)["nodes"] if n["id"] == "b"][0]["exists"] is False
        vm.patch_note(ws, mv, "b.md", {}, "real now")
        b_nodes = [n for n in vm.load(ws, mv)["nodes"] if n["id"] == "b"]
        assert len(b_nodes) == 1 and b_nodes[0]["exists"] is True

    def test_patch_adds_ghost_for_new_unresolved_target(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        vm.ensure_fresh(ws, mv, lambda: [_entry("a.md")], debounce=0)
        vm.patch_note(ws, mv, "a.md", {}, "points at [[nowhere]]")
        by_id = {n["id"]: n for n in vm.load(ws, mv)["nodes"]}
        assert by_id["nowhere"]["exists"] is False

    def test_patch_restamps_watermark_so_ensure_fresh_skips(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        vm.ensure_fresh(ws, mv, lambda: [_entry("a.md")], debounce=0)
        vm.patch_note(ws, mv, "b.md", {}, "body")
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return [_entry("a.md"), _entry("b.md")]

        vm.ensure_fresh(ws, mv, provider, debounce=0)
        assert calls["n"] == 0


# ---------------------------------------------------------------------------
# VaultManager integration
# ---------------------------------------------------------------------------

class TestVaultManagerAccessor:
    def test_get_manifest_none_when_disabled(self):
        from sympose.vault import VaultManager
        assert VaultManager.get_manifest() is None

    def test_get_manifest_and_write_through_when_enabled(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        from sympose.vault import config_manager

        real_get = config_manager.get
        overrides = {"vault.manifest.enabled": True, "vault.manifest.check_debounce_seconds": 0.0,
                     "vault.manifest.max_nodes": 0}
        monkeypatch.setattr(config_manager, "get",
                            lambda k, d=None: overrides.get(k, real_get(k, d)))
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        (tmp_vault_dir / "Notes").mkdir()
        (tmp_vault_dir / "Notes" / "seed.md").write_text("# Seed\n[[target]]\n")

        m = VaultManager.get_manifest()
        assert m is not None
        assert "seed" in {n["id"] for n in m["nodes"]}

        VaultManager.write_note({"vault_folders": ["Notes"], "handle": "t"}, "fresh", "body [[seed]]")
        m2 = VaultManager.get_manifest()
        assert "fresh" in {n["id"] for n in m2["nodes"] if n["exists"]}
