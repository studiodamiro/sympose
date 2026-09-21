"""Tests for sympose.vault_paths sandbox-containment logic — the persona
vault sandbox, and CODE_QUALITY_STANDARDS.md's directory/path-boundary-
safety rule."""

import os

import pytest

from sympose import vault_paths


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_VAULT_PATH", str(tmp_path))
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
