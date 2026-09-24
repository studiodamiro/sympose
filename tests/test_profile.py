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


def test_aliases_default_to_none_and_are_kept_when_a_list(profiles_dir):
    _write(profiles_dir, "dev", "name: Dev\n")
    assert profile.get_profile("dev")["aliases"] == []
    _write(profiles_dir, "samantha", "name: Samantha\naliases:\n  - Sam\n  - ' Sammy '\n")
    assert profile.get_profile("samantha")["aliases"] == ["Sam", "Sammy"]


def test_a_single_alias_written_as_a_string_is_one_alias(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\naliases: Sam\n")
    assert profile.get_profile("samantha")["aliases"] == ["Sam"]


@pytest.mark.parametrize("value", ["{a: 1}", "42", "[1, null, '', '  ', {x: y}]", "~"])
def test_malformed_aliases_are_ignored_not_fatal(profiles_dir, value):
    _write(profiles_dir, "dev", f"name: Dev\naliases: {value}\n")
    assert profile.get_profile("dev")["aliases"] == []


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


# -- load_soul (docs/decisions/012) --


def test_load_soul_returns_the_stripped_text(profiles_dir):
    directory = _persona_with(profiles_dir, "samantha")
    (directory / "soul.md").write_text("\n  You are warm.  \n\n")

    assert profile.load_soul("samantha") == "You are warm."


def test_load_soul_is_none_when_missing_or_empty(profiles_dir):
    directory = _persona_with(profiles_dir, "samantha")
    assert profile.load_soul("samantha") is None

    (directory / "soul.md").write_text("   \n")
    assert profile.load_soul("samantha") is None


def test_load_soul_is_none_with_no_profiles_dir(no_profiles_dir):
    assert profile.load_soul("samantha") is None


def test_load_soul_rejects_a_traversal_handle(profiles_dir):
    outside = profiles_dir.parent / "outside"
    outside.mkdir()
    (outside / "soul.md").write_text("should never be read")

    assert profile.load_soul("../outside") is None


def test_load_soul_degrades_to_none_and_logs_when_unreadable(profiles_dir, caplog):
    directory = _persona_with(profiles_dir, "samantha")
    (directory / "soul.md").write_bytes(b"\xff\xfe not valid utf-8 \x80")

    with caplog.at_level("WARNING"):
        assert profile.load_soul("samantha") is None
    assert "default soul" in caplog.text


def _persona_with(profiles_dir, handle):
    return write_persona(profiles_dir, handle, f"name: {handle.title()}\n")


# -- a handle must be one plain path component --


@pytest.mark.parametrize("handle", [".", "..", "a/b", "../outside", ""])
def test_a_handle_that_is_not_a_single_path_component_resolves_to_nothing(profiles_dir, handle):
    """`is_safe_path` only proves a path stays inside profiles/, which `.`
    (profiles/ itself) and `a/b` (a nested path) do. A stray
    profiles/persona.yaml or profiles/soul.md must never load as a persona."""
    (profiles_dir / "persona.yaml").write_text("name: Stray\nvault_folders: '*'\n")
    (profiles_dir / "soul.md").write_text("stray soul")
    _write(profiles_dir, "a", "name: A\n")
    (profiles_dir / "a" / "b").mkdir()
    (profiles_dir / "a" / "b" / "persona.yaml").write_text("name: Nested\n")

    assert profile.get_profile(handle) is None
    assert profile.load_soul(handle) is None


# -- the Sympose reference library flag (docs/decisions/022) --


@pytest.mark.parametrize("value,expected", [("true", True), ("false", False), ("'true'", False), ("1", False), ("~", False)])
def test_only_an_explicit_true_gives_a_persona_the_reference_library(profiles_dir, value, expected):
    _write(profiles_dir, "dev", f"name: Dev\nsympose_reference: {value}\n")
    assert profile.get_profile("dev")["sympose_reference"] is expected


def test_the_default_persona_keeps_the_library_when_its_file_predates_the_key(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\n")  # written before `sympose_reference` existed
    _write(profiles_dir, "ada", "name: Ada\n")

    assert profile.get_profile("samantha")["sympose_reference"] is True
    assert profile.get_profile("ada")["sympose_reference"] is False


def test_the_default_persona_can_turn_the_library_off_explicitly(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nsympose_reference: false\n")
    assert profile.get_profile("samantha")["sympose_reference"] is False


def test_a_persona_name_that_is_not_text_does_not_break_the_roster(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nsympose_reference: true\n")
    _write(profiles_dir, "odd", "name: 2024\nsympose_reference: true\n")

    assert profile.reference_persona_names() == ["2024", "Samantha"]


def test_no_flag_means_no_library_and_the_synthetic_default_persona_has_it(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path / "no-profiles-here"))
    assert profile.get_profile("samantha")["sympose_reference"] is True
    assert profile.get_profile("someone-else")["sympose_reference"] is False


def test_the_names_of_the_personas_that_have_the_library(profiles_dir):
    _write(profiles_dir, "samantha", "name: Samantha\nsympose_reference: true\n")
    _write(profiles_dir, "dev", "name: Dev\n")
    _write(profiles_dir, "ada", "name: Ada\nsympose_reference: true\n")

    assert profile.reference_persona_names() == ["Ada", "Samantha"]
