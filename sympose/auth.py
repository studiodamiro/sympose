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

import os
import secrets
import logging
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

log = logging.getLogger(__name__)

DASHBOARD_USER = "sympose"
_security = HTTPBasic(auto_error=True)


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
            env_file, pw,
        )
    log.info("[auth] Dashboard login — user: %s  password: %s", DASHBOARD_USER, pw)
    return pw


def require_dashboard_auth(credentials: HTTPBasicCredentials = Depends(_security)) -> None:
    """FastAPI dependency gating a route behind the dashboard password.
    Constant-time comparison on both fields to avoid a username/password timing
    oracle; raises 401 with a WWW-Authenticate challenge on any mismatch."""
    expected_pw = os.getenv("DASHBOARD_PASSWORD", "")
    user_ok = secrets.compare_digest(credentials.username.encode("utf-8"), DASHBOARD_USER.encode("utf-8"))
    pass_ok = bool(expected_pw) and secrets.compare_digest(
        credentials.password.encode("utf-8"), expected_pw.encode("utf-8")
    )
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dashboard credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
