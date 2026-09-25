"""Tests for sympose.vault_paths sandbox-containment logic — the persona
vault sandbox, and CODE_QUALITY_STANDARDS.md's directory/path-boundary-
safety rule. The configured/active vault list itself (ADR 003, ADR 004) is
`vault_registry`, tested in test_vault_registry.py."""

import os

import pytest

from sympose import vault_paths


@pytest.fixture(autouse=True)
def isolated_settings_store(tmp_path, monkeypatch):
    """`get_master_vault()` resolves through `vault_registry`, which reads
    `settings_store` on every call — without this, a test here would
    silently read this checkout's real `./settings.json`."""
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return str(tmp_path)


def test_wildcard_vault_folders_grants_full_root(vault_root):
    profile = {"vault_folders": ["*"]}
    assert vault_paths.get_allowed_dirs(profile) == [vault_root]


def test_scoped_vault_folders_grants_only_named_subfolder(vault_root):
    profile = {"vault_folders": ["Code"]}
    assert vault_paths.get_allowed_dirs(profile) == [
        os.path.join(vault_root, "Code")
    ]


def test_escaping_vault_folder_is_rejected(vault_root):
    profile = {"vault_folders": ["../../etc"]}
    allowed = vault_paths.get_allowed_dirs(profile)
    # the unsafe entry is dropped; falling back to the vault root itself
    # means it never resolves outside the sandbox.
    assert allowed == [vault_root]


def test_get_master_vault_reflects_the_active_vault(vault_root):
    assert vault_paths.get_master_vault() == vault_root


def test_get_vault_name_uses_the_disambiguated_registry_name(tmp_path, monkeypatch):
    work = tmp_path / "Work" / "Notes"
    personal = tmp_path / "Personal" / "Notes"
    work.mkdir(parents=True)
    personal.mkdir(parents=True)
    monkeypatch.setenv("VAULT_PATHS", f"{work},{personal}")
    assert vault_paths.get_vault_name() == "Work/Notes"


def test_no_configured_vaults_resolves_to_none(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    assert vault_paths.get_master_vault() is None
    assert vault_paths.get_vault_name() is None


@pytest.mark.xfail(
    strict=True,
    reason="looking up a persona's folders creates them, so a misspelt `vault_folders` entry adds an empty "
    "folder to the user's vault on a read-only request",
)
def test_looking_up_a_personas_folders_creates_nothing(vault_root):
    vault_paths.get_allowed_dirs({"vault_folders": ["Misspelt"]})
    assert os.listdir(vault_root) == []
