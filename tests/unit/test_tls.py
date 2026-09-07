"""
Unit tests for sympose.tls.ensure_dashboard_tls_choice — the first-boot HTTPS
vs. plain-HTTP prompt (ADR-064.2), mirroring ensure_dashboard_password's
generate-once-and-persist pattern.
"""

import os
import pytest

from sympose.tls import ensure_dashboard_tls_choice


class TestEnsureDashboardTlsChoice:
    def test_env_var_already_set_wins_no_prompt(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SYMPOSE_DASHBOARD_TLS", "0")
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        assert ensure_dashboard_tls_choice(str(tmp_path)) is False

    def test_env_var_truthy_variants(self, tmp_path, monkeypatch):
        for value, expected in [("1", True), ("true", True), ("0", False), ("false", False), ("no", False)]:
            monkeypatch.setenv("SYMPOSE_DASHBOARD_TLS", value)
            assert ensure_dashboard_tls_choice(str(tmp_path)) is expected

    def test_non_interactive_defaults_to_https_without_prompting(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SYMPOSE_DASHBOARD_TLS", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        assert ensure_dashboard_tls_choice(str(tmp_path)) is True
        # Nothing should have been persisted — no one was asked.
        assert not (tmp_path / ".env").exists()

    def test_interactive_choice_persists_to_env_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SYMPOSE_DASHBOARD_TLS", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **k: False)

        result = ensure_dashboard_tls_choice(str(tmp_path))

        assert result is False
        assert os.environ["SYMPOSE_DASHBOARD_TLS"] == "0"
        env_file = tmp_path / ".env"
        assert env_file.exists()
        assert "SYMPOSE_DASHBOARD_TLS=0" in env_file.read_text()

    def test_interactive_choice_true_persists_as_1(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SYMPOSE_DASHBOARD_TLS", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **k: True)

        result = ensure_dashboard_tls_choice(str(tmp_path))

        assert result is True
        assert os.environ["SYMPOSE_DASHBOARD_TLS"] == "1"
        assert "SYMPOSE_DASHBOARD_TLS=1" in (tmp_path / ".env").read_text()
