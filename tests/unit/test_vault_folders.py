"""
Unit tests for sympose.vault_folders - the folder-level digest/sampling
mixin, plus ADR-123.1's folder-kind signal: a structural, zero-config
one-line hint about what kind of folder this is, derived from which real
frontmatter keys (and, where one value dominates, which value) show up
across most of a folder's notes.
"""

import os

from sympose.vault import VaultManager
from sympose.vault_folders import (
    _folder_kind_signal,
    _normalize_field_tokens,
)


def _entry(meta: dict) -> dict:
    """A minimal `_get_vault_snapshot`-shaped entry - only `meta` matters
    to `_folder_kind_signal`, which never looks at the rest."""
    return {"meta": meta}


def _write_note(path, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# _normalize_field_tokens
# ---------------------------------------------------------------------------


class TestNormalizeFieldTokens:
    def test_yaml_list_value(self):
        assert _normalize_field_tokens(["Code", "Python"]) == ["code", "python"]

    def test_comma_separated_string(self):
        assert _normalize_field_tokens("Code, Python") == ["code", "python"]

    def test_plain_scalar(self):
        assert _normalize_field_tokens("Damiro") == ["damiro"]

    def test_none_and_empty_are_no_tokens(self):
        assert _normalize_field_tokens(None) == []
        assert _normalize_field_tokens("") == []
        assert _normalize_field_tokens([]) == []

    def test_non_string_scalar_is_stringified(self):
        assert _normalize_field_tokens(2024) == ["2024"]


# ---------------------------------------------------------------------------
# _folder_kind_signal
# ---------------------------------------------------------------------------


class TestFolderKindSignal:
    def test_too_few_notes_gives_no_signal(self):
        entries = [_entry({"tags": ["code"]}), _entry({"tags": ["code"]})]
        assert _folder_kind_signal(entries) == ""

    def test_dominant_tag_value_across_folder_is_the_signal(self):
        """The Code/ half of the Code-vs-Limbo scenario: most notes share
        one dominant tag value, so the line should name that value
        directly, not just the bare `tags` field."""
        entries = [
            _entry({"tags": ["code", "python"]}),
            _entry({"tags": ["code", "python"]}),
            _entry({"tags": ["code"]}),
            _entry({"tags": ["misc"]}),
        ]
        signal = _folder_kind_signal(entries)
        assert "tags: code" in signal

    def test_heterogeneous_catch_all_gives_no_signal(self):
        """The Limbo/ half: every note's tag is unique, nothing dominates,
        and no other field repeats either - a genuine catch-all folder
        should get silence, not a guessed signal."""
        entries = [
            _entry({"tags": ["journal"]}),
            _entry({"tags": ["recipe"]}),
            _entry({"tags": ["quote"]}),
            _entry({"tags": ["idea"]}),
        ]
        assert _folder_kind_signal(entries) == ""

    def test_presence_only_field_with_varying_values_still_signals(self):
        """`created` legitimately differs on every note - the field's mere
        presence is still meaningful even though no single value
        dominates, so it should surface as a bare field name."""
        entries = [
            _entry({"created": "2024-01-01"}),
            _entry({"created": "2024-02-14"}),
            _entry({"created": "2024-03-30"}),
        ]
        signal = _folder_kind_signal(entries)
        assert "created" in signal
        assert "created:" not in signal  # no dominant value to name

    def test_field_below_presence_threshold_is_excluded(self):
        entries = [
            _entry({"birthday": "1990-01-01"}),
            _entry({}),
            _entry({}),
            _entry({}),
        ]
        assert _folder_kind_signal(entries) == ""

    def test_uses_any_real_frontmatter_key_not_a_fixed_list(self):
        """No hardcoded vocabulary - a vault-specific key like `status`
        works exactly like a well-known one."""
        entries = [
            _entry({"status": "active"}),
            _entry({"status": "active"}),
            _entry({"status": "active"}),
        ]
        signal = _folder_kind_signal(entries)
        assert "status: active" in signal

    def test_caps_at_three_fields_and_orders_by_strength(self):
        entries = [
            _entry({"a": "x", "b": "x", "c": "x", "d": "x"}),
            _entry({"a": "x", "b": "x", "c": "x", "d": "x"}),
            _entry({"a": "x", "b": "x", "c": "x"}),
            _entry({"a": "x", "b": "x"}),
        ]
        signal = _folder_kind_signal(entries)
        body = signal.removeprefix("This folder's notes mostly carry: ").rstrip(".")
        named_fields = [part.split(":")[0] for part in body.split(", ")]
        assert named_fields == ["a", "b", "c"]  # strongest presence first

    def test_entries_without_meta_are_skipped_not_fatal(self):
        entries = [
            {"meta": None},
            _entry({"tags": ["code"]}),
            _entry({"tags": ["code"]}),
            _entry({"tags": ["code"]}),
        ]
        assert "tags: code" in _folder_kind_signal(entries)


# ---------------------------------------------------------------------------
# Integration: get_folder_digest / get_random_sample_notes prepend the signal
# ---------------------------------------------------------------------------


class TestGetFolderDigestKindSignal:
    def _wire_vault(self, monkeypatch, vault_dir):
        monkeypatch.setattr(VaultManager, "_get_master_vault", staticmethod(lambda: str(vault_dir)))
        monkeypatch.setattr(
            VaultManager, "get_allowed_dirs", classmethod(lambda cls, profile: [str(vault_dir)])
        )

    def test_digest_is_prefixed_with_kind_signal_when_one_is_found(self, tmp_vault_dir, monkeypatch):
        folder = tmp_vault_dir / "Code"
        for i in range(3):
            _write_note(
                folder / f"note{i}.md",
                f"---\ntags: [code, python]\n---\n\nSnippet {i}\n",
            )
        self._wire_vault(monkeypatch, tmp_vault_dir)

        digest = VaultManager.get_folder_digest({}, "Code")
        assert digest.startswith("This folder's notes mostly carry: tags: code")
        assert "High-Density Folder Digest" in digest

    def test_digest_has_no_signal_line_for_a_catch_all_folder(self, tmp_vault_dir, monkeypatch):
        folder = tmp_vault_dir / "Limbo"
        tags = ["journal", "recipe", "quote", "idea"]
        for i, tag in enumerate(tags):
            _write_note(folder / f"note{i}.md", f"---\ntags: [{tag}]\n---\n\nStuff {i}\n")
        self._wire_vault(monkeypatch, tmp_vault_dir)

        digest = VaultManager.get_folder_digest({}, "Limbo")
        assert digest.startswith("### High-Density Folder Digest")
        assert "mostly carry" not in digest

    def test_random_sample_is_prefixed_with_kind_signal_when_one_is_found(
        self, tmp_vault_dir, monkeypatch
    ):
        folder = tmp_vault_dir / "Code"
        for i in range(3):
            _write_note(
                folder / f"note{i}.md",
                f"---\ntags: [code, python]\n---\n\nSnippet body {i}\n",
            )
        self._wire_vault(monkeypatch, tmp_vault_dir)

        sample = VaultManager.get_random_sample_notes({}, "Code", count=1)
        assert sample.startswith("This folder's notes mostly carry: tags: code")
        assert "Ground-Truth Sandboxed Vault Note" in sample
