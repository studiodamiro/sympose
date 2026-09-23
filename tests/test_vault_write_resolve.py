"""Regression test for a `/code-review` finding: `_resolve_note_recursively`
used to return whichever same-stem note the filesystem happened to
enumerate first, with no tie-break — filesystem-order-dependent, not
deterministic. Fixed to resolve to the alphabetically-first path instead."""

import os

import pytest

from sympose import vault_write_resolve


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_PATHS", str(tmp_path))
    return str(tmp_path)


@pytest.fixture
def profile():
    return {"vault_folders": ["*"]}


def test_resolve_bare_name_at_allowed_dir_top_level(vault, profile):
    with open(os.path.join(vault, "Solo.md"), "w") as f:
        f.write("x")
    resolved = vault_write_resolve.resolve_existing_note(profile, "Solo")
    assert resolved == os.path.join(vault, "Solo.md")


def test_resolve_ambiguous_stem_is_deterministic(vault, profile):
    """Two notes sharing a stem in different folders, neither at an
    allowed dir's own top level (so resolution falls through to the
    recursive case) -- must always resolve to the same, alphabetically-
    first path regardless of filesystem enumeration order."""
    zeta_path = os.path.join(vault, "Zeta", "Nested")
    os.makedirs(zeta_path)
    with open(os.path.join(zeta_path, "Ideas.md"), "w") as f:
        f.write("zeta")
    alpha_path = os.path.join(vault, "Alpha", "Nested")
    os.makedirs(alpha_path)
    with open(os.path.join(alpha_path, "Ideas.md"), "w") as f:
        f.write("alpha")

    resolved = vault_write_resolve.resolve_existing_note(profile, "Ideas")
    assert resolved == os.path.join(alpha_path, "Ideas.md")

    # Deterministic across repeated calls, not just lucky once.
    for _ in range(5):
        assert vault_write_resolve.resolve_existing_note(profile, "Ideas") == os.path.join(
            alpha_path, "Ideas.md"
        )
