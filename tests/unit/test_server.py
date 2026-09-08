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
