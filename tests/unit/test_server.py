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
