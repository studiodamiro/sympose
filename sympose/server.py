"""
Minimal FastAPI backend for the Sympose dashboard — vault browsing, note
editing, trash recovery, and the Knowledge Nebula graph. Ported from
sympose-legacy's much larger `server.py` (~21 routes: chat, personas,
skills, Slack, search, TLS, and a password-auth middleware), trimmed to
the routes the dashboard's tree, editor, note-management menus, bin, and
nebula actually call. Deliberately not included yet: full-text search and
asset (image) serving. No auth yet — this is a local dev server bound to
localhost; add `DashboardAuthMiddleware` back before this is ever exposed
beyond that.

Request/response models and handler logic live in `server_handlers.py`
(note/folder CRUD) and `server_trash_handlers.py` (the bin); this file only
wires routes to them.
"""

from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from sympose import server_handlers as h
from sympose import server_trash_handlers as th
from sympose import vault_paths
from sympose.server_models import TrashEmpty, TrashRestore


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sympose Dashboard API (minimal)",
        description="Vault browsing and note editing — no auth, local dev only.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "healthy", "vault": vault_paths.get_master_vault()}

    @app.get("/api/vault/tree")
    def get_vault_tree(persona: str | None = Query("samantha")) -> dict[str, Any]:
        return h.get_vault_tree(persona)

    @app.get("/api/vault/graph")
    def get_vault_graph() -> dict[str, Any]:
        return h.get_vault_graph()

    @app.get("/api/vault/note")
    def read_note(
        path: str = Query(..., description="Relative path of note"),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return h.read_note(path, persona)

    @app.put("/api/vault/note")
    def write_note(body: h.NoteWrite) -> dict[str, Any]:
        return h.write_note(body)

    @app.post("/api/vault/note", status_code=201)
    def create_note(body: h.NoteCreate) -> dict[str, Any]:
        return h.create_note(body)

    @app.post("/api/vault/folder", status_code=201)
    def create_folder(body: h.FolderCreate) -> dict[str, Any]:
        return h.create_folder(body)

    @app.patch("/api/vault/note")
    def rename_note(body: h.NoteRename) -> dict[str, Any]:
        return h.rename_note(body)

    @app.delete("/api/vault/note")
    def delete_note(
        path: str = Query(..., description="Relative path of the note to delete"),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return h.delete_note(path, persona)

    @app.delete("/api/vault/folder")
    def delete_folder(
        path: str = Query(
            ..., description="Vault-relative path of the folder to delete"
        ),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return h.delete_folder(path, persona)

    @app.get("/api/vault/trash")
    def list_trash(persona: str | None = Query("samantha")) -> dict[str, Any]:
        return th.list_trash(persona)

    @app.post("/api/vault/trash/restore")
    def restore_trash(body: TrashRestore) -> dict[str, Any]:
        return th.restore_trash(body)

    @app.delete("/api/vault/trash")
    def purge_trash(
        path: str = Query(..., description="`.trash`-relative path to delete"),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return th.purge_trash(path, persona)

    @app.post("/api/vault/trash/empty")
    def empty_trash(body: TrashEmpty) -> dict[str, Any]:
        return th.empty_trash(body)

    return app
