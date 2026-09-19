"""
FastAPI Server & Dashboard API Gateway for Sympose.

`create_app` used to register all ~21 routes as nested `@app.get/...`
closures directly in its own body — mccabe flagged it at complexity 58
(every nested route handler's own branching rolls up into the enclosing
factory function's total, the same reason `commands.py`'s `intercept` and
`actions.py`'s `execute_actions` were flagged). Unlike those two, simply
making each nested handler a trivial one-line delegator isn't enough on
its own here: mccabe counts *each* nested function definition, trivial or
not, so 21 routes alone put a floor around 20+ regardless of what's
inside them. The fix is the same principle as splitting a too-big file
into cohesive modules, applied to route registration instead: the routes
are grouped by resource onto separate `_register_*_routes(app, ...)`
functions (`_register_system_routes`, `_register_vault_read_routes`,
`_register_vault_write_routes`, `_register_vault_trash_routes`), each a
small top-level function decorating `app` directly (not an `APIRouter` —
this FastAPI version's `include_router` wraps routes in an internal
`_IncludedRouter` that no longer flattens into `app.routes`, which the
existing route-introspection tests rely on; registering straight on
`app` from a smaller function keeps that structure identical while still
keeping each function's own nested-def count, and therefore its
complexity, low). Each route's actual logic also moved into a plain
top-level `_verb_noun(engine, ...)` function — the nested route handler
itself is just `return _verb_noun(engine, ...)` now — and the six
near-identical "translate a VaultManager sentinel result into the right
HTTPException" blocks collapsed into one `_translate_vault_result`
helper.
"""

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sympose import slack_heartbeat
from sympose.auth import DashboardAuthMiddleware
from sympose.server_chat import register_chat_routes
from sympose.config import get_version
from sympose.vault import VaultManager
from sympose.workspace import resolve_workspace_dir

log = logging.getLogger(__name__)


class NoteWrite(BaseModel):
    """Body of `PUT /api/vault/note` — the dashboard editor saving an *existing*
    note back to the vault verbatim, frontmatter included (ADR-081)."""

    path: str = Field(..., min_length=1)
    content: str
    persona: str = "samantha"
    expected_mtime: float | None = Field(
        None,
        description="mtime this save was opened from (from GET /api/vault/note). "
        "When given, a save is rejected with 409 if the file changed on disk "
        "since then (ADR-129) instead of silently overwriting it.",
    )


class NoteCreate(BaseModel):
    """Body of `POST /api/vault/note` — create a *new* note at `path` (relative
    to the vault, e.g. `Projects/Idea`). `content` is optional; omitted, the
    backend seeds a frontmatter + title stub (ADR-083)."""

    path: str = Field(..., min_length=1)
    content: str | None = None
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


def _resolve_profile(engine: Any, persona: str | None) -> dict[str, Any]:
    return engine.pm.get_profile(persona) or engine.pm.get_profile("samantha")


def _translate_vault_result(
    result: str,
    *,
    not_found: str | None = None,
    exists: str | None = None,
    denied: str | None = None,
    conflict: str | None = None,
) -> None:
    """Raises the matching HTTPException for one of VaultManager's shared
    sentinel outcomes, or returns None when `result` is a genuine success
    message. A caller passes only the sentinels it can actually hit —
    e.g. `write_note` never creates, so it has no `exists` message."""
    if not_found is not None and result == VaultManager.NOTE_NOT_FOUND:
        raise HTTPException(status_code=404, detail=not_found)
    if exists is not None and result == VaultManager.NOTE_EXISTS:
        raise HTTPException(status_code=409, detail=exists)
    if denied is not None and result == VaultManager.NOTE_DENIED:
        raise HTTPException(status_code=403, detail=denied)
    if conflict is not None and result == VaultManager.NOTE_CONFLICT:
        raise HTTPException(status_code=409, detail=conflict)
    if result.startswith("Error:"):
        raise HTTPException(status_code=500, detail=result)


# --- System routes -----------------------------------------------------------
def _health_check(engine: Any) -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": get_version(),
        "active_personas": list(engine.pm.profiles.keys()),
        "default_persona": engine.config.get("runtime.default_persona"),
    }


def _list_personas(engine: Any) -> dict[str, Any]:
    """Roster for the dashboard persona picker — a trimmed projection of each
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


def _register_system_routes(app: FastAPI, engine: Any, workspace_dir: str) -> None:
    @app.get("/health", tags=["System"])
    def health_check() -> dict[str, Any]:
        return _health_check(engine)

    @app.get("/api/personas")
    def list_personas() -> dict[str, Any]:
        return _list_personas(engine)

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        return {"config": engine.config.data}

    @app.get("/api/slack/status")
    def slack_status() -> dict[str, Any]:
        """Liveness of the `sympose --slack` daemon, read from its workspace
        heartbeat file (ADR-082): `state` is `connected` / `stale` /
        `offline`, with `last_seen` and the live persona handles. Read-only —
        the dashboard never starts or stops the daemon."""
        return slack_heartbeat.read_status(workspace_dir)


# --- Vault read routes ---------------------------------------------------------
def _get_backlinks(engine: Any, note: str, persona: str | None) -> dict[str, Any]:
    profile = _resolve_profile(engine, persona)
    backlinks = VaultManager.get_backlinks(profile, note)
    digest = VaultManager.get_backlinks_digest(profile, note)
    return {
        "target": note,
        "count": len(backlinks),
        "backlinks": backlinks,
        "digest": digest,
    }


def _get_vault_tree(engine: Any, persona: str | None) -> dict[str, Any]:
    """Nested `VaultNode` directory tree (ADR-078 manifest projection) for
    the dashboard browser, scoped to the persona's allowed vault folders."""
    profile = _resolve_profile(engine, persona)
    return {
        "persona": persona,
        "tree": VaultManager.get_vault_tree(profile),
        "vaultName": VaultManager.get_vault_name(),
    }


def _search_vault(engine: Any, q: str, persona: str | None) -> dict[str, Any]:
    """Full-text vault search (ADR-057 structured results — title + content
    matches with snippets) for the dashboard search field's content tier,
    behind the tree's instant client-side name/tag/link filter. Whole-vault
    within the persona's sandbox, not scoped to whatever folder the panel
    currently has open — a content hit can live anywhere. Same engine as
    the CLI/Slack `/vault` command (`VaultManager.search_structured`)."""
    profile = _resolve_profile(engine, persona)
    return {"query": q, "results": VaultManager.search_structured(profile, q)}


def _get_vault_asset(engine: Any, path: str, persona: str | None) -> FileResponse:
    """Raw file bytes for one vault asset — backs stylo's `![[ref]]` image
    embeds (the `embedSource` prop), scoped to the persona's allowed vault
    folders. 404 if it doesn't resolve inside the sandbox."""
    profile = _resolve_profile(engine, persona)
    resolved = VaultManager.resolve_asset_path(profile, path)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"Asset `{path}` not found in allowed vault folders.",
        )
    return FileResponse(resolved)


def _read_note(engine: Any, path: str, persona: str | None) -> dict[str, Any]:
    profile = _resolve_profile(engine, persona)
    # ADR-129: content and mtime come from the same resolved file in one
    # pass (read_note_with_mtime), not two independent lookups — otherwise
    # a concurrent write landing between them could hand back a mtime that
    # doesn't actually describe the content in this response, undermining
    # the round-trip a later save's expected_mtime depends on.
    content, mtime = VaultManager.read_note_with_mtime(profile, path)
    if content.startswith("Note `") and "not found" in content:
        raise HTTPException(status_code=404, detail=content)
    return {"path": path, "content": content, "mtime": mtime}


def _list_trash(engine: Any, persona: str | None) -> dict[str, Any]:
    """Recoverable notes in `<vault>/.trash` (ADR-085), scoped to the
    persona, newest deletion first."""
    profile = _resolve_profile(engine, persona)
    items = VaultManager.list_trash(profile)
    return {"count": len(items), "items": items}


def _register_vault_read_routes(app: FastAPI, engine: Any) -> None:
    @app.get("/api/vault/backlinks")
    def get_backlinks(
        note: str = Query(..., description="Target note name or wikilink stem"),
        persona: str | None = Query(
            "samantha", description="Persona handle for sandbox scoping"
        ),
    ) -> dict[str, Any]:
        return _get_backlinks(engine, note, persona)

    @app.get("/api/vault/graph")
    def get_vault_graph() -> dict[str, Any]:
        """Whole-vault knowledge graph (ADR-078) for the dashboard nebula:
        `{nodes: [{id, label, folder, tags, val, exists}], links: [{source, target}]}`."""
        return VaultManager.get_vault_graph()

    @app.get("/api/vault/tree")
    def get_vault_tree(
        persona: str | None = Query(
            "samantha", description="Persona handle for sandbox scoping"
        ),
    ) -> dict[str, Any]:
        return _get_vault_tree(engine, persona)

    @app.get("/api/vault/search")
    def search_vault(
        q: str = Query(..., min_length=1, description="Search query"),
        persona: str | None = Query(
            "samantha", description="Persona handle for sandbox scoping"
        ),
    ) -> dict[str, Any]:
        return _search_vault(engine, q, persona)

    @app.get("/api/vault/asset")
    def get_vault_asset(
        path: str = Query(
            ..., description="Relative path of the vault asset (image, etc.)"
        ),
        persona: str | None = Query(
            "samantha", description="Persona handle for sandbox scoping"
        ),
    ) -> FileResponse:
        return _get_vault_asset(engine, path, persona)

    @app.get("/api/vault/note")
    def read_note(
        path: str = Query(..., description="Relative path of note"),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return _read_note(engine, path, persona)

    @app.get("/api/vault/trash")
    def list_trash(persona: str | None = Query("samantha")) -> dict[str, Any]:
        return _list_trash(engine, persona)


# --- Vault write routes --------------------------------------------------------
def _write_note(engine: Any, body: NoteWrite) -> dict[str, Any]:
    """Save the dashboard editor's contents back to an existing vault note.
    404 when the note doesn't exist (no create), 403 when the path resolves
    outside the persona's sandbox, 409 when `expected_mtime` was given and
    the file changed on disk since the editor opened it (ADR-129)."""
    profile = _resolve_profile(engine, body.persona)
    result = VaultManager.overwrite_note(
        profile, body.path, body.content, expected_mtime=body.expected_mtime
    )
    _translate_vault_result(
        result,
        not_found=f"Note `{body.path}` not found in allowed vault folders.",
        denied=f"Path `{body.path}` is outside the assigned sandbox.",
        conflict=f"Note `{body.path}` changed on disk since it was opened — reload before saving.",
    )
    return {"path": body.path, "detail": result}


def _create_note(engine: Any, body: NoteCreate) -> dict[str, Any]:
    """Create a new vault note (ADR-083). 409 if a file already exists at
    that path, 403 if it resolves outside the persona's sandbox."""
    profile = _resolve_profile(engine, body.persona)
    result = VaultManager.create_note(profile, body.path, body.content)
    _translate_vault_result(
        result,
        exists=f"A note already exists at `{body.path}`.",
        denied=f"Path `{body.path}` is outside the assigned sandbox.",
    )
    return {"path": body.path, "detail": result}


def _create_folder(engine: Any, body: FolderCreate) -> dict[str, Any]:
    """Create a new empty vault folder (ADR-095). 409 if a file or folder
    already exists at that path, 403 if it resolves outside the persona's
    sandbox."""
    profile = _resolve_profile(engine, body.persona)
    result = VaultManager.create_folder(profile, body.path)
    _translate_vault_result(
        result,
        exists=f"A file or folder already exists at `{body.path}`.",
        denied=f"Path `{body.path}` is outside the assigned sandbox.",
    )
    return {"path": body.path, "detail": result}


def _delete_folder(engine: Any, path: str, persona: str | None) -> dict[str, Any]:
    """Delete a vault folder (ADR-099): an empty one is removed outright, a
    non-empty one moves to `<vault>/.trash/` like a note (ADR-084). 404 if
    it doesn't exist, 403 if it resolves outside the persona's sandbox."""
    profile = _resolve_profile(engine, persona)
    result = VaultManager.delete_folder(profile, path)
    _translate_vault_result(
        result,
        not_found=f"Folder `{path}` not found in allowed vault folders.",
        denied=f"Path `{path}` is outside the assigned sandbox.",
    )
    return {"path": path, "detail": result}


def _rename_note(engine: Any, body: NoteRename) -> dict[str, Any]:
    """Rename a note and rewrite the `[[wikilinks]]` that pointed at it
    (ADR-084). 404 if the source is gone, 409 if the target exists, 403
    outside the sandbox."""
    profile = _resolve_profile(engine, body.persona)
    result = VaultManager.rename_note(profile, body.path, body.new_path)
    _translate_vault_result(
        result,
        not_found=f"Note `{body.path}` not found in allowed vault folders.",
        exists=f"A note already exists at `{body.new_path}`.",
        denied=f"Path `{body.new_path}` is outside the assigned sandbox.",
    )
    return {"path": body.new_path, "detail": result}


def _delete_note(engine: Any, path: str, persona: str | None) -> dict[str, Any]:
    """Move a note to `<vault>/.trash/` (ADR-084). 404 if it doesn't exist,
    403 if it resolves outside the persona's sandbox."""
    profile = _resolve_profile(engine, persona)
    result = VaultManager.delete_note(profile, path)
    _translate_vault_result(
        result,
        not_found=f"Note `{path}` not found in allowed vault folders.",
        denied=f"Path `{path}` is outside the assigned sandbox.",
    )
    return {"path": path, "detail": result}


def _register_vault_write_routes(app: FastAPI, engine: Any) -> None:
    @app.put("/api/vault/note")
    def write_note(body: NoteWrite) -> dict[str, Any]:
        return _write_note(engine, body)

    @app.post("/api/vault/note", status_code=201)
    def create_note(body: NoteCreate) -> dict[str, Any]:
        return _create_note(engine, body)

    @app.post("/api/vault/folder", status_code=201)
    def create_folder(body: FolderCreate) -> dict[str, Any]:
        return _create_folder(engine, body)

    @app.delete("/api/vault/folder")
    def delete_folder(
        path: str = Query(
            ..., description="Vault-relative path of the folder to delete"
        ),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return _delete_folder(engine, path, persona)

    @app.patch("/api/vault/note")
    def rename_note(body: NoteRename) -> dict[str, Any]:
        return _rename_note(engine, body)

    @app.delete("/api/vault/note")
    def delete_note(
        path: str = Query(..., description="Relative path of the note to delete"),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return _delete_note(engine, path, persona)


# --- Vault trash routes -----------------------------------------------------
def _restore_trash(engine: Any, body: TrashRestore) -> dict[str, Any]:
    """Move a trashed note back to its original path (ADR-085). 404 if it's
    not in the trash, 409 if something occupies the original path now, 403
    outside the sandbox."""
    profile = _resolve_profile(engine, body.persona)
    result = VaultManager.restore_from_trash(profile, body.path)
    _translate_vault_result(
        result,
        not_found=f"`{body.path}` is not in the bin.",
        exists="A note already exists at the original path.",
        denied=f"Path `{body.path}` is outside the assigned sandbox.",
    )
    return {"path": body.path, "detail": result}


def _purge_trash(engine: Any, path: str, persona: str | None) -> dict[str, Any]:
    """Permanently delete one trashed note (ADR-085). 404 if it's not in the
    trash, 403 outside the sandbox."""
    profile = _resolve_profile(engine, persona)
    result = VaultManager.purge_from_trash(profile, path)
    _translate_vault_result(
        result,
        not_found=f"`{path}` is not in the bin.",
        denied=f"Path `{path}` is outside the assigned sandbox.",
    )
    return {"path": path, "detail": result}


def _empty_trash(engine: Any, body: TrashEmpty) -> dict[str, Any]:
    """Permanently delete every in-scope trashed note (ADR-085)."""
    profile = _resolve_profile(engine, body.persona)
    result = VaultManager.empty_trash(profile)
    _translate_vault_result(result, denied="Vault access denied for this persona.")
    return {"detail": result}


def _register_vault_trash_routes(app: FastAPI, engine: Any) -> None:
    @app.post("/api/vault/trash/restore")
    def restore_trash(body: TrashRestore) -> dict[str, Any]:
        return _restore_trash(engine, body)

    @app.delete("/api/vault/trash")
    def purge_trash(
        path: str = Query(
            ..., description="`.trash`-relative path of the note to delete forever"
        ),
        persona: str | None = Query("samantha"),
    ) -> dict[str, Any]:
        return _purge_trash(engine, path, persona)

    @app.post("/api/vault/trash/empty")
    def empty_trash(body: TrashEmpty) -> dict[str, Any]:
        return _empty_trash(engine, body)


# --- Frontend (dashboard SPA) -------------------------------------------------
def _resolve_allowed_origins() -> list[str]:
    """CORS allow-list from `ALLOWED_ORIGINS`, defaulting to localhost-only
    for safety."""
    return [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://localhost:8080",
        ).split(",")
        if o.strip()
    ]


def _resolve_ui_root() -> str | None:
    """Locates the frontend root to serve. The committed, packaged bundle
    (`sympose/webui/`, ADR-079) is authoritative — it ships in the wheel, so
    a `pipx install git+…` serves the real dashboard. A source checkout that
    has run `npm run build` also writes there. The old `ui/dist` and the
    hand-authored `ui/` scaffold remain as fallbacks for a stale tree."""
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_root = os.path.dirname(pkg_dir)
    ui_candidates = [
        os.path.join(pkg_dir, "webui"),
        os.path.join(pkg_root, "ui", "dist"),
        os.path.join(os.getcwd(), "ui", "dist"),
        os.path.join(pkg_root, "ui"),
        os.path.join(os.getcwd(), "ui"),
    ]
    return next(
        (p for p in ui_candidates if os.path.isfile(os.path.join(p, "index.html"))),
        None,
    )


def _render_index_html(ui_root: str | None) -> str:
    if ui_root:
        with open(os.path.join(ui_root, "index.html"), "r", encoding="utf-8") as f:
            return f.read()

    _version = get_version()
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sympose // Multi-Model Persona Hub &amp; Vault Gateway</title>
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
            <h1>Multi-Model Persona Hub &amp; Vault API</h1>
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


def _mount_spa(app: FastAPI, ui_root: str) -> None:
    """Serves the rest of the frontend bundle (hashed assets, sympose.svg,
    etc.) from `ui_root`, registered last so it never shadows an API route
    (the explicit "/" handler still owns the index document). Unknown
    non-API paths fall back to index.html so the client-side router
    (react-router) can resolve deep links like /components on a hard
    refresh."""
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


def create_app(engine: Any, workspace_dir: str | None = None) -> FastAPI:
    """Factory creating the FastAPI application bound to a PersonaEngine instance.
    Every route (including `/`, `/docs`, and the vault/config API) sits behind the
    ADR-064.1 password guard — call `ensure_dashboard_password()` before this so
    `DASHBOARD_PASSWORD` is set in the environment first. `workspace_dir` locates
    per-workspace runtime state (the Slack heartbeat); it defaults to the same
    resolution the CLI uses."""
    workspace_dir = workspace_dir or resolve_workspace_dir()
    app = FastAPI(
        title="Sympose Multi-Model Persona Hub API",
        version=get_version(),
        description="FastAPI REST API & Standalone Vault Gateway for Sympose",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # S1: the password guard is ASGI middleware, not a FastAPI route
    # dependency — a route dependency can't reach the static-asset mount
    # registered near the bottom of this function (a Starlette `Mount`
    # never goes through FastAPI's dependency-injection tree). Added
    # *before* CORSMiddleware below so CORS ends up outermost (Starlette
    # runs the most-recently-added middleware first) and can answer a
    # cross-origin preflight OPTIONS request directly — browsers send those
    # with no credentials at all, so if auth ran first every preflight
    # would 401 and cross-origin requests would never work.
    app.add_middleware(DashboardAuthMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_system_routes(app, engine, workspace_dir)
    _register_vault_read_routes(app, engine)
    _register_vault_write_routes(app, engine)
    _register_vault_trash_routes(app, engine)
    register_chat_routes(app, engine)

    ui_root = _resolve_ui_root()
    if ui_root:
        log.info("[server] dashboard frontend: %s", ui_root)
    else:
        log.warning(
            "[server] no UI bundle found (looked under %s and CWD) — serving the "
            "API-only placeholder at `/`. Build it with `cd ui && npm run build`.",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _render_index_html(ui_root)

    if ui_root:
        _mount_spa(app, ui_root)

    return app


def run_server(
    engine: Any,
    workspace_dir: str,
    host: str = "127.0.0.1",
    port: int = 8000,
    tls: bool = True,
) -> None:
    """Launches the Uvicorn ASGI server hosting the Sympose Dashboard API.
    Generates/loads the ADR-064.1 dashboard password and, unless `tls=False` or
    `cryptography` isn't installed, the ADR-064.2 self-signed certificate,
    before the app (and its global auth dependency) is constructed."""
    import uvicorn

    from sympose.auth import DASHBOARD_USER, ensure_dashboard_password

    password = ensure_dashboard_password(workspace_dir)
    app = create_app(engine, workspace_dir=workspace_dir)

    ssl_kwargs: dict[str, Any] = {}
    if tls:
        from sympose.tls import ensure_self_signed_cert

        cert_pair = ensure_self_signed_cert(workspace_dir)
        if cert_pair:
            ssl_kwargs = {"ssl_certfile": cert_pair[0], "ssl_keyfile": cert_pair[1]}

    scheme = "https" if ssl_kwargs else "http"
    print(f"\nSympose Dashboard running at: {scheme}://{host}:{port}", flush=True)
    print(
        f"Login — user: {DASHBOARD_USER}  password: {password}  (see workspace .env)\n",
        flush=True,
    )
    uvicorn.run(app, host=host, port=port, log_level="info", **ssl_kwargs)
