"""
Dashboard authentication (ADR-064.1): a shared-secret password guard.

Zero-maintenance by default (ADR-020): if DASHBOARD_PASSWORD isn't set when the
dashboard first boots, Sympose generates one, persists it to the workspace
.env, and logs it once so the operator can retrieve it later.

Implemented as HTTP Basic Auth (`fastapi.security.HTTPBasic` +
`secrets.compare_digest`) rather than the custom signed session-cookie
originally sketched in ADR-064.1 — the browser caches the credential itself
for the life of the tab, so there is no session store or cookie signer to
write or maintain, which is a smaller mechanism for the same threat model.
See ADR-064's Implementation Note for the full rationale (the same kind of
deliberate deviation as ADR-072.3's semaphore pool vs. `ThreadPoolExecutor`).
"""

import base64
import logging
import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.datastructures import Headers
from starlette.responses import Response

log = logging.getLogger(__name__)

DASHBOARD_USER = "sympose"
_security = HTTPBasic(auto_error=True)


def _check_credentials(username: str, password: str) -> bool:
    """Constant-time username+password check against `DASHBOARD_PASSWORD`.
    Shared by `require_dashboard_auth` (the FastAPI route dependency) and
    `DashboardAuthMiddleware` below (S1's ASGI-level gate), so both enforce
    the exact same comparison rather than two copies drifting apart."""
    expected_pw = os.getenv("DASHBOARD_PASSWORD", "")
    user_ok = secrets.compare_digest(
        username.encode("utf-8"), DASHBOARD_USER.encode("utf-8")
    )
    pass_ok = bool(expected_pw) and secrets.compare_digest(
        password.encode("utf-8"), expected_pw.encode("utf-8")
    )
    return user_ok and pass_ok


def ensure_dashboard_password(workspace_dir: str) -> str:
    """Returns DASHBOARD_PASSWORD from the environment, generating and persisting
    one to the workspace .env on first boot if it isn't already set."""
    pw = os.getenv("DASHBOARD_PASSWORD")
    if pw:
        return pw

    pw = secrets.token_urlsafe(18)
    os.environ["DASHBOARD_PASSWORD"] = pw
    env_file = os.path.join(workspace_dir, ".env")
    try:
        with open(env_file, "a", encoding="utf-8") as f:
            f.write(f'\nDASHBOARD_PASSWORD="{pw}"\n')
        log.info("[auth] Generated dashboard password and saved it to %s", env_file)
    except Exception:
        log.warning(
            "[auth] Generated a dashboard password but could not persist it to %s "
            "(a new one will generate next boot). Password for this session: %s",
            env_file,
            pw,
        )
    log.info("[auth] Dashboard login — user: %s  password: %s", DASHBOARD_USER, pw)
    return pw


def require_dashboard_auth(
    credentials: HTTPBasicCredentials = Depends(_security),
) -> None:
    """FastAPI dependency gating a route behind the dashboard password.
    Constant-time comparison on both fields to avoid a username/password timing
    oracle; raises 401 with a WWW-Authenticate challenge on any mismatch."""
    if not _check_credentials(credentials.username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dashboard credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


class DashboardAuthMiddleware:
    """S1: raw ASGI middleware gating *every* request, including the
    mounted static-asset SPA files that `app.mount()` serves.

    A `Starlette` `Mount` isn't a FastAPI `APIRoute` — it never goes through
    FastAPI's dependency-injection tree, so the app-level
    `dependencies=[Depends(require_dashboard_auth)]` (or a per-route one)
    can't reach it. Every asset except the exact `/` route used to be
    served with no credential check at all. ASGI middleware runs ahead of
    routing, so it covers the mount uniformly with every other route — this
    replaces the app-level `Depends()` as the one auth layer for the whole
    app, rather than sitting alongside it as a second, easy-to-forget one."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._authorized(Headers(scope=scope)):
            await self.app(scope, receive, send)
            return

        response = Response(
            "Unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )
        await response(scope, receive, send)

    @staticmethod
    def _authorized(headers: Headers) -> bool:
        auth_header = headers.get("authorization", "")
        scheme, _, encoded = auth_header.partition(" ")
        if scheme.lower() != "basic" or not encoded:
            return False
        try:
            decoded = base64.b64decode(encoded).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, sep, password = decoded.partition(":")
        if not sep:
            return False
        return _check_credentials(username, password)
