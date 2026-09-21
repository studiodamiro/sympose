"""Tests for sympose.vault_registry — the configured/active vault list, one
active vault at a time, and adding a new one at runtime (ADR 003, ADR 004)."""

import pytest

from sympose import vault_registry


@pytest.fixture(autouse=True)
def isolated_settings_store(tmp_path, monkeypatch):
    """`get_configured_vaults()` reads `settings_store`'s `added_vaults`
    on every call, not just the active-vault helpers — without this, any
    test here would silently read (and, via `add_vault`, write) this
    checkout's real `./settings.json` instead of a throwaway one."""
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture
def two_vaults(tmp_path, monkeypatch):
    one = tmp_path / "One"
    two = tmp_path / "Two"
    one.mkdir()
    two.mkdir()
    monkeypatch.setenv("VAULT_PATHS", f"{one},{two}")
    return str(one), str(two)


def test_get_configured_vaults_parses_comma_separated_list(two_vaults):
    one, two = two_vaults
    assert vault_registry.get_configured_vaults() == [
        {"name": "One", "path": one},
        {"name": "Two", "path": two},
    ]


def test_get_configured_vaults_dedupes_repeated_path(tmp_path, monkeypatch):
    vault = tmp_path / "Solo"
    vault.mkdir()
    monkeypatch.setenv("VAULT_PATHS", f"{vault},{vault}")
    assert vault_registry.get_configured_vaults() == [
        {"name": "Solo", "path": str(vault)}
    ]


def test_get_configured_vaults_disambiguates_same_basename(tmp_path, monkeypatch):
    work = tmp_path / "Work" / "Notes"
    personal = tmp_path / "Personal" / "Notes"
    work.mkdir(parents=True)
    personal.mkdir(parents=True)
    monkeypatch.setenv("VAULT_PATHS", f"{work},{personal}")
    assert vault_registry.get_configured_vaults() == [
        {"name": "Work/Notes", "path": str(work)},
        {"name": "Personal/Notes", "path": str(personal)},
    ]


def test_active_vault_defaults_to_first_configured(two_vaults):
    one, _ = two_vaults
    assert vault_registry.get_active_vault_path() == one


def test_set_active_vault_persists_and_resolves(two_vaults):
    one, two = two_vaults
    assert vault_registry.set_active_vault(two)
    assert vault_registry.get_active_vault_path() == two


def test_set_active_vault_rejects_unconfigured_path(two_vaults, tmp_path):
    one, _ = two_vaults
    outsider = tmp_path / "NotConfigured"
    outsider.mkdir()
    assert not vault_registry.set_active_vault(str(outsider))
    # active vault is unchanged
    assert vault_registry.get_active_vault_path() == one


def test_active_vault_falls_back_when_saved_choice_no_longer_configured(
    two_vaults, monkeypatch
):
    one, two = two_vaults
    assert vault_registry.set_active_vault(two)
    # simulate VAULT_PATHS shrinking back to just the first vault
    monkeypatch.setenv("VAULT_PATHS", one)
    assert vault_registry.get_active_vault_path() == one


def test_no_configured_vaults_resolves_to_none(monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    assert vault_registry.get_configured_vaults() == []
    assert vault_registry.get_active_vault_path() is None


def test_add_vault_appends_to_configured_list(two_vaults, tmp_path):
    one, two = two_vaults
    added = tmp_path / "Added"
    added.mkdir()
    result = vault_registry.add_vault(str(added))
    assert result == {"name": "Added", "path": str(added)}
    assert vault_registry.get_configured_vaults() == [
        {"name": "One", "path": one},
        {"name": "Two", "path": two},
        {"name": "Added", "path": str(added)},
    ]


def test_add_vault_survives_across_calls_like_a_fresh_process(two_vaults, tmp_path):
    # `settings_store` is the persistence, not an in-memory cache, so a
    # freshly "started" call site (no prior add_vault call in this process)
    # still sees a previously added vault — this is what makes it survive a
    # backend restart in practice.
    added = tmp_path / "Added"
    added.mkdir()
    vault_registry.add_vault(str(added))
    assert any(
        v["path"] == str(added) for v in vault_registry.get_configured_vaults()
    )


def test_add_vault_activates_the_new_vault_when_set_active_is_called(
    two_vaults, tmp_path
):
    added = tmp_path / "Added"
    added.mkdir()
    vault_registry.add_vault(str(added))
    assert vault_registry.set_active_vault(str(added))
    assert vault_registry.get_active_vault_path() == str(added)


def test_add_vault_is_idempotent_for_an_already_configured_path(two_vaults):
    one, _ = two_vaults
    result = vault_registry.add_vault(one)
    assert result == {"name": "One", "path": one}
    # not duplicated
    assert (
        vault_registry.get_configured_vaults().count({"name": "One", "path": one})
        == 1
    )


def test_add_vault_rejects_nonexistent_directory(two_vaults, tmp_path):
    missing = str(tmp_path / "DoesNotExist")
    assert vault_registry.add_vault(missing) is None
    assert not any(
        v["path"] == missing for v in vault_registry.get_configured_vaults()
    )


def test_add_vault_rejects_blank_path(two_vaults):
    assert vault_registry.add_vault("") is None
    assert vault_registry.add_vault("   ") is None


def test_add_vault_expands_user_and_relative_forms(tmp_path, monkeypatch):
    monkeypatch.delenv("VAULT_PATHS", raising=False)
    added = tmp_path / "Added"
    added.mkdir()
    monkeypatch.chdir(tmp_path)
    result = vault_registry.add_vault("Added")
    assert result == {"name": "Added", "path": str(added)}


def test_add_vault_returns_none_when_settings_store_write_fails(
    two_vaults, tmp_path, monkeypatch
):
    """A `settings_store.set` failure (e.g. an unwritable settings
    directory) must surface as `add_vault` returning `None`, not raise
    `StopIteration` from the trailing lookup — the whole point of checking
    its return value."""
    added = tmp_path / "Added"
    added.mkdir()
    monkeypatch.setattr(vault_registry.settings_store, "set", lambda *a, **k: False)
    assert vault_registry.add_vault(str(added)) is None
