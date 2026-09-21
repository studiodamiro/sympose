"""Tests for sympose.settings_store — the app-wide settings JSON file
(ADR 003)."""

import os

import pytest

from sympose import settings_store


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = str(tmp_path / "settings.json")
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", path)
    return path


def test_get_missing_file_returns_default(settings_file):
    assert settings_store.get("active_vault") is None
    assert settings_store.get("active_vault", "fallback") == "fallback"


def test_set_then_get_round_trips(settings_file):
    assert settings_store.set("active_vault", "/some/vault")
    assert settings_store.get("active_vault") == "/some/vault"


def test_set_preserves_other_keys(settings_file):
    settings_store.set("active_vault", "/vault/one")
    settings_store.set("compaction_default", "auto")
    assert settings_store.get("active_vault") == "/vault/one"
    assert settings_store.get("compaction_default") == "auto"


def test_corrupt_file_falls_back_to_default(settings_file):
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write("{not valid json")
    assert settings_store.get("active_vault", "fallback") == "fallback"


def test_creates_parent_directory(tmp_path, monkeypatch):
    nested = str(tmp_path / "nested" / "settings.json")
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", nested)
    assert settings_store.set("active_vault", "/vault")
    assert os.path.exists(nested)
