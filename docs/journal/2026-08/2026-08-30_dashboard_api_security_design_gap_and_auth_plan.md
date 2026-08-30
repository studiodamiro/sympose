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

## 2. Decision (ADR-064) — Proposed

We propose closing this gap with a design that preserves Sympose's standing **Zero-Maintenance Mandate** ([ADR-020](../../../docs/journal/2026-08/2026-08-25_automated_memory_compactor.md)) and pipx-installable, self-resolving-dependency model ([ADR-045](../../../docs/journal/2026-08/2026-08-29_sovereign_packaging_and_cli_design_system.md)): no step should ever require the user to manually install an external system tool.

### ADR-064.1: Shared-Secret Password Guard with Long-Lived Session Cookie
* A single operator-set secret (`DASHBOARD_PASSWORD` env var) gates every dashboard/API route via a FastAPI dependency.
* First visit per browser prompts once; on success, the server issues a long-lived signed session cookie so subsequent visits from that browser (including other devices on the LAN once they've completed the same one-time step) are frictionless.
* An unauthenticated request receives a `401` before any handler logic runs — no vault content, config, or persona data is ever computed for an unrecognized caller.

### ADR-064.2: Zero-Dependency TLS via In-Process Self-Signed Certificate
* At first server boot, Sympose generates its own self-signed certificate directly in Python using the `cryptography` package — a normal `pip`/`pipx` dependency, resolved automatically like every other requirement in [`pyproject.toml`](../../../pyproject.toml). No external binary, no separate install step, no OS trust-store mutation.
* This encrypts the password and session cookie in transit, closing the plaintext-sniffing gap that a bare password alone leaves open on a shared or untrusted network segment.
* **Accepted trade-off:** because the certificate is self-signed rather than backed by a locally-trusted CA, each browser shows a one-time "not secure, proceed anyway" warning per device on first connection. This is judged an acceptable cost for a zero-manual-step guarantee, and matches the default posture of comparable self-hosted personal tools (Home Assistant, Sonarr/Radarr) out of the box.

### ADR-064.3: Alternatives Considered & Rejected (for now)
* **`mkcert`-issued locally-trusted certificate:** Eliminates the browser warning entirely, but requires either a manual `brew install mkcert` (violates the zero-manual-step goal outright) or Sympose auto-downloading and running an external binary — which still requires at least one explicit OS keychain/admin consent prompt to install a trusted root CA, a security boundary that cannot and should not be bypassed silently. Deferred; revisit if the one-time browser warning proves to be a real point of user friction.
* **VPN overlay (e.g. Tailscale):** Would provide real, warning-free HTTPS certificates and additionally restrict reachability to an explicit private device list rather than the whole LAN — the strongest option, and the right one if remote (outside-LAN) dashboard access is ever wanted. Rejected for the current scope as disproportionate infrastructure for a single-user LAN dashboard, and it is an adopted-service dependency rather than a self-resolving one.

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
