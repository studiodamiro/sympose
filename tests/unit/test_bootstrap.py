"""
Unit tests for sympose.bootstrap — the fresh-workspace starter templates and
first-run onboarding.

Covers a real regression: SAMANTHA_YAML (the persona template every fresh
`pipx install` actually writes to disk) used to hardcode
vault_folders: ["General", "Projects", "Thoughts", "Templates"] — folders
that get auto-created inside whatever vault a new user links, and outside of
which Samantha has zero visibility. That contradicts the "adapts to any
folder taxonomy" claim for the one persona guaranteed to ship. Fixed to
vault_folders: ["*"] (full vault access, nothing auto-created).
"""

import os
import yaml
import pytest

from sympose.bootstrap import SAMANTHA_YAML, ensure_workspace
from sympose.vault import VaultManager


class TestSamanthaTemplate:
    def test_parses_as_valid_yaml(self):
        data = yaml.safe_load(SAMANTHA_YAML)
        assert data["handle"] == "samantha"

    def test_vault_folders_is_full_access_wildcard(self):
        """The regression: a fixed folder list isn't taxonomy-agnostic and
        auto-creates folders inside a new user's real vault."""
        data = yaml.safe_load(SAMANTHA_YAML)
        assert data["vault_folders"] == ["*"]

    def test_full_access_creates_no_folders_in_a_pre_existing_vault(self, tmp_path, monkeypatch):
        """get_allowed_dirs on a wildcard profile must not os.makedirs anything
        — a fixed-folder-list profile would create each listed folder."""
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "MyOwnStructure").mkdir()
        monkeypatch.setenv("MASTER_VAULT_PATH", str(vault))

        data = yaml.safe_load(SAMANTHA_YAML)
        dirs = VaultManager.get_allowed_dirs(data)

        assert dirs == [str(vault)]
        assert os.listdir(vault) == ["MyOwnStructure"], "wildcard access must not create any new folders"


class TestEnsureWorkspace:
    def test_fresh_workspace_writes_samantha_with_full_vault_access(self, tmp_path):
        ws = str(tmp_path / "ws")
        is_fresh = ensure_workspace(ws)
        assert is_fresh is True

        with open(os.path.join(ws, "profiles", "samantha.yaml"), encoding="utf-8") as f:
            data = yaml.safe_load(f.read())
        assert data["vault_folders"] == ["*"]

    def test_existing_workspace_is_not_overwritten(self, tmp_path):
        ws = str(tmp_path / "ws")
        ensure_workspace(ws)
        sam_file = os.path.join(ws, "profiles", "samantha.yaml")
        with open(sam_file, "a", encoding="utf-8") as f:
            f.write("\n# user customization marker\n")

        is_fresh_second_call = ensure_workspace(ws)
        assert is_fresh_second_call is False
        with open(sam_file, encoding="utf-8") as f:
            assert "user customization marker" in f.read()


def test_default_rules_md_matches_workspace_rules_file():
    """DEFAULT_RULES_MD is the wheel-install fallback for prompts/workspace_rules.md
    (prompts/ isn't shipped in the wheel). They drifted once, leaving fresh installs
    on an older, shorter ruleset. Keep them byte-for-byte identical."""
    import os
    from sympose.bootstrap import DEFAULT_RULES_MD

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    with open(os.path.join(repo_root, "prompts", "workspace_rules.md"), encoding="utf-8") as f:
        assert DEFAULT_RULES_MD == f.read()


def test_resolve_workspace_dir_single_impl():
    """bootstrap re-exports the workspace resolver; there must not be a second copy."""
    import sympose.bootstrap as b
    import sympose.workspace as w

    assert b.resolve_workspace_dir is w.resolve_workspace_dir


def test_config_loads_workspace_env_not_parent_walked(tmp_path):
    """sympose.config must load the *workspace* .env at import — not a bare
    load_dotenv() that walks up and finds a repo/parent .env first (which then
    shadows the workspace .env, since python-dotenv never overrides)."""
    import subprocess
    import sys

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "config.yaml").write_text("performance:\n  request_timeout: 10.0\n")
    (ws / ".env").write_text("DEFAULT_MODEL=sentinel/workspace-model\n")
    # a conflicting .env in the parent — a bare load_dotenv() walking up would hit this
    (tmp_path / ".env").write_text("DEFAULT_MODEL=wrong/parent-model\n")

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    child_env = {k: v for k, v in os.environ.items() if k != "DEFAULT_MODEL"}
    child_env["PYTHONPATH"] = repo_root
    out = subprocess.run(
        [sys.executable, "-c", "import sympose.config as c; print(c.DEFAULT_CHAT_MODEL)"],
        cwd=str(ws),
        env=child_env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "sentinel/workspace-model", out.stdout
