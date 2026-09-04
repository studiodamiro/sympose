---
entry: 2026-08-30
created: 2026-08-30 05:15
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - security
  - dashboard
  - api-gateway
  - auth
  - adr-064
---

# Engineering Journal: Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan (ADR-064)

> **Date:** August 30, 2026
> **Lead Architect:** damiro
> **Engineering Partner:** Claude (Sonnet 5)
> **Status:** PROPOSED — PENDING IMPLEMENTATION (ADR-064)

---

## 1. Context & Problem Statement

An independent codebase audit (Antigravity IDE, `sympose_audit_report.md`, generated 2026-08-29) flagged that `sympose/server.py` — the FastAPI Dashboard & Vault Gateway — ships with **zero authentication on any route**, including `/api/config` (full runtime config, vault paths, model knobs) and `/api/vault/note` (raw vault content by path). The server also binds to `host="0.0.0.0"` by default ([`app.py:54`](../../../app.py#L54)), meaning it is reachable from any device on the local network, not only from the machine it runs on.

Re-reading the dashboard's own architectural spec — [ADR-051 – ADR-053](../../../docs/wiki/architecture/dashboard-and-vault-explorer.md) — confirmed this wasn't a deliberate trade-off: those three ADRs (2026-08-27–29) cover UI/UX (the 2D/3D Knowledge Nebula, shadcn theming, native desktop launchers) and performance (sub-5ms caching, GPU instancing) exclusively. No access-control question is raised anywhere in that spec. Compounding this, [ADR-038](../../../docs/journal/2026-08/2026-08-26_post_remediation_hardening_and_defensive_engineering_standards.md) — the one dedicated defensive-engineering hardening pass the project has had — was ratified on 2026-08-26, **before** `server.py` and its `/api/*` surface existed at all (2026-08-27–29). The one review that might have caught this landed chronologically ahead of the code it should have covered, and no equivalent pass ran again afterward.

A narrower, already-shipped mitigation exists: `allow_origins` on `CORSMiddleware` was restricted to a small localhost allowlist (Phase 1 of the audit's remediation plan, see [`server.py:28-34`](../../../sympose/server.py#L28)). This is a genuinely different control — it only constrains which **browser-origin JavaScript** may read a response, enforced by the browser. It does nothing against a direct request from `curl`, a script, or any other non-browser client, so it does not substitute for authentication.

**Explicitly out of scope:** Slack access. The Slack integration ([`sympose/slack.py`](../../../sympose/slack.py)) connects outbound via Socket Mode using its own `SLACK_BOT_TOKEN`/`SLACK_APP_TOKEN` credentials and never touches `server.py` — it is a fully independent trust boundary, gated by Slack's own workspace membership and token model. Nothing in this ADR changes how Slack access works.

---

## 2. Decision (ADR-064) - Proposed

- **[ADR-064 - Dashboard/API Gateway Security Design Gap & Zero-Dependency Auth Plan](./2026-08-30_adr-064-dashboard-api-auth-plan.md):**
  status **Proposed - pending implementation**. Proposes a `DASHBOARD_PASSWORD`
  shared-secret guard with a long-lived signed session cookie (064.1) and a
  zero-dependency in-process self-signed TLS certificate generated with
  `cryptography` (064.2), accepting a one-time per-device browser warning.
  `mkcert` (manual install / root-CA consent) and a Tailscale VPN overlay
  (disproportionate for a single-user LAN; revisit if outside-LAN access is
  wanted) were considered and deferred. Slack is out of scope - it authenticates
  independently via Socket Mode tokens. No code has landed.

---

## 3. Consequences (Anticipated)

* **Security**: Closes the audit's Critical Finding #5 (`/api/config` — no auth) and Phase 4 Item #20 (auth middleware on the FastAPI server) once implemented.
* **Scope boundary preserved**: Slack access is unaffected — it was never routed through `server.py` and has its own credential model.
* **Residual accepted risk**: No rate-limiting/throttling on the password check, and the self-signed certificate does not eliminate the first-connection browser warning per device. Both are judged proportionate to a single-user, personal-LAN threat model and should be revisited if Sympose's dashboard is ever intended to be reachable from outside a trusted LAN.
* **No implementation has landed yet.** This entry documents the design and the reasoning behind it in response to the audit; ADR-064.1 and ADR-064.2 are queued as the next engineering pass on `sympose/server.py` and `app.py`.

---

## 4. Cross-References
* **Audit source**: Antigravity IDE `sympose_audit_report.md` (generated 2026-08-29), Critical Finding #5 and Phase 4 Item #20.
* **[ADR-038](../../../docs/journal/2026-08/2026-08-26_post_remediation_hardening_and_defensive_engineering_standards.md)**: Prior defensive-engineering hardening pass, predates this API surface.
* **[ADR-051 – ADR-053](../../../docs/wiki/architecture/dashboard-and-vault-explorer.md)**: Dashboard architecture spec this ADR extends with a security design the original spec omitted.
* **[ADR-045](../../../docs/journal/2026-08/2026-08-29_sovereign_packaging_and_cli_design_system.md)**: Sovereign, pipx-installable packaging standard this design stays consistent with.
