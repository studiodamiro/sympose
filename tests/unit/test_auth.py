"""
Unit tests for sympose.auth — the ADR-064.1 dashboard password guard.
"""

import os
import pytest
from fastapi.testclient import TestClient

from sympose.server import create_app
from sympose.auth import DASHBOARD_USER


class _FakeConfig:
    data = {"runtime": {"default_persona": "samantha"}}

    def get(self, key, default=None):
        return default


class _FakePM:
    profiles = {"samantha": {"name": "Samantha"}}


class _FakeEngine:
    pm = _FakePM()
    config = _FakeConfig()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test-secret-pw")
    app = create_app(_FakeEngine())
    return TestClient(app)


class TestDashboardAuth:
    def test_no_credentials_returns_401(self, client):
        resp = client.get("/health")
        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate", "").lower().startswith("basic")

    def test_wrong_password_returns_401(self, client):
        resp = client.get("/health", auth=(DASHBOARD_USER, "wrong-password"))
        assert resp.status_code == 401

    def test_wrong_username_returns_401(self, client):
        resp = client.get("/health", auth=("someone-else", "test-secret-pw"))
        assert resp.status_code == 401

    def test_correct_credentials_succeed(self, client):
        resp = client.get("/health", auth=(DASHBOARD_USER, "test-secret-pw"))
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_api_routes_also_gated(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 401
        resp_ok = client.get("/api/config", auth=(DASHBOARD_USER, "test-secret-pw"))
        assert resp_ok.status_code == 200

    def test_static_asset_mount_is_also_gated(self, client):
        """S1: the dashboard's static bundle is served via `app.mount()`,
        a Starlette `Mount` that never goes through FastAPI's per-route
        `Depends()` - only ASGI middleware (`DashboardAuthMiddleware`) can
        reach it. This hits a path with no matching FastAPI route at all
        (falls through to the mount's SPA fallback, same as any deep-linked
        frontend route or a plain asset file) to prove the mount itself is
        gated, not just the routes FastAPI knows about."""
        resp = client.get("/some-deep-frontend-route")
        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate", "").lower().startswith("basic")

        resp_ok = client.get(
            "/some-deep-frontend-route", auth=(DASHBOARD_USER, "test-secret-pw")
        )
        assert resp_ok.status_code == 200
        # Fell through to the mount's SPA fallback (index.html), not a 401
        # page or a real 404 - confirms the request actually reached the
        # mount post-auth rather than being blocked by something else.
        assert "<html" in resp_ok.text.lower()

    def test_cors_preflight_is_not_blocked_by_the_auth_middleware(self, client):
        """A browser's CORS preflight OPTIONS request never carries
        credentials - DashboardAuthMiddleware must be added *before*
        CORSMiddleware in server.py so CORS ends up outermost and answers
        the preflight directly, ahead of the auth check. Getting that
        ordering backwards would 401 every preflight and silently break
        every cross-origin request the dashboard makes."""
        resp = client.options(
            "/api/config",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
