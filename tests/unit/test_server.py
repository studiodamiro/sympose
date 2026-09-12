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


def test_slack_status_endpoint_registered_and_reads_heartbeat(tmp_path, monkeypatch):
    from sympose import slack_heartbeat

    engine = MagicMock()
    engine.pm.profiles = {}
    app = create_app(engine, workspace_dir=str(tmp_path))
    route = _route(app, "/api/slack/status")

    # No heartbeat file yet -> offline
    assert route.endpoint()["state"] == "offline"

    # Daemon writes one -> connected, with persona handles
    slack_heartbeat.write_heartbeat(str(tmp_path), ["samantha"])
    payload = route.endpoint()
    assert payload["state"] == "connected"
    assert payload["personas"] == ["samantha"]


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


class TestVaultNoteCreate:
    """`POST /api/vault/note` maps `VaultManager.create_note`'s sentinels onto
    HTTP status codes (ADR-083)."""

    def _client(self, monkeypatch, create_result):
        from fastapi.testclient import TestClient
        from sympose.auth import DASHBOARD_USER
        import sympose.server as server

        monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
        monkeypatch.setattr(
            server.VaultManager, "create_note",
            classmethod(lambda cls, profile, path, content=None: create_result),
        )
        engine = MagicMock()
        engine.pm.get_profile.return_value = {"vault_folders": ["*"]}
        engine.pm.profiles = {}
        return TestClient(server.create_app(engine)), DASHBOARD_USER

    def test_success_returns_201(self, monkeypatch):
        client, user = self._client(monkeypatch, "Created note: `Ideas/x.md`")
        resp = client.post(
            "/api/vault/note", json={"path": "Ideas/x"}, auth=(user, "pw")
        )
        assert resp.status_code == 201
        assert resp.json()["detail"].startswith("Created note:")

    def test_existing_note_returns_409(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_EXISTS)
        resp = client.post(
            "/api/vault/note", json={"path": "Ideas/taken"}, auth=(user, "pw")
        )
        assert resp.status_code == 409

    def test_denied_returns_403(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_DENIED)
        resp = client.post(
            "/api/vault/note", json={"path": "../evil"}, auth=(user, "pw")
        )
        assert resp.status_code == 403


class TestVaultFolderCreate:
    """`POST /api/vault/folder` maps `VaultManager.create_folder`'s sentinels
    onto HTTP status codes (ADR-095)."""

    def _client(self, monkeypatch, create_result):
        from fastapi.testclient import TestClient
        from sympose.auth import DASHBOARD_USER
        import sympose.server as server

        monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
        monkeypatch.setattr(
            server.VaultManager, "create_folder",
            classmethod(lambda cls, profile, path: create_result),
        )
        engine = MagicMock()
        engine.pm.get_profile.return_value = {"vault_folders": ["*"]}
        engine.pm.profiles = {}
        return TestClient(server.create_app(engine)), DASHBOARD_USER

    def test_success_returns_201(self, monkeypatch):
        client, user = self._client(monkeypatch, "Created folder: `Ideas/Archive`")
        resp = client.post(
            "/api/vault/folder", json={"path": "Ideas/Archive"}, auth=(user, "pw")
        )
        assert resp.status_code == 201
        assert resp.json()["detail"].startswith("Created folder:")

    def test_existing_path_returns_409(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_EXISTS)
        resp = client.post(
            "/api/vault/folder", json={"path": "Ideas/Taken"}, auth=(user, "pw")
        )
        assert resp.status_code == 409

    def test_denied_returns_403(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_DENIED)
        resp = client.post(
            "/api/vault/folder", json={"path": "../evil"}, auth=(user, "pw")
        )
        assert resp.status_code == 403


class TestVaultFolderDelete:
    """`DELETE /api/vault/folder` maps `VaultManager.delete_folder`'s
    sentinels onto HTTP status codes (ADR-099)."""

    def _client(self, monkeypatch, delete_result):
        from fastapi.testclient import TestClient
        from sympose.auth import DASHBOARD_USER
        import sympose.server as server

        monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
        monkeypatch.setattr(
            server.VaultManager, "delete_folder",
            classmethod(lambda cls, profile, path: delete_result),
        )
        engine = MagicMock()
        engine.pm.get_profile.return_value = {"vault_folders": ["*"]}
        engine.pm.profiles = {}
        return TestClient(server.create_app(engine)), DASHBOARD_USER

    def test_success_returns_200(self, monkeypatch):
        client, user = self._client(
            monkeypatch, "Moved folder to the bin: `Ideas/Archive` (2 notes)"
        )
        resp = client.delete(
            "/api/vault/folder", params={"path": "Ideas/Archive"}, auth=(user, "pw")
        )
        assert resp.status_code == 200
        assert resp.json()["detail"].startswith("Moved folder to the bin:")

    def test_not_found_returns_404(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_NOT_FOUND)
        resp = client.delete(
            "/api/vault/folder", params={"path": "Ghost"}, auth=(user, "pw")
        )
        assert resp.status_code == 404

    def test_denied_returns_403(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, VaultManager.NOTE_DENIED)
        resp = client.delete(
            "/api/vault/folder", params={"path": "../evil"}, auth=(user, "pw")
        )
        assert resp.status_code == 403


class TestVaultNoteRenameDelete:
    """`PATCH` / `DELETE /api/vault/note` sentinel → status-code mapping (ADR-084)."""

    def _client(self, monkeypatch, *, rename_result=None, delete_result=None):
        from fastapi.testclient import TestClient
        from sympose.auth import DASHBOARD_USER
        import sympose.server as server

        monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
        if rename_result is not None:
            monkeypatch.setattr(
                server.VaultManager, "rename_note",
                classmethod(lambda cls, profile, path, new_path: rename_result),
            )
        if delete_result is not None:
            monkeypatch.setattr(
                server.VaultManager, "delete_note",
                classmethod(lambda cls, profile, path: delete_result),
            )
        engine = MagicMock()
        engine.pm.get_profile.return_value = {"vault_folders": ["*"]}
        engine.pm.profiles = {}
        return TestClient(server.create_app(engine)), DASHBOARD_USER

    def test_rename_success(self, monkeypatch):
        client, user = self._client(monkeypatch, rename_result="Renamed to `N/b.md` (2 files relinked)")
        resp = client.patch(
            "/api/vault/note", json={"path": "N/a", "new_path": "b"}, auth=(user, "pw")
        )
        assert resp.status_code == 200
        assert resp.json()["path"] == "b"

    def test_rename_target_exists_409(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, rename_result=VaultManager.NOTE_EXISTS)
        resp = client.patch(
            "/api/vault/note", json={"path": "N/a", "new_path": "b"}, auth=(user, "pw")
        )
        assert resp.status_code == 409

    def test_rename_missing_404(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, rename_result=VaultManager.NOTE_NOT_FOUND)
        resp = client.patch(
            "/api/vault/note", json={"path": "ghost", "new_path": "b"}, auth=(user, "pw")
        )
        assert resp.status_code == 404

    def test_delete_success(self, monkeypatch):
        client, user = self._client(monkeypatch, delete_result="Moved to the bin: `.trash/N/a.md`")
        resp = client.delete("/api/vault/note?path=N/a", auth=(user, "pw"))
        assert resp.status_code == 200
        assert "bin" in resp.json()["detail"]

    def test_delete_missing_404(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, delete_result=VaultManager.NOTE_NOT_FOUND)
        resp = client.delete("/api/vault/note?path=ghost", auth=(user, "pw"))
        assert resp.status_code == 404

    def test_delete_denied_403(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, delete_result=VaultManager.NOTE_DENIED)
        resp = client.delete("/api/vault/note?path=../evil", auth=(user, "pw"))
        assert resp.status_code == 403


class TestVaultTrash:
    """`/api/vault/trash*` sentinel → status-code mapping (ADR-085)."""

    def _client(self, monkeypatch, **overrides):
        from fastapi.testclient import TestClient
        from sympose.auth import DASHBOARD_USER
        import sympose.server as server

        monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
        for name, value in overrides.items():
            monkeypatch.setattr(
                server.VaultManager, name,
                classmethod(lambda cls, *a, _v=value, **k: _v),
            )
        engine = MagicMock()
        engine.pm.get_profile.return_value = {"vault_folders": ["*"]}
        engine.pm.profiles = {}
        return TestClient(server.create_app(engine)), DASHBOARD_USER

    def test_list_trash_shape(self, monkeypatch):
        rows = [{"trash_path": "a.md", "original_path": "a.md", "deleted_at": 1.0, "size": 3}]
        client, user = self._client(monkeypatch, list_trash=rows)
        resp = client.get("/api/vault/trash", auth=(user, "pw"))
        assert resp.status_code == 200
        assert resp.json() == {"count": 1, "items": rows}

    def test_restore_success(self, monkeypatch):
        client, user = self._client(monkeypatch, restore_from_trash="Restored to `Notes/a.md`")
        resp = client.post(
            "/api/vault/trash/restore", json={"path": "Notes/a.md"}, auth=(user, "pw")
        )
        assert resp.status_code == 200
        assert "Restored" in resp.json()["detail"]

    def test_restore_missing_404(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, restore_from_trash=VaultManager.NOTE_NOT_FOUND)
        resp = client.post(
            "/api/vault/trash/restore", json={"path": "ghost.md"}, auth=(user, "pw")
        )
        assert resp.status_code == 404

    def test_restore_target_occupied_409(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, restore_from_trash=VaultManager.NOTE_EXISTS)
        resp = client.post(
            "/api/vault/trash/restore", json={"path": "a.md"}, auth=(user, "pw")
        )
        assert resp.status_code == 409

    def test_purge_success(self, monkeypatch):
        client, user = self._client(monkeypatch, purge_from_trash="Deleted permanently")
        resp = client.delete("/api/vault/trash?path=a.md", auth=(user, "pw"))
        assert resp.status_code == 200

    def test_purge_denied_403(self, monkeypatch):
        from sympose.vault import VaultManager
        client, user = self._client(monkeypatch, purge_from_trash=VaultManager.NOTE_DENIED)
        resp = client.delete("/api/vault/trash?path=../evil.md", auth=(user, "pw"))
        assert resp.status_code == 403

    def test_empty_trash(self, monkeypatch):
        client, user = self._client(monkeypatch, empty_trash="Emptied the bin (3 notes)")
        resp = client.post("/api/vault/trash/empty", json={}, auth=(user, "pw"))
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Emptied the bin (3 notes)"


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
