"""
Unit tests for sympose.profiles.ProfileManager.bootstrap_missing_artifacts —
the fallback soul-file scaffold used when a persona manifest doesn't provide
`soul_content` (ADR-075.2) — and `set_persona_field`, the `/persona set` write path.
"""

import os
import pytest
import yaml

from sympose.profiles import ProfileManager


class TestBootstrapMissingArtifactsFallbackSoul:
    def test_fallback_soul_is_more_than_one_sentence(self, tmp_path):
        pm = ProfileManager(profiles_dir=str(tmp_path))
        pm.bootstrap_missing_artifacts({"handle": "archimedes", "name": "Archimedes", "title": "Engineer"})

        soul_path = tmp_path / "archimedes_soul.md"
        assert soul_path.exists()
        content = soul_path.read_text()
        assert "Anti-Hallucination" in content
        assert content.count("\n") > 3, "fallback soul should be a real scaffold, not one line"

    def test_does_not_overwrite_an_existing_soul_file(self, tmp_path):
        pm = ProfileManager(profiles_dir=str(tmp_path))
        soul_path = tmp_path / "archimedes_soul.md"
        soul_path.write_text("# Archimedes\n\nCustom hand-written soul.\n")

        pm.bootstrap_missing_artifacts({"handle": "archimedes", "name": "Archimedes", "title": "Engineer"})

        assert "Custom hand-written soul" in soul_path.read_text()

    def test_respects_explicit_soul_file_path(self, tmp_path):
        pm = ProfileManager(profiles_dir=str(tmp_path))
        pm.bootstrap_missing_artifacts({
            "handle": "curie", "name": "Marie Curie", "title": "Researcher",
            "soul_file": "profiles/curie_soul.md",
        })
        assert (tmp_path / "curie_soul.md").exists()


class TestSetPersonaField:
    def _seed(self, tmp_path):
        (tmp_path / "sam.yaml").write_text(
            'name: "Sam"\nhandle: "sam"\nmodel: ""\nskills:\n  - vault_recall\n'
        )
        return ProfileManager(profiles_dir=str(tmp_path))

    def test_writes_and_coerces_a_persona_knob(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("@sam", "temperature", "0.7")
        assert ok
        data = yaml.safe_load((tmp_path / "sam.yaml").read_text())
        assert data["temperature"] == 0.7  # coerced to float, not "0.7"

    def test_rejects_a_global_key_with_a_pointer_to_config(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("sam", "performance.stream", "true")
        assert not ok and "/config set" in msg

    def test_rejects_an_out_of_range_value(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("sam", "temperature", "9")
        assert not ok and "<=" in msg
        assert "temperature" not in yaml.safe_load((tmp_path / "sam.yaml").read_text())

    def test_rejects_a_bad_enum(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("sam", "vault_grounding", "loose")
        assert not ok and "auto" in msg

    def test_unknown_persona_is_reported(self, tmp_path):
        pm = self._seed(tmp_path)
        ok, msg = pm.set_persona_field("nobody", "temperature", "0.5")
        assert not ok and "not found" in msg
