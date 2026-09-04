"""
Unit tests for sympose.profiles.ProfileManager.bootstrap_missing_artifacts —
the fallback soul-file scaffold used when a persona manifest doesn't provide
`soul_content` (ADR-075.2).
"""

import os
import pytest

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
