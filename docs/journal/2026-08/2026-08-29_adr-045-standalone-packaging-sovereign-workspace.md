---
title: "ADR-045 — Modern Standalone Python Packaging (pyproject.toml) & Sovereign User Workspace"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-045 — Modern Standalone Python Packaging (`pyproject.toml`) & Sovereign User Workspace (`~/.sympose/`)

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Sympose required `git clone`, `python -m venv`, `source venv/bin/activate`,
`pip install -r requirements.txt`. Non-technical users could not install or run
it.

## Decision

1. **PEP 517/621 packaging.** `pyproject.toml` + `MANIFEST.in`; entry point
   `sympose = "app:main"`.
2. **Global workspace resolver (`sympose.bootstrap.resolve_workspace_dir`).**
   `./profiles/` or `./config.yaml` present → Local Dev Mode; otherwise → Global
   Sovereign Mode (`~/.sympose/`).
3. **Distribution mandate.** `pipx install git+https://…/sympose.git` /
   `pipx upgrade sympose`.

## Consequences

**Positive**

- One-command install / upgrade across macOS, Linux, Windows.
- User data, memories, and personas persist in `~/.sympose/` across upgrades.

**Negative / costs**

- Dual-mode resolution is a branch every path-resolving call must respect.

## Alternatives rejected

- **Keeping the manual `git clone` + venv + `pip install` flow.** Rejected:
  excludes non-technical users; incompatible with a "sovereign, production-grade
  CLI runtime" goal.
