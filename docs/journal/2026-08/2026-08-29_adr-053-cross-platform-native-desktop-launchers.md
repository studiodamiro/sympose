---
title: "ADR-053 — Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-053 — Cross-Platform Native Desktop Launchers & Zero-Bloat Frameless App-Mode Wrappers

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Requiring the user to open a terminal, recall `sympose --web`, and browse to
`http://localhost:8000` is daily friction. Bundling Electron for a native icon
adds 150 MB+ download, 600 MB+ RAM, and subprocess management.

## Decision

- **Zero-bloat native launchers.** macOS: a ~60 KB `/Applications/Sympose.app`
  (Spotlight, Launchpad, Dock). Windows: a `Sympose.lnk` targeting
  `msedge.exe --app=...` (Start Menu, Taskbar, `Win+S`). Linux: a
  `~/.local/share/applications/sympose.desktop` entry.
- **Frameless "App Mode".** Launchers invoke the system browser engine in
  dedicated app mode (`--app=...` or `pywebview`), no chrome / tabs / URL bar.
- **Automated provisioning.** `sympose --install-app`, plus detection during the
  1-line install.

## Consequences

**Positive**

- One-click launch from Spotlight / Start Menu / Dock; clean frameless window;
  full cross-platform parity; < 60 KB launcher, < 165 MB total RAM.

**Negative / costs**

- Depends on a system browser engine being present (Edge on Windows,
  WebKit/Cocoa on macOS).

## Alternatives rejected

- **Bundling Electron for a native desktop app.** Rejected: 150 MB+ download,
  600 MB+ RAM, and complex subprocess management for what a frameless browser
  window already provides.
