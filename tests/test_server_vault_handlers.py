"""Tests for sympose.server_vault_handlers — the workspace switcher's route
handlers (ADR 003, ADR 004): list/switch/add, and the HTTP-error mapping
`vault_paths`' plain return values (`False`/`None`) turn into."""

import pytest
from fastapi import HTTPException

from sympose import server_vault_handlers as vh


@pytest.fixture(autouse=True)
def isolated_settings_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture
def two_vaults(tmp_path, monkeypatch):
    one = tmp_path / "One"
    two = tmp_path / "Two"
    one.mkdir()
    two.mkdir()
    monkeypatch.setenv("VAULT_PATHS", f"{one},{two}")
    return str(one), str(two)


def test_list_vaults_reports_configured_and_active(two_vaults):
    one, two = two_vaults
    result = vh.list_vaults()
    assert result == {
        "vaults": [
            {"name": "One", "path": one},
            {"name": "Two", "path": two},
        ],
        "active": one,
    }


def test_set_active_vault_switches_and_returns_the_updated_list(two_vaults):
    one, two = two_vaults
    result = vh.set_active_vault(two)
    assert result["active"] == two
    assert result["vaults"] == [
        {"name": "One", "path": one},
        {"name": "Two", "path": two},
    ]


def test_set_active_vault_raises_404_for_an_unconfigured_path(two_vaults, tmp_path):
    outsider = tmp_path / "NotConfigured"
    outsider.mkdir()
    with pytest.raises(HTTPException) as exc_info:
        vh.set_active_vault(str(outsider))
    assert exc_info.value.status_code == 404


def test_add_vault_adds_and_activates(two_vaults, tmp_path):
    one, _two = two_vaults
    added = tmp_path / "Added"
    added.mkdir()
    result = vh.add_vault(str(added))
    assert result["active"] == str(added)
    assert {"name": "Added", "path": str(added)} in result["vaults"]
    # the originally active vault is unaffected, just no longer active
    assert any(v["path"] == one for v in result["vaults"])


def test_add_vault_raises_400_for_a_nonexistent_directory(two_vaults, tmp_path):
    missing = tmp_path / "DoesNotExist"
    with pytest.raises(HTTPException) as exc_info:
        vh.add_vault(str(missing))
    assert exc_info.value.status_code == 400
