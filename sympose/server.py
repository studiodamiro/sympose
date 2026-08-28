"""
FastAPI Server & Dashboard API Gateway for Sympose.
"""

import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sympose.vault import VaultManager
from sympose.config import config_manager


def create_app(engine: Any) -> FastAPI:
    """Factory creating the FastAPI application bound to a PersonaEngine instance."""
    app = FastAPI(
        title="Sympose Multi-Model Agent Hub API",
        version="0.2.7",
        description="FastAPI REST API & Standalone Vault Gateway for Sympose",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health_check() -> Dict[str, Any]:
        return {
            "status": "healthy",
            "version": "0.2.7",
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

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        dist_index = os.path.join(os.getcwd(), "ui", "dist", "index.html")
        if os.path.exists(dist_index):
            with open(dist_index, "r", encoding="utf-8") as f:
                return f.read()

        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8"><title>Sympose Dashboard & Vault Gateway</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0B0F17; color: #E2E8F0; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }
                .card { background: #111827; border: 1px solid #1F2937; border-radius: 16px; max-width: 600px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
                h1 { color: #8B5CF6; font-size: 24px; margin-top: 0; }
                p { line-height: 1.6; color: #94A3B8; }
                .badge { background: #1E1B4B; color: #A78BFA; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 600; display: inline-block; margin-bottom: 16px; }
                a { color: #38BDF8; text-decoration: none; font-weight: 500; }
                a:hover { text-decoration: underline; }
                ul { list-style: none; padding: 0; }
                li { padding: 10px 0; border-bottom: 1px solid #1F2937; }
                code { background: #1E293B; padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #F1F5F9; }
            </style>
        </head>
        <body>
            <div class="card">
                <span class="badge">API Gateway Active &bull; < 0.8s SLA</span>
                <h1>🏛️ Sympose Hub & Vault API</h1>
                <p>The local API server and Inverted Index Engine are live on <code>localhost:8000</code>.</p>
                <ul>
                    <li>📖 <b>Interactive API Docs:</b> <a href="/docs">/docs (Swagger UI)</a></li>
                    <li>🏥 <b>Health Status:</b> <a href="/api/health">/api/health</a></li>
                    <li>🎭 <b>Active Personas:</b> <a href="/api/personas">/api/personas</a></li>
                    <li>⚙️ <b>Live Configuration:</b> <a href="/api/config">/api/config</a></li>
                </ul>
            </div>
        </body>
        </html>
        """

    return app


def run_server(engine: Any, host: str = "0.0.0.0", port: int = 8000) -> None:
    """Launches the Uvicorn ASGI server hosting the Sympose Dashboard API."""
    import uvicorn
    app = create_app(engine)
    print(f"\n🚀 Sympose Dashboard & Vault Gateway starting on http://{host}:{port}")
    print(f"📖 Swagger API Documentation available at: http://localhost:{port}/docs\n")
    uvicorn.run(app, host=host, port=port, log_level="info")
