"""Tests for sympose.vault_graph.get_vault_graph — the persona-scoped Knowledge
Nebula projection (docs/decisions/010)."""

from helpers import write_persona
import os

import pytest
from fastapi import HTTPException

from sympose import server_handlers as h
from sympose import vault_graph


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path / "vault"))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    root = tmp_path / "vault"
    root.mkdir()
    return str(root)


def _write(root: str, rel_path: str, content: str) -> None:
    full = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


WHOLE = {"vault_folders": ["*"]}
CODE_ONLY = {"vault_folders": ["Code"]}


def _ids(graph):
    return {n["id"] for n in graph["nodes"]}


def test_whole_vault_persona_sees_every_note_and_link(vault):
    _write(vault, "Code/A.md", "links to [[B]] and [[Diary]]")
    _write(vault, "Code/B.md", "plain")
    _write(vault, "Journal/Diary.md", "private")

    graph = vault_graph.get_vault_graph(WHOLE)

    assert _ids(graph) == {"Code/A.md", "Code/B.md", "Journal/Diary.md"}
    assert len(graph["links"]) == 2


def test_restricted_persona_sees_only_its_folders(vault):
    _write(vault, "Code/A.md", "links to [[B]]")
    _write(vault, "Code/B.md", "plain")
    _write(vault, "Journal/Diary.md", "private, links to [[A]]")

    graph = vault_graph.get_vault_graph(CODE_ONLY)

    assert _ids(graph) == {"Code/A.md", "Code/B.md"}
    assert graph["links"] == [
        {"source": "Code/A.md", "target": "Code/B.md", "target_stem": "B"}
    ]


def test_a_link_to_an_out_of_scope_note_leaks_neither_node_nor_ghost(vault):
    """The reason the whole-vault manifest is filtered instead of built
    from only the allowed folders: a scoped build would surface `Diary` as
    a ghost node (`exists: false`) named after the hidden note."""
    _write(vault, "Code/A.md", "mentions [[Diary]]")
    _write(vault, "Journal/Diary.md", "private")

    graph = vault_graph.get_vault_graph(CODE_ONLY)

    assert _ids(graph) == {"Code/A.md"}
    assert graph["links"] == []
    assert "Diary" not in str(graph)


def test_a_genuinely_broken_link_from_an_in_scope_note_stays_a_ghost(vault):
    _write(vault, "Code/A.md", "mentions [[NoSuchNoteAnywhere]]")

    graph = vault_graph.get_vault_graph(CODE_ONLY)

    ghost = next(n for n in graph["nodes"] if not n["exists"])
    assert ghost["id"] == "NoSuchNoteAnywhere"
    assert len(graph["links"]) == 1


def test_a_ghost_only_linked_from_out_of_scope_notes_is_dropped(vault):
    _write(vault, "Code/A.md", "plain")
    _write(vault, "Journal/Diary.md", "mentions [[NoSuchNoteAnywhere]]")

    graph = vault_graph.get_vault_graph(CODE_ONLY)

    assert _ids(graph) == {"Code/A.md"}


def test_node_size_counts_only_links_the_persona_can_see(vault):
    _write(vault, "Code/A.md", "links to [[B]]")
    _write(vault, "Code/B.md", "plain")
    _write(vault, "Journal/Diary.md", "links to [[B]] and [[A]]")

    scoped = {n["id"]: n["val"] for n in vault_graph.get_vault_graph(CODE_ONLY)["nodes"]}
    whole = {n["id"]: n["val"] for n in vault_graph.get_vault_graph(WHOLE)["nodes"]}

    assert scoped["Code/B.md"] == 2  # one visible inbound link, +1
    assert whole["Code/B.md"] == 3  # Diary's link counts too


def test_a_folder_prefix_does_not_match_a_sibling_sharing_its_name_start(vault):
    _write(vault, "Code/A.md", "plain")
    _write(vault, "Code-Archive/Old.md", "plain")

    graph = vault_graph.get_vault_graph(CODE_ONLY)

    assert _ids(graph) == {"Code/A.md"}


def test_no_vault_configured_returns_an_empty_graph(tmp_path, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))

    assert vault_graph.get_vault_graph(WHOLE) == {"nodes": [], "links": []}


def test_route_handler_404s_an_unknown_persona(vault, tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))

    with pytest.raises(HTTPException) as exc_info:
        h.get_vault_graph("some-typo-handle")
    assert exc_info.value.status_code == 404


def test_route_handler_scopes_to_the_named_persona(vault, tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    write_persona(profiles, "dev", "name: Dev\nvault_folders:\n  - Code\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    _write(vault, "Code/A.md", "plain")
    _write(vault, "Journal/Diary.md", "private")

    assert _ids(h.get_vault_graph("dev")) == {"Code/A.md"}
    assert _ids(h.get_vault_graph(None)) == {"Code/A.md", "Journal/Diary.md"}


def test_a_same_named_note_in_a_hidden_folder_cannot_capture_an_in_scope_link(vault):
    """Links resolve among the notes the persona can see. Resolved against
    the whole vault instead, `[[Foo]]` from `Work/Sub/A` would pick the
    alphabetically-first same-top-folder candidate (`Work/Other/Foo`), which
    is hidden, and the persona's own `A -> Foo` edge would vanish."""
    _write(vault, "Work/Sub/A.md", "see [[Foo]]")
    _write(vault, "Work/Sub/Foo.md", "visible")
    _write(vault, "Work/Other/Foo.md", "hidden")

    graph = vault_graph.get_vault_graph({"vault_folders": ["Work/Sub"]})

    assert _ids(graph) == {"Work/Sub/A.md", "Work/Sub/Foo.md"}
    assert graph["links"] == [
        {"source": "Work/Sub/A.md", "target": "Work/Sub/Foo.md", "target_stem": "Foo"}
    ]


def test_note_stem_scan_matches_the_snapshots_ignore_rules(vault):
    """`_vault_note_stems` decides which ghosts are "really a hidden note"
    — it must see notes the snapshot sees and skip what the snapshot skips
    (dot-folders, ignored folders, non-note files)."""
    _write(vault, "Journal/Diary.md", "x")
    _write(vault, "Journal/readme.txt", "x")
    _write(vault, "Journal/image.png", "x")
    _write(vault, ".trash/Gone.md", "x")

    stems = vault_graph._vault_note_stems(vault)

    assert {"Diary", "readme"} <= stems
    assert "image" not in stems
    assert "Gone" not in stems
