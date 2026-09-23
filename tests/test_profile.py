"""Tests for sympose.profile — persona-profile loading, the fail-closed
"unknown persona" contract, and the settings-store-backed default persona
(docs/decisions/009)."""

import pytest
from helpers import write_persona

from sympose import profile


@pytest.fixture(autouse=True)
def isolated_settings_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture
def no_profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "does-not-exist"))


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    base.mkdir()
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    return base


def _write(base, handle: str, body: str) -> None:
    write_persona(base, handle, body)


# -- get_profile --


def test_no_profiles_dir_returns_whole_vault_fallback(no_profiles_dir):
    p = profile.get_profile("samantha")
    assert p["vault_folders"] == ["*"]
    assert p["handle"] == "samantha"


def test_unknown_handle_with_profiles_dir_returns_none_not_fallback(profiles_dir):
    """The core regression test: once a profiles/ dir exists, a handle
    with no matching file must fail closed, not silently get full vault
    access the way the pre-fix `except (OSError, ...)` catch-all did."""
    _write(profiles_dir, "samantha", "name: Samantha\nvault_folders: '*'\n")
    assert profile.get_profile("some-typo-handle") is None


def test_malformed_yaml_returns_none(profiles_dir):
    _write(profiles_dir, "broken", "name: [unterminated\n")
    assert profile.get_profile("broken") is None


def test_unsafe_traversal_handle_returns_none(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\n")
    assert profile.get_profile("../../etc/passwd") is None


def test_model_and_skills_default_when_absent(profiles_dir):
    _write(profiles_dir, "dev", "name: Dev\nvault_folders:\n  - Code\n")
    p = profile.get_profile("dev")
    assert p["model"] is None
    assert p["skills"] == []


def test_model_and_skills_preserved_when_present(profiles_dir):
    _write(
        profiles_dir,
        "dev",
        "name: Dev\nvault_folders:\n  - Code\nmodel: ollama_chat/foo\nskills:\n  - triage\n",
    )
    p = profile.get_profile("dev")
    assert p["model"] == "ollama_chat/foo"
    assert p["skills"] == ["triage"]


# -- resolve_default_persona --


def test_resolve_default_persona_falls_back_to_factory_default():
    assert profile.resolve_default_persona() == "samantha"


def test_resolve_default_persona_reads_the_configured_setting(monkeypatch):
    from sympose import settings_store

    settings_store.set("default_persona", "dev")
    assert profile.resolve_default_persona() == "dev"


# -- resolve_profile --


def test_resolve_profile_none_uses_factory_default_with_no_profiles_dir(no_profiles_dir):
    p = profile.resolve_profile(None)
    assert p["handle"] == "samantha"
    assert p["vault_folders"] == ["*"]


def test_resolve_profile_none_honors_a_configured_custom_default(profiles_dir):
    from sympose import settings_store

    _write(profiles_dir, "dev", "name: Dev\nvault_folders:\n  - Code\n")
    settings_store.set("default_persona", "dev")
    p = profile.resolve_profile(None)
    assert p["handle"] == "dev"


def test_resolve_profile_none_still_resolves_if_samantha_file_is_missing(profiles_dir):
    """Pathological case: profiles/ exists but samantha.yaml itself is
    gone. The factory-default safety net still guarantees a result."""
    _write(profiles_dir, "dev", "name: Dev\nvault_folders:\n  - Code\n")
    p = profile.resolve_profile(None)
    assert p["handle"] == "samantha"
    assert p["vault_folders"] == ["*"]


def test_resolve_profile_safety_net_matches_a_mixed_case_configured_default(profiles_dir):
    """Regression test (`/code-review` finding): the safety net compared
    the raw handle to FACTORY_DEFAULT_PERSONA (a lowercase literal)
    without lowering it first -- a settings_store value of "Samantha"
    (nothing normalizes case on write) would never match "samantha" and
    the fallback would wrongly be skipped, returning None instead of
    whole-vault access, even though samantha.yaml has simply gone
    missing exactly like the all-lowercase case above."""
    from sympose import settings_store

    settings_store.set("default_persona", "Samantha")
    p = profile.resolve_profile(None)
    assert p is not None
    assert p["handle"] == "samantha"
    assert p["vault_folders"] == ["*"]


def test_resolve_profile_none_fails_closed_for_a_broken_configured_default(profiles_dir):
    """A *configured* custom default whose file has gone missing must not
    cascade back to the whole-vault fallback under that orphaned handle —
    that would reopen the exact bug this module fixes, just reached via
    the settings key instead of a typo."""
    from sympose import settings_store

    _write(profiles_dir, "samantha", "name: Samantha\nvault_folders: '*'\n")
    settings_store.set("default_persona", "dev")  # dev.yaml never created
    assert profile.resolve_profile(None) is None


def test_resolve_profile_explicit_bogus_handle_propagates_none(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nvault_folders: '*'\n")
    assert profile.resolve_profile("bogus") is None


# -- list_profiles --


def test_list_profiles_no_dir_returns_synthetic_samantha(no_profiles_dir):
    profiles = profile.list_profiles()
    assert [p["handle"] for p in profiles] == ["samantha"]


def test_list_profiles_skips_broken_files_keeps_good_ones(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nvault_folders: '*'\n")
    _write(profiles_dir, "broken", "name: [unterminated\n")
    profiles = profile.list_profiles()
    assert [p["handle"] for p in profiles] == ["samantha"]


def test_list_profiles_empty_dir_returns_empty_list(profiles_dir):
    assert profile.list_profiles() == []


# -- set_default_persona (docs/decisions/010) --


def test_set_default_persona_persists_and_is_read_back(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nvault_folders: '*'\n")
    _write(profiles_dir, "dev", "name: Dev\nvault_folders:\n  - Code\n")

    assert profile.set_default_persona("dev") is True
    assert profile.resolve_default_persona() == "dev"
    assert profile.resolve_profile(None)["handle"] == "dev"


def test_set_default_persona_lowercases_the_handle(profiles_dir):
    _write(profiles_dir, "dev", "name: Dev\nvault_folders:\n  - Code\n")

    assert profile.set_default_persona("DEV") is True
    assert profile.resolve_default_persona() == "dev"


def test_set_default_persona_refuses_an_unknown_handle_and_writes_nothing(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nvault_folders: '*'\n")

    assert profile.set_default_persona("some-typo-handle") is False
    assert profile.resolve_default_persona() == profile.FACTORY_DEFAULT_PERSONA


def test_set_default_persona_refuses_a_traversal_handle(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nvault_folders: '*'\n")

    assert profile.set_default_persona("../samantha") is False


# -- one directory per persona (docs/decisions/011) --


def test_a_flat_yaml_file_is_not_a_persona(profiles_dir):
    (profiles_dir / "samantha.yaml").write_text("name: Samantha\nvault_folders: '*'\n")
    _write(profiles_dir, "dev", "name: Dev\nvault_folders:\n  - Code\n")

    assert profile.get_profile("samantha") is None
    assert [p["handle"] for p in profile.list_profiles()] == ["dev"]


def test_a_directory_without_persona_yaml_is_not_a_persona(profiles_dir):
    (profiles_dir / "half-made").mkdir()
    (profiles_dir / "half-made" / "soul.md").write_text("voice")

    assert profile.get_profile("half-made") is None
    assert profile.list_profiles() == []


def test_stray_files_in_the_profiles_dir_are_ignored_by_the_roster(profiles_dir):
    _write(profiles_dir, "dev", "name: Dev\nvault_folders:\n  - Code\n")
    (profiles_dir / "_shared_memory.md").write_text("cross-persona note")
    (profiles_dir / "notes.txt").write_text("x")

    assert [p["handle"] for p in profile.list_profiles()] == ["dev"]


def test_a_traversal_handle_cannot_load_a_persona_outside_profiles(profiles_dir):
    outside = profiles_dir.parent / "outside"
    outside.mkdir()
    (outside / "persona.yaml").write_text("name: Outside\nvault_folders: '*'\n")

    assert profile.get_profile("../outside") is None
