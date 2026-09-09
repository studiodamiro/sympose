"""
Unit tests for sympose.server.create_app — frontend resolution.
"""

import os
from unittest.mock import MagicMock

from sympose.server import create_app


def _app():
    engine = MagicMock()
    engine.pm.profiles = {}
    return create_app(engine)


def test_spa_is_mounted_regardless_of_cwd(tmp_path, monkeypatch):
    """The dashboard must serve its frontend even when launched from a
    directory that has no `ui/` — resolution is package-relative, not CWD."""
    monkeypatch.chdir(tmp_path)
    app = _app()
    assert any(getattr(r, "name", "") == "ui" for r in app.routes), (
        "SPA static mount missing — client routes like /menu would 404"
    )


def test_graph_endpoint_registered():
    app = _app()
    assert any(getattr(r, "path", "") == "/api/vault/graph" for r in app.routes)


def test_vault_tree_endpoint_registered():
    app = _app()
    assert any(getattr(r, "path", "") == "/api/vault/tree" for r in app.routes)


def test_vault_note_write_endpoint_registered():
    app = _app()
    put_routes = [
        r for r in app.routes
        if getattr(r, "path", "") == "/api/vault/note" and "PUT" in getattr(r, "methods", set())
    ]
    assert put_routes, "PUT /api/vault/note missing — the dashboard editor cannot save"


class TestVaultNoteWrite:
    """`PUT /api/vault/note` maps `VaultManager.overwrite_note`'s sentinels onto
    HTTP status codes (ADR-081)."""

    def _client(self, monkeypatch, overwrite_result):
        from fastapi.testclient import TestClient
        from sympose.auth import DASHBOARD_USER
        import sympose.server as server

        monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
        monkeypatch.setattr(
            server.VaultManager, "overwrite_note",
            classmethod(lambda cls, profile, path, content: overwrite_result),
        )
        engine = MagicMock()
        engine.pm.get_profile.return_value = {"vault_folders": ["*"]}
        engine.pm.profiles = {}
        return TestClient(server.create_app(engine)), DASHBOARD_USER

    def test_success_returns_200(self, monkeypatch):
        client, user = self._client(monkeypatch, "Saved note: `x.md`")
        resp = client.put(
            "/api/vault/note",
            json={"path": "x", "content": "body", "persona": "samantha"},
            auth=(user, "pw"),
        )
        assert resp.status_code == 200
        assert resp.json()["detail"].startswith("Saved note:")

    def test_missing_note_returns_404(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_NOT_FOUND)
        resp = client.put(
            "/api/vault/note", json={"path": "ghost", "content": ""}, auth=(user, "pw")
        )
        assert resp.status_code == 404

    def test_denied_note_returns_403(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_DENIED)
        resp = client.put(
            "/api/vault/note", json={"path": "../evil", "content": ""}, auth=(user, "pw")
        )
        assert resp.status_code == 403

    def test_blank_path_rejected(self, monkeypatch):
        client, user = self._client(monkeypatch, "Saved note: `x.md`")
        resp = client.put(
            "/api/vault/note", json={"path": "", "content": "body"}, auth=(user, "pw")
        )
        assert resp.status_code == 422


def _route(app, path):
    return next(r for r in app.routes if getattr(r, "path", "") == path)


def test_personas_endpoint_is_a_trimmed_projection():
    """The agent-picker roster must not leak profile file paths or internals —
    only identity + model + skills, plus which handle is the default."""
    engine = MagicMock()
    engine.config.get.return_value = "samantha"
    engine.pm.profiles = {
        "samantha": {
            "handle": "samantha", "name": "Samantha",
            "title": "Polymath Strategic Master Orchestrator",
            "model": "gemini/gemini-3.6-flash", "skills": ["vault_recall"],
            "soul_file": "profiles/samantha_soul.md",
            "memory_file": "profiles/samantha_memory.md",
            "thinking_phrases": ["Connecting high-level dots..."],
        },
    }
    app = create_app(engine)

    payload = _route(app, "/api/personas").endpoint()

    assert payload["default"] == "samantha"
    (persona,) = payload["personas"]
    assert persona == {
        "handle": "samantha", "name": "Samantha",
        "title": "Polymath Strategic Master Orchestrator",
        "model": "gemini/gemini-3.6-flash", "skills": ["vault_recall"],
        "is_default": True,
    }
    assert "soul_file" not in persona and "thinking_phrases" not in persona
