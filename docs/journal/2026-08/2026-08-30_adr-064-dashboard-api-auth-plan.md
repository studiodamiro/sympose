---
title: "ADR-064 — Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan"
created: 2026-08-30
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-064 — Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan

- **Status:** Accepted — ADR-064.1 (password guard) and ADR-064.2 (self-signed
  TLS) both implemented 2026-09-04, with 064.1 built as HTTP Basic Auth rather
  than the custom signed-cookie session originally sketched. See second
  **Implementation Note** below. Extends
  [ADR-051 – ADR-053](./2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md)
  with a security design the original dashboard spec omitted; stays consistent
  with [ADR-020](./2026-08-25_adr-020-zero-maintenance-mandate.md) and
  [ADR-045](./2026-08-29_adr-045-standalone-packaging-sovereign-workspace.md)
- **Date:** 2026-08-30
- **Deciders:** damiro (Lead Architect); Claude (Sonnet 5) (Engineering Partner)

## Context

An independent codebase audit flagged that `sympose/server.py` — the FastAPI
dashboard & vault gateway — ships with **zero authentication on any route**,
including `/api/config` (full runtime config, vault paths) and `/api/vault/note`
(raw vault content by path). The server also binds `host="0.0.0.0"`, reachable
from any device on the LAN. The dashboard spec
([ADR-051–053](./2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md))
covered UI/UX and performance only; the one defensive-engineering pass
([ADR-038](./2026-08-26_adr-038-defensive-engineering-hardening-standards.md))
predates `server.py`. The already-shipped `CORSMiddleware` localhost allowlist
constrains only browser-origin JavaScript — it does nothing against `curl` or a
script, so it is not authentication. Slack access is explicitly out of scope: it
connects outbound via Socket Mode with its own tokens and never touches
`server.py`.

## Decision

Proposed, not yet implemented:

- **ADR-064.1 — Shared-secret password guard + long-lived session cookie.** A
  single `DASHBOARD_PASSWORD` env var gates every route via a FastAPI
  dependency; first visit per browser prompts once, then a signed session cookie
  makes subsequent visits frictionless; an unauthenticated request gets `401`
  before any handler logic runs.
- **ADR-064.2 — Zero-dependency TLS via in-process self-signed certificate.** At
  first boot Sympose generates its own self-signed cert in Python using
  `cryptography` (a normal `pip`/`pipx` dependency) — no external binary, no OS
  trust-store mutation. Encrypts the password and cookie in transit. Accepted
  trade-off: a one-time per-device "not secure, proceed" browser warning.

## Consequences

**Positive** (anticipated — ADR-064 is not yet implemented)

- Closes the audit's Critical Finding #5 and the auth-middleware item once
  implemented.
- Slack's independent trust boundary is unaffected.

**Negative / costs**

- No rate-limiting on the password check; the self-signed cert still shows a
  first-connection warning per device. Both are judged proportionate to a
  single-user personal-LAN threat model and flagged for revisit if the dashboard
  is ever exposed beyond a trusted LAN.
- **Not implemented** — this ADR records the design and reasoning only; the code
  pass on `sympose/server.py` / `app.py` is queued.

## Implementation Note (2026-09-04)

Neither ADR-064.1 (password guard) nor ADR-064.2 (self-signed TLS) is
implemented. As an interim mitigation pending that decision,
`run_server()`'s default changed from `host="0.0.0.0"` to `host="127.0.0.1"`,
and `app.py` reads `SYMPOSE_DASHBOARD_HOST` so LAN exposure requires an
explicit opt-in rather than being the out-of-the-box default. This closes the
"reachable from any device on the LAN with zero auth" part of the finding for
anyone running the default config; it does nothing for a user who does set
`SYMPOSE_DASHBOARD_HOST=0.0.0.0` — the auth gap the rest of this ADR describes
is unchanged for that case. Commit `86aca37` on
`chore/backend-architecture-review-and-fixes`.

## Implementation Note (2026-09-04, cont'd — Tier 4)

Both halves shipped:

- **ADR-064.1 (password guard)** — implemented as **HTTP Basic Auth**
  (`fastapi.security.HTTPBasic`, `sympose/auth.py`), not the custom signed
  session-cookie this ADR originally sketched. `DASHBOARD_PASSWORD` gates
  every route via a global FastAPI dependency (`FastAPI(dependencies=[...])`,
  so `/`, `/docs`, and every `/api/*` route are covered uniformly, not
  route-by-route); an unauthenticated or wrong-credential request gets `401`
  with a `WWW-Authenticate: Basic` challenge before any handler runs, matching
  the original goal. If `DASHBOARD_PASSWORD` isn't set on first boot, Sympose
  generates one (`secrets.token_urlsafe(18)`), persists it to the workspace
  `.env`, and logs it once — the zero-maintenance mandate (ADR-020) means the
  default experience needs no manual step, not that auth ships open. **Why
  Basic over the cookie design**: the browser caches the credential itself
  for the life of the tab, so there is no session store, no cookie signer, no
  expiry logic to write or maintain — a smaller mechanism for the same
  single-user threat model. The same kind of deliberate deviation as
  ADR-072.3's semaphore pool vs. the literal `ThreadPoolExecutor` wording.
- **ADR-064.2 (self-signed TLS)** — implemented via `sympose/tls.py` using
  `cryptography` (now a real dependency, `pyproject.toml`/`requirements.txt`),
  exactly as this ADR proposed: an in-process self-signed cert generated on
  first boot into `<workspace>/.certs/` (gitignored), no external `openssl`/
  `mkcert` binary, no OS trust-store mutation. `run_server()` wires
  `ssl_certfile`/`ssl_keyfile` into `uvicorn.run`. If `cryptography` somehow
  isn't installed, cert generation logs a warning and the dashboard falls
  back to plain HTTP rather than failing to boot. `SYMPOSE_DASHBOARD_TLS=0`
  opts out (e.g. running behind an external terminator).
- Verified end-to-end, not just unit-tested: booted the real dashboard with
  `tls=True` against a scratch workspace, confirmed `curl` without credentials
  gets `401` over `https://127.0.0.1`, and with `-u sympose:<generated pw>`
  gets `200` — the self-signed cert, the generated password, and the auth
  dependency all wired together, not just each piece in isolation. Unit tests
  in `tests/unit/test_auth.py` cover missing/wrong username/wrong password/
  correct credentials against both `/health` and `/api/config`.
- This closes the ADR's Critical Finding #5 in full: every dashboard route
  now requires the password, over HTTPS by default.

## Alternatives rejected

- **`mkcert`-issued locally-trusted certificate.** Removes the browser warning,
  but needs either a manual `brew install mkcert` (violates the zero-manual-step
  goal) or Sympose auto-running an external binary plus an OS keychain/admin
  consent prompt to install a trusted root CA. Deferred; **revisit trigger:** the
  one-time browser warning proving to be real user friction.
- **VPN overlay (e.g. Tailscale).** The strongest option — real warning-free
  HTTPS and device-list reachability — and the right choice **if** outside-LAN
  dashboard access is ever wanted (**revisit trigger**). Rejected for current
  scope as disproportionate infrastructure and an adopted-service dependency
  rather than a self-resolving one.
