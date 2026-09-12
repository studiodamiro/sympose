"""
FastAPI Server & Dashboard API Gateway for Sympose.
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sympose.vault import VaultManager
from sympose.config import config_manager
from sympose.auth import require_dashboard_auth
from sympose import slack_heartbeat
from sympose.workspace import resolve_workspace_dir

log = logging.getLogger(__name__)


class NoteWrite(BaseModel):
    """Body of `PUT /api/vault/note` — the dashboard editor saving an *existing*
    note back to the vault verbatim, frontmatter included (ADR-081)."""
    path: str = Field(..., min_length=1)
    content: str
    persona: str = "samantha"


class NoteCreate(BaseModel):
    """Body of `POST /api/vault/note` — create a *new* note at `path` (relative
    to the vault, e.g. `Projects/Idea`). `content` is optional; omitted, the
    backend seeds a frontmatter + title stub (ADR-083)."""
    path: str = Field(..., min_length=1)
    content: Optional[str] = None
    persona: str = "samantha"


class FolderCreate(BaseModel):
    """Body of `POST /api/vault/folder` — create a new *empty* folder at `path`
    (relative to the vault, e.g. `Projects/Archive`) (ADR-095)."""
    path: str = Field(..., min_length=1)
    persona: str = "samantha"


class NoteRename(BaseModel):
    """Body of `PATCH /api/vault/note` — rename `path` to `new_path` and rewrite
    every `[[wikilink]]` that referenced it (ADR-084). `new_path` stays in the
    same folder unless it carries a separator."""
    path: str = Field(..., min_length=1)
    new_path: str = Field(..., min_length=1)
    persona: str = "samantha"


class TrashRestore(BaseModel):
    """Body of `POST /api/vault/trash/restore` — move the trashed note at
    `path` (a `.trash`-relative path from `GET /api/vault/trash`) back to where
    it was deleted from (ADR-085)."""
    path: str = Field(..., min_length=1)
    persona: str = "samantha"


class TrashEmpty(BaseModel):
    """Body of `POST /api/vault/trash/empty` — permanently delete every in-scope
    trashed note (ADR-085)."""
    persona: str = "samantha"


def create_app(engine: Any, workspace_dir: Optional[str] = None) -> FastAPI:
    """Factory creating the FastAPI application bound to a PersonaEngine instance.
    Every route (including `/`, `/docs`, and the vault/config API) sits behind the
    ADR-064.1 password guard — call `ensure_dashboard_password()` before this so
    `DASHBOARD_PASSWORD` is set in the environment first. `workspace_dir` locates
    per-workspace runtime state (the Slack heartbeat); it defaults to the same
    resolution the CLI uses."""
    workspace_dir = workspace_dir or resolve_workspace_dir()
    app = FastAPI(
        title="Sympose Multi-Model Agent Hub API",
        version="0.2.26",
        description="FastAPI REST API & Standalone Vault Gateway for Sympose",
        docs_url="/docs",
        redoc_url="/redoc",
        dependencies=[Depends(require_dashboard_auth)],
    )

    # Restrict allowed origins via env var; defaults to localhost-only for safety
    allowed_origins = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8080").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System"])
    def health_check() -> Dict[str, Any]:
        return {
            "status": "healthy",
            "version": "0.2.26",
            "active_personas": list(engine.pm.profiles.keys()),
            "default_persona": engine.config.get("runtime.default_persona"),
        }

    @app.get("/api/personas")
    def list_personas() -> Dict[str, Any]:
        """Roster for the dashboard agent picker — a trimmed projection of each
        profile (never the raw manifest: no `soul_file` / `memory_file` paths,
        no `thinking_phrases`)."""
        default = engine.config.get("runtime.default_persona")
        return {
            "default": default,
            "personas": [
                {
                    "handle": p.get("handle", h),
                    "name": p.get("name", h),
                    "title": p.get("title", ""),
                    "model": p.get("model", ""),
                    "skills": p.get("skills") or [],
                    "is_default": p.get("handle", h) == default,
                }
                for h, p in engine.pm.profiles.items()
            ],
        }

    @app.get("/api/config")
    def get_config() -> Dict[str, Any]:
        return {"config": engine.config.data}

    @app.get("/api/slack/status")
    def slack_status() -> Dict[str, Any]:
        """Liveness of the `sympose --slack` daemon, read from its workspace
        heartbeat file (ADR-082): `state` is `connected` / `stale` / `offline`,
        with `last_seen` and the live persona handles. Read-only — the dashboard
        never starts or stops the daemon."""
        return slack_heartbeat.read_status(workspace_dir)

    @app.get("/api/vault/backlinks")
    def get_backlinks(
        note: str = Query(..., description="Target note name or wikilink stem"),
        persona: Optional[str] = Query("samantha", description="Persona handle for sandbox scoping")
    ) -> Dict[str, Any]:
        profile = engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")
        backlinks = VaultManager.get_backlinks(profile, note)
        digest = VaultManager.get_backlinks_digest(profile, note)
        return {
            "target": note,
            "count": len(backlinks),
            "backlinks": backlinks,
            "digest": digest,
        }

    @app.get("/api/vault/graph")
    def get_vault_graph() -> Dict[str, Any]:
        """Whole-vault knowledge graph (ADR-078) for the dashboard nebula:
        `{nodes: [{id, label, folder, tags, val, exists}], links: [{source, target}]}`."""
        return VaultManager.get_vault_graph()

    @app.get("/api/vault/tree")
    def get_vault_tree(
        persona: Optional[str] = Query("samantha", description="Persona handle for sandbox scoping")
    ) -> Dict[str, Any]:
        """Nested `VaultNode` directory tree (ADR-078 manifest projection) for
        the dashboard browser, scoped to the persona's allowed vault folders."""
        profile = engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")
        return {"persona": persona, "tree": VaultManager.get_vault_tree(profile)}

    @app.get("/api/vault/note")
    def read_note(
        path: str = Query(..., description="Relative path of note"),
        persona: Optional[str] = Query("samantha")
    ) -> Dict[str, Any]:
        profile = engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")
        content = VaultManager.read_note(profile, path)
        if content.startswith("Note `") and "not found" in content:
            raise HTTPException(status_code=404, detail=content)
        return {"path": path, "content": content}

    @app.put("/api/vault/note")
    def write_note(body: NoteWrite) -> Dict[str, Any]:
        """Save the dashboard editor's contents back to an existing vault note.
        404 when the note doesn't exist (no create), 403 when the path resolves
        outside the persona's sandbox."""
        profile = engine.pm.get_profile(body.persona) or engine.pm.get_profile("samantha")
        result = VaultManager.overwrite_note(profile, body.path, body.content)
        if result == VaultManager.NOTE_NOT_FOUND:
            raise HTTPException(status_code=404, detail=f"Note `{body.path}` not found in allowed vault folders.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{body.path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": body.path, "detail": result}

    @app.post("/api/vault/note", status_code=201)
    def create_note(body: NoteCreate) -> Dict[str, Any]:
        """Create a new vault note (ADR-083). 409 if a file already exists at
        that path, 403 if it resolves outside the persona's sandbox."""
        profile = engine.pm.get_profile(body.persona) or engine.pm.get_profile("samantha")
        result = VaultManager.create_note(profile, body.path, body.content)
        if result == VaultManager.NOTE_EXISTS:
            raise HTTPException(status_code=409, detail=f"A note already exists at `{body.path}`.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{body.path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": body.path, "detail": result}

    @app.post("/api/vault/folder", status_code=201)
    def create_folder(body: FolderCreate) -> Dict[str, Any]:
        """Create a new empty vault folder (ADR-095). 409 if a file or folder
        already exists at that path, 403 if it resolves outside the persona's
        sandbox."""
        profile = engine.pm.get_profile(body.persona) or engine.pm.get_profile("samantha")
        result = VaultManager.create_folder(profile, body.path)
        if result == VaultManager.NOTE_EXISTS:
            raise HTTPException(status_code=409, detail=f"A file or folder already exists at `{body.path}`.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{body.path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": body.path, "detail": result}

    @app.delete("/api/vault/folder")
    def delete_folder(
        path: str = Query(..., description="Vault-relative path of the folder to delete"),
        persona: Optional[str] = Query("samantha"),
    ) -> Dict[str, Any]:
        """Delete a vault folder (ADR-099): an empty one is removed outright,
        a non-empty one moves to `<vault>/.trash/` like a note (ADR-084). 404
        if it doesn't exist, 403 if it resolves outside the persona's sandbox."""
        profile = engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")
        result = VaultManager.delete_folder(profile, path)
        if result == VaultManager.NOTE_NOT_FOUND:
            raise HTTPException(status_code=404, detail=f"Folder `{path}` not found in allowed vault folders.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": path, "detail": result}

    @app.patch("/api/vault/note")
    def rename_note(body: NoteRename) -> Dict[str, Any]:
        """Rename a note and rewrite the `[[wikilinks]]` that pointed at it
        (ADR-084). 404 if the source is gone, 409 if the target exists, 403
        outside the sandbox."""
        profile = engine.pm.get_profile(body.persona) or engine.pm.get_profile("samantha")
        result = VaultManager.rename_note(profile, body.path, body.new_path)
        if result == VaultManager.NOTE_NOT_FOUND:
            raise HTTPException(status_code=404, detail=f"Note `{body.path}` not found in allowed vault folders.")
        if result == VaultManager.NOTE_EXISTS:
            raise HTTPException(status_code=409, detail=f"A note already exists at `{body.new_path}`.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{body.new_path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": body.new_path, "detail": result}

    @app.delete("/api/vault/note")
    def delete_note(
        path: str = Query(..., description="Relative path of the note to delete"),
        persona: Optional[str] = Query("samantha"),
    ) -> Dict[str, Any]:
        """Move a note to `<vault>/.trash/` (ADR-084). 404 if it doesn't exist,
        403 if it resolves outside the persona's sandbox."""
        profile = engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")
        result = VaultManager.delete_note(profile, path)
        if result == VaultManager.NOTE_NOT_FOUND:
            raise HTTPException(status_code=404, detail=f"Note `{path}` not found in allowed vault folders.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": path, "detail": result}

    @app.get("/api/vault/trash")
    def list_trash(
        persona: Optional[str] = Query("samantha"),
    ) -> Dict[str, Any]:
        """Recoverable notes in `<vault>/.trash` (ADR-085), scoped to the
        persona, newest deletion first."""
        profile = engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")
        items = VaultManager.list_trash(profile)
        return {"count": len(items), "items": items}

    @app.post("/api/vault/trash/restore")
    def restore_trash(body: TrashRestore) -> Dict[str, Any]:
        """Move a trashed note back to its original path (ADR-085). 404 if it's
        not in the trash, 409 if something occupies the original path now, 403
        outside the sandbox."""
        profile = engine.pm.get_profile(body.persona) or engine.pm.get_profile("samantha")
        result = VaultManager.restore_from_trash(profile, body.path)
        if result == VaultManager.NOTE_NOT_FOUND:
            raise HTTPException(status_code=404, detail=f"`{body.path}` is not in the bin.")
        if result == VaultManager.NOTE_EXISTS:
            raise HTTPException(status_code=409, detail="A note already exists at the original path.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{body.path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": body.path, "detail": result}

    @app.delete("/api/vault/trash")
    def purge_trash(
        path: str = Query(..., description="`.trash`-relative path of the note to delete forever"),
        persona: Optional[str] = Query("samantha"),
    ) -> Dict[str, Any]:
        """Permanently delete one trashed note (ADR-085). 404 if it's not in the
        trash, 403 outside the sandbox."""
        profile = engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")
        result = VaultManager.purge_from_trash(profile, path)
        if result == VaultManager.NOTE_NOT_FOUND:
            raise HTTPException(status_code=404, detail=f"`{path}` is not in the bin.")
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail=f"Path `{path}` is outside the assigned sandbox.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"path": path, "detail": result}

    @app.post("/api/vault/trash/empty")
    def empty_trash(body: TrashEmpty) -> Dict[str, Any]:
        """Permanently delete every in-scope trashed note (ADR-085)."""
        profile = engine.pm.get_profile(body.persona) or engine.pm.get_profile("samantha")
        result = VaultManager.empty_trash(profile)
        if result == VaultManager.NOTE_DENIED:
            raise HTTPException(status_code=403, detail="Vault access denied for this persona.")
        if result.startswith("Error:"):
            raise HTTPException(status_code=500, detail=result)
        return {"detail": result}

    # Resolve the frontend root. The committed, packaged bundle
    # (`sympose/webui/`, ADR-079) is authoritative — it ships in the wheel, so a
    # `pipx install git+…` serves the real dashboard. A source checkout that has
    # run `npm run build` also writes there. The old `ui/dist` and the
    # hand-authored `ui/` scaffold remain as fallbacks for a stale tree.
    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    _pkg_root = os.path.dirname(_pkg_dir)
    ui_candidates = [
        os.path.join(_pkg_dir, "webui"),
        os.path.join(_pkg_root, "ui", "dist"),
        os.path.join(os.getcwd(), "ui", "dist"),
        os.path.join(_pkg_root, "ui"),
        os.path.join(os.getcwd(), "ui"),
    ]
    ui_root = next((p for p in ui_candidates if os.path.isfile(os.path.join(p, "index.html"))), None)
    if ui_root:
        log.info("[server] dashboard frontend: %s", ui_root)
    else:
        log.warning(
            "[server] no UI bundle found (looked under %s and CWD) — serving the "
            "API-only placeholder at `/`. Build it with `cd ui && npm run build`.",
            _pkg_root,
        )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        if ui_root:
            with open(os.path.join(ui_root, "index.html"), "r", encoding="utf-8") as f:
                return f.read()

        try:
            from importlib.metadata import version as pkg_version
            _version = pkg_version("sympose")
        except Exception:
            _version = "0.2.26"
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Sympose // Multi-Model Agent Hub &amp; Vault Gateway</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; background: #080D14; color: #E2E8F0; margin: 0; padding: 40px 20px; display: flex; justify-content: center; align-items: center; min-height: 80vh; }}
                .card {{ background: #0E1726; border: 1px solid #1E293B; border-radius: 16px; max-width: 620px; width: 100%; padding: 36px; box-shadow: 0 20px 40px rgba(0,0,0,0.6); }}
                .header-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }}
                .brand-badge {{ background: #0C4A6E; color: #38BDF8; padding: 6px 12px; border-radius: 8px; font-size: 13px; font-weight: 700; font-family: monospace; letter-spacing: 0.05em; border: 1px solid #0284C7; }}
                .sla-badge {{ background: #064E3B; color: #34D399; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
                h1 {{ color: #38BDF8; font-size: 24px; margin: 0 0 10px 0; font-weight: 700; letter-spacing: -0.02em; }}
                p {{ line-height: 1.6; color: #94A3B8; margin-bottom: 24px; font-size: 15px; }}
                ul {{ list-style: none; padding: 0; margin: 0; }}
                li {{ padding: 14px 0; border-bottom: 1px solid #1E293B; display: flex; justify-content: space-between; align-items: center; }}
                li:last-child {{ border-bottom: none; }}
                .endpoint-label {{ color: #CBD5E1; font-weight: 500; font-size: 14px; }}
                a.btn {{ background: #1E293B; color: #38BDF8; padding: 6px 14px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; border: 1px solid #334155; transition: all 0.15s ease; }}
                a.btn:hover {{ background: #0284C7; color: #FFFFFF; border-color: #38BDF8; }}
                code {{ background: #1E293B; padding: 2px 6px; border-radius: 4px; font-family: ui-monospace, monospace; color: #F1F5F9; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header-row">
                    <span class="brand-badge">&lt;S&gt; S Y M P O S E</span>
                    <span class="sla-badge">Live Gateway &bull; v{_version}</span>
                </div>
                <h1>Multi-Model Agent Hub &amp; Vault API</h1>
                <p>Zero-Bloat AI Orchestration Runtime &amp; Standalone Obsidian Vault Gateway running on <code>localhost:8000</code>.</p>
                <ul>
                    <li><span class="endpoint-label">📖 Interactive Swagger API Docs</span> <a class="btn" href="/docs">/docs</a></li>
                    <li><span class="endpoint-label">🏥 Health &amp; Runtime Status</span> <a class="btn" href="/health">/health</a></li>
                    <li><span class="endpoint-label">🎭 Active Personas Index</span> <a class="btn" href="/api/personas">/api/personas</a></li>
                    <li><span class="endpoint-label">⚙️ Live Configuration Knobs</span> <a class="btn" href="/api/config">/api/config</a></li>
                </ul>
            </div>
        </body>
        </html>
        """

    # Serve the rest of the frontend bundle (hashed assets, sympose.svg, etc.)
    # from the resolved root. Registered last so it never shadows an API route;
    # the explicit "/" handler above still owns the index document. Unknown
    # non-API paths fall back to index.html so the client-side router
    # (react-router) can resolve deep links like /components on a hard refresh.
    if ui_root:
        from starlette.exceptions import HTTPException as StarletteHTTPException

        class SPAStaticFiles(StaticFiles):
            async def get_response(self, path: str, scope):  # type: ignore[override]
                try:
                    return await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    if exc.status_code == 404 and not path.startswith("api"):
                        return await super().get_response("index.html", scope)
                    raise

        app.mount("/", SPAStaticFiles(directory=ui_root, html=True), name="ui")

    return app


def run_server(engine: Any, workspace_dir: str, host: str = "127.0.0.1", port: int = 8000, tls: bool = True) -> None:
    """Launches the Uvicorn ASGI server hosting the Sympose Dashboard API.
    Generates/loads the ADR-064.1 dashboard password and, unless `tls=False` or
    `cryptography` isn't installed, the ADR-064.2 self-signed certificate,
    before the app (and its global auth dependency) is constructed."""
    import uvicorn
    from sympose.auth import ensure_dashboard_password, DASHBOARD_USER

    password = ensure_dashboard_password(workspace_dir)
    app = create_app(engine, workspace_dir=workspace_dir)

    ssl_kwargs: Dict[str, Any] = {}
    if tls:
        from sympose.tls import ensure_self_signed_cert
        cert_pair = ensure_self_signed_cert(workspace_dir)
        if cert_pair:
            ssl_kwargs = {"ssl_certfile": cert_pair[0], "ssl_keyfile": cert_pair[1]}

    scheme = "https" if ssl_kwargs else "http"
    print(f"\nSympose Dashboard running at: {scheme}://{host}:{port}", flush=True)
    print(f"Login — user: {DASHBOARD_USER}  password: {password}  (see workspace .env)\n", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info", **ssl_kwargs)
