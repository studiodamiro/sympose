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
# ensure_fresh — ADR-078.4 delta-read
# ---------------------------------------------------------------------------

def _fs_providers(mv):
    """(full_snapshot, read_notes) backed by real files under `mv`."""
    def _entry_for(rel):
        p = os.path.join(mv, rel)
        body = open(p, encoding="utf-8").read()
        return {"rel_path": rel.replace(os.sep, "/"), "abs_path": p,
                "full_content": body, "meta": {}, "body": body}

    def snapshot():
        out = []
        for root, dirs, files in os.walk(mv):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.endswith(".md"):
                    out.append(_entry_for(os.path.relpath(os.path.join(root, f), mv)))
        return out

    def read_notes(rels):
        return [_entry_for(r) for r in rels if os.path.exists(os.path.join(mv, r))]

    return snapshot, read_notes


def _norm(m):
    return (
        sorted((n["id"], n["rel_path"], n["folder"], n["bytes"], n["exists"]) for n in m["nodes"]),
        sorted((l["source"], l["target"]) for l in m["links"]),
        dict(sorted(m["folders"].items())),
        m["meta"]["note_count"],
    )


class TestDeltaRead:
    def _vault(self, tmp_path):
        v = tmp_path / "vault"
        (v / "Daily").mkdir(parents=True)
        (v / "a.md").write_text("# A\n[[b]] [[ghost]]\n")
        (v / "b.md").write_text("# B\n")
        (v / "Daily" / "2026-09-09.md").write_text("# Day\n[[a]]\n")
        return str(v), str(tmp_path / "ws")

    def test_delta_reparses_only_changed_notes(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        snap, read = _fs_providers(mv)
        vm.ensure_fresh(ws, mv, snap, read_notes=read, debounce=0)  # cold: full build

        seen = {"rels": None}
        spy = lambda rels: (seen.__setitem__("rels", list(rels)), read(rels))[1]
        (tmp_path / "vault" / "b.md").write_text("# B\nnow links [[a]]\n")
        _bump_mtime(os.path.join(mv, "b.md"))
        _bump_mtime(mv)
        m = vm.ensure_fresh(ws, mv, snap, read_notes=spy, debounce=0)

        assert seen["rels"] == ["b.md"]                       # only the changed note
        assert ("b", "a") in {(l["source"], l["target"]) for l in m["links"]}

    def test_delta_handles_add_and_delete(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        snap, read = _fs_providers(mv)
        vm.ensure_fresh(ws, mv, snap, read_notes=read, debounce=0)

        os.remove(os.path.join(mv, "b.md"))
        (tmp_path / "vault" / "c.md").write_text("# C\n[[a]]\n")
        _bump_mtime(mv)
        m = vm.ensure_fresh(ws, mv, snap, read_notes=read, debounce=0)

        ids = {n["id"] for n in m["nodes"] if n["exists"]}
        assert "c" in ids and "b" not in ids
        assert all(l["source"] != "b" for l in m["links"])
        assert m["nodes"] and any(n["id"] == "b" and not n["exists"] for n in m["nodes"])  # b is now a ghost (a still links it)

    def test_delta_result_equals_a_full_build_for_the_same_disk_state(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        snap, read = _fs_providers(mv)
        vm.ensure_fresh(ws, mv, snap, read_notes=read, debounce=0)

        # mutate disk: change one, add one, delete one, rename one
        (tmp_path / "vault" / "a.md").write_text("# A v2\n[[b]]\n")
        (tmp_path / "vault" / "new.md").write_text("# New\n[[a]] [[missing]]\n")
        os.remove(os.path.join(mv, "b.md"))
        os.rename(os.path.join(mv, "Daily", "2026-09-09.md"), os.path.join(mv, "Daily", "2026-09-10.md"))
        for p in (mv, os.path.join(mv, "Daily")):
            _bump_mtime(p)

        delta = vm.ensure_fresh(ws, mv, snap, read_notes=read, debounce=0)
        vm._mem_cache.clear()
        os.remove(vm.manifest_path(ws, mv))
        full = vm.ensure_fresh(ws, mv, snap, read_notes=read, debounce=0)  # cold => full build

        assert _norm(delta) == _norm(full)

    def test_no_reader_falls_back_to_full_rebuild(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        snap, _ = _fs_providers(mv)
        vm.ensure_fresh(ws, mv, snap, debounce=0)
        (tmp_path / "vault" / "b.md").write_text("# B changed\n")
        _bump_mtime(mv)
        m = vm.ensure_fresh(ws, mv, snap, debounce=0)  # no read_notes -> full
        assert m is not None and {n["id"] for n in m["nodes"] if n["exists"]} == {"a", "b", "2026-09-09"}

    def test_dirs_touched_but_no_note_change_reuses_prev(self, tmp_path):
        mv, ws = self._vault(tmp_path)
        snap, read = _fs_providers(mv)
        vm.ensure_fresh(ws, mv, snap, read_notes=read, debounce=0)
        called = {"n": 0}
        spy = lambda rels: (called.__setitem__("n", called["n"] + 1), read(rels))[1]
        (tmp_path / "vault" / "Daily" / "sub").mkdir()  # touches Daily mtime, no .md change
        _bump_mtime(mv)
        vm.ensure_fresh(ws, mv, snap, read_notes=spy, debounce=0)
        assert called["n"] == 0


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

class TestFormatDigest:
    def _manifest(self, tmp_path):
        return vm.build(str(tmp_path), [
            _entry("Daily/2026/a.md", "[[Arch]]", tags=["jour"]),
            _entry("Daily/2026/b.md", "[[Arch]] [[Ghost]]", tags=["jour"]),
            _entry("Projects/Arch.md", "", tags=["proj"]),
        ])

    def test_digest_lists_top_level_folders_with_counts(self, tmp_path):
        from sympose.vault import VaultManager
        d = VaultManager.format_manifest_digest(self._manifest(tmp_path))
        assert "`Daily/` — 2 notes" in d and "`Projects/` — 1 note" in d

    def test_digest_reports_tags_hubs_and_ghosts(self, tmp_path):
        from sympose.vault import VaultManager
        d = VaultManager.format_manifest_digest(self._manifest(tmp_path))
        assert "#jour (2)" in d
        assert "[[Arch]] (2)" in d
        assert "Unresolved links:** 1" in d and "[[Ghost]]" in d

    def test_digest_carries_no_note_bodies_and_flags_structure_only(self, tmp_path):
        from sympose.vault import VaultManager
        m = vm.build(str(tmp_path), [_entry("a.md", "TOP SECRET BODY", tags=["x"])])
        d = VaultManager.format_manifest_digest(m)
        assert "TOP SECRET BODY" not in d
        assert "Structure only" in d

    def test_flat_vault_has_no_folder_rows(self, tmp_path):
        from sympose.vault import VaultManager
        d = VaultManager.format_manifest_digest(vm.build(str(tmp_path), [_entry("a.md"), _entry("b.md")]))
        assert "flat vault" in d


class TestResolveTurnContextStructureTier:
    def _enable(self, monkeypatch, tmp_vault_dir):
        from sympose.vault import config_manager
        real_get = config_manager.get
        ov = {"vault.manifest.enabled": True, "vault.manifest.check_debounce_seconds": 0.0,
              "vault.manifest.max_nodes": 0}
        monkeypatch.setattr(config_manager, "get", lambda k, d=None: ov.get(k, real_get(k, d)))
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        (tmp_vault_dir / "Daily").mkdir()
        (tmp_vault_dir / "Daily" / "2026-09-09.md").write_text("# Day\n#jour\n")

    @pytest.mark.parametrize("q", [
        "how is my vault organised?",
        "how many notes are in my vault?",
        "so, hows our vault doing? how many files are in?",
        "give me a vault summary",
        "what's the breakdown of my vault",
    ])
    def test_structure_query_returns_the_map_when_enabled(self, tmp_vault_dir, monkeypatch, q):
        from sympose.vault import VaultManager
        self._enable(monkeypatch, tmp_vault_dir)
        prof = {"vault_folders": ["*"], "skills": ["vault_recall"], "handle": "t"}
        out = VaultManager.resolve_turn_context(prof, q)
        assert out is not None and out.startswith("### Ground-Truth Vault Structure Map")

    def test_subject_query_does_not_hijack_search(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        self._enable(monkeypatch, tmp_vault_dir)
        prof = {"vault_folders": ["*"], "skills": ["vault_recall"], "handle": "t"}
        out = VaultManager.resolve_turn_context(prof, "what's in my vault about Rilke?")
        assert out is None or not out.startswith("### Ground-Truth Vault Structure Map")

    def test_structure_query_inert_when_manifest_disabled(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        from sympose.vault import config_manager
        real_get = config_manager.get
        monkeypatch.setattr(config_manager, "get",
                            lambda k, d=None: False if k == "vault.manifest.enabled" else real_get(k, d))
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        (tmp_vault_dir / "Daily").mkdir()
        (tmp_vault_dir / "Daily" / "2026-09-09.md").write_text("# Day\n#jour\n")
        prof = {"vault_folders": ["*"], "skills": ["vault_recall"], "handle": "t"}
        out = VaultManager.resolve_turn_context(prof, "how is my vault organised?")
        assert out is None or not out.startswith("### Ground-Truth Vault Structure Map")


class TestVaultGraph:
    def _vault(self, tmp_vault_dir):
        (tmp_vault_dir / "Notes").mkdir()
        (tmp_vault_dir / "Notes" / "hub.md").write_text("# Hub\ntags: [x]\n[[a]] [[b]] [[ghost]]\n")
        (tmp_vault_dir / "Notes" / "a.md").write_text("# A\n")
        (tmp_vault_dir / "Notes" / "b.md").write_text("# B\n[[a]]\n")

    def test_empty_graph_when_no_vault(self, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", "")
        assert VaultManager.get_vault_graph() == {"nodes": [], "links": []}

    def test_nebula_shape_and_degree_weight(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        self._vault(tmp_vault_dir)
        g = VaultManager.get_vault_graph()
        by_id = {n["id"]: n for n in g["nodes"]}
        assert set(by_id["hub"]) == {"id", "label", "folder", "tags", "val", "exists"}
        # hub: 3 outbound -> val 4 ; a: 2 inbound -> val 3 ; b: 1 in + 1 out -> val 3
        assert by_id["hub"]["val"] == 4
        assert by_id["a"]["val"] == 3
        assert by_id["ghost"]["exists"] is False
        assert {(l["source"], l["target"]) for l in g["links"]} >= {("hub", "a"), ("hub", "ghost"), ("b", "a")}

    def test_long_quote_style_label_is_clipped_but_id_is_whole(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        (tmp_vault_dir / "Quotes").mkdir()
        quote = "Art is a lie that enables us to realize the truth, at least the truth that is given to us to understand"
        (tmp_vault_dir / "Quotes" / f"{quote}.md").write_text("---\ntags: [quote]\n---")
        g = VaultManager.get_vault_graph()
        node = next(n for n in g["nodes"] if n["id"] == quote)
        assert node["id"] == quote                       # full stem kept for links/search
        assert len(node["label"]) <= 64 and node["label"].endswith("…")

    def test_works_with_knob_disabled_via_ephemeral_build(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        from sympose.vault import config_manager
        real_get = config_manager.get
        monkeypatch.setattr(config_manager, "get",
                            lambda k, d=None: False if k == "vault.manifest.enabled" else real_get(k, d))
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        self._vault(tmp_vault_dir)
        g = VaultManager.get_vault_graph()
        assert "hub" in {n["id"] for n in g["nodes"]} and g["links"]


class TestWorkerManifestInjection:
    def _enable(self, monkeypatch, tmp_vault_dir):
        from sympose.vault import config_manager
        real_get = config_manager.get
        ov = {"vault.manifest.enabled": True, "vault.manifest.check_debounce_seconds": 0.0,
              "vault.manifest.max_nodes": 0}
        monkeypatch.setattr(config_manager, "get", lambda k, d=None: ov.get(k, real_get(k, d)))
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))

    def test_vault_recall_worker_gets_the_structure_map(self, tmp_vault_dir, monkeypatch):
        from sympose.workers import WorkerEngine, WorkerTask
        self._enable(monkeypatch, tmp_vault_dir)
        (tmp_vault_dir / "Projects").mkdir()
        (tmp_vault_dir / "Projects" / "x.md").write_text("# X\n[[y]]\n")
        task = WorkerTask("count notes", skills=["vault_recall"], parent_agent="samantha")
        sysprompt = WorkerEngine._build_worker_context(task)[0]
        assert "Ground-Truth Vault Structure Map" in sysprompt

    def test_non_vault_worker_gets_no_map(self, tmp_vault_dir, monkeypatch):
        from sympose.workers import WorkerEngine, WorkerTask
        self._enable(monkeypatch, tmp_vault_dir)
        (tmp_vault_dir / "a.md").write_text("hi")
        task = WorkerTask("do a thing", skills=["web_search"], parent_agent="samantha")
        sysprompt = WorkerEngine._build_worker_context(task)[0]
        assert "Ground-Truth Vault Structure Map" not in sysprompt


class TestVaultManagerAccessor:
    def test_get_manifest_none_when_knob_off(self, tmp_vault_dir, monkeypatch):
        from sympose.vault import VaultManager
        from sympose.vault import config_manager
        real_get = config_manager.get
        monkeypatch.setattr(config_manager, "get",
                            lambda k, d=None: False if k == "vault.manifest.enabled" else real_get(k, d))
        monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_vault_dir))
        assert VaultManager.get_manifest() is None

    def test_get_manifest_none_when_no_vault_configured(self, monkeypatch):
        from sympose.vault import VaultManager
        monkeypatch.setenv("MASTER_VAULT_PATH", "")
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
