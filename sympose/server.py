"""
FastAPI Server & Dashboard API Gateway for Sympose.
"""

import os
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sympose.vault import VaultManager
from sympose.config import config_manager

log = logging.getLogger(__name__)


def create_app(engine: Any) -> FastAPI:
    """Factory creating the FastAPI application bound to a PersonaEngine instance."""
    app = FastAPI(
        title="Sympose Multi-Model Agent Hub API",
        version="0.2.24",
        description="FastAPI REST API & Standalone Vault Gateway for Sympose",
        docs_url="/docs",
        redoc_url="/redoc",
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
            "version": "0.2.24",
            "active_personas": list(engine.pm.profiles.keys()),
            "default_persona": engine.config.get("runtime.default_persona", "samantha"),
        }

    @app.get("/api/personas")
    def list_personas() -> Dict[str, Any]:
        return {
            "personas": [p for p in engine.pm.profiles.values()]
        }

    @app.get("/api/config")
    def get_config() -> Dict[str, Any]:
        return {"config": engine.config.data}

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

    # Resolve the frontend root: a built Vite bundle (ui/dist) wins over the
    # hand-authored vanilla scaffold (ui/) when present. Both are optional.
    ui_candidates = [
        os.path.join(os.getcwd(), "ui", "dist"),
        os.path.join(os.getcwd(), "ui"),
    ]
    ui_root = next((p for p in ui_candidates if os.path.isfile(os.path.join(p, "index.html"))), None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        if ui_root:
            with open(os.path.join(ui_root, "index.html"), "r", encoding="utf-8") as f:
                return f.read()

        try:
            from importlib.metadata import version as pkg_version
            _version = pkg_version("sympose")
        except Exception:
            _version = "0.2.24"
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


def run_server(engine: Any, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Launches the Uvicorn ASGI server hosting the Sympose Dashboard API."""
    import uvicorn
    app = create_app(engine)
    log.info("Sympose Dashboard & Vault Gateway starting on http://%s:%s", host, port)
    log.info("Swagger API Documentation available at: http://localhost:%s/docs", port)
    uvicorn.run(app, host=host, port=port, log_level="info")
