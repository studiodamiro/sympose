# Security Policy

## Threat model

Sympose is a **local-first, single-user** personal AI hub. It runs on your
own machine, reads and writes your own Obsidian vault, and (optionally)
exposes a dashboard on your own LAN and a Slack Socket Mode connection using
your own tokens. The primary threat model is "a model mistake or a
prompt-injected note causes an unintended local action" — not a remote
attacker on the open internet. That shapes what's in scope below.

Relevant existing hardening, if you're looking for how a specific surface is
handled before filing a report:

- **Dashboard auth & transport** — every route requires a password
  (auto-generated into your workspace `.env` on first boot) and is served
  over a self-signed HTTPS certificate by default. See
  [ADR-064](docs/journal/2026-08/2026-08-30_adr-064-dashboard-api-auth-plan.md).
- **Worker shell execution** — `run_command` is gated by an argv[0]
  allowlist (read/inspect commands only by default, configurable via
  `worker.shell_allowlist`) and runs with a scrubbed environment so provider
  API keys and other credentials never reach a shelled-out command. See
  [ADR-073](docs/journal/2026-09/2026-09-04_adr-073-worker-native-shell-allowlisting.md).
- **Vault sandboxing** — all file reads/writes are constrained to a
  persona's allowed vault folders via `is_safe_path`, which resolves
  symlinks before comparing paths. See
  [ADR-002](docs/journal/2026-08/2026-08-24_adr-002-master-vault-domain-sandboxing.md).

## Supported versions

Sympose does not yet maintain multiple release branches. Security fixes land
on `main`; please run the latest version before filing a report.

## Reporting a vulnerability

**Please do not open a public GitHub issue for a security vulnerability.**

Use GitHub's private reporting flow instead: go to the
[**Security** tab](https://github.com/studiodamiro/sympose/security) →
**Report a vulnerability**. This opens a private draft advisory visible only
to you and the maintainer, so the details don't become public (or
discoverable by a scanner) before a fix ships.

Include what you'd normally include in a report: the affected file/function,
a reproduction case, and the impact you think it has (what an attacker gains,
and under what precondition — e.g. "requires the dashboard exposed beyond
localhost," "requires a malicious note already inside the vault").

There's no bug bounty — this is a personal open-source project — but real
reports are read and acted on, and you'll be credited in the fix's commit
and changelog unless you ask not to be.

## Out of scope

- Vulnerabilities that require the reporter to already have full local
  access to the machine Sympose is running on (the local-first threat model
  assumes the machine itself is trusted).
- Findings that only apply when `SYMPOSE_DASHBOARD_HOST=0.0.0.0` or
  `SYMPOSE_DASHBOARD_TLS=0` have been set explicitly, contrary to the
  documented secure-by-default configuration — unless the finding is that
  the explicit-opt-in itself is bypassable.
