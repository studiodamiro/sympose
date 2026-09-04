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
