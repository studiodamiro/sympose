---
title: "ADR-051 — Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-051 — Flat Architectural Web Dashboard, 2D/3D Knowledge Nebula & shadcn Theme Customizer Engine

- **Status:** Accepted — the security surface this spec omitted is documented and
  proposed by [ADR-064](./2026-08-30_adr-064-dashboard-api-auth-plan.md)
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Most AI web interfaces copy dark-purple neon glows and heavy blur that fatigue
the eye, reduce contrast, and offer no customization. Sympose wants a sovereign,
high-contrast, flat architectural interface with full visualizer control and both
2D and 3D knowledge exploration.

## Decision

### Accepted for the first release

- **Design philosophy.** Reject neon glow; flat matte cards, crisp 1px borders,
  Swiss / editorial typography, perfect light/dark parity.
- **Dual 2D/3D renderer.** One backend graph contract (`/api/vault/graph`) feeds
  either a 2D Canvas/SVG engine or a 3D WebGL (Three.js) orbital universe.
- **Ambient background states.** *Explore Mode* — interactive
  (`pointer-events: auto`); *Focus/Chat Mode* — ~75% dimmed ambient drift
  (`pointer-events: none`), no click interception.
- **Theme & style customizer.** The `ui.shadcn.com/create` control pattern:
  `data-style="nova|maia|sera"`, corner radius `0rem`–`0.75rem`, interchangeable
  icon libraries, curated presets (*Obsidian Matte*, *Blueprint & Paper*,
  *Nordic Spruce*, *Swiss Grid*), live color pickers.
- **Obsidian graph control parity.** Filters (Search, Tags, Existing, Orphans,
  Groups), Display (Arrows, Text fade, Node size, Link thickness), Forces
  (Center, Repel, Link force, Link distance).

### Deferred (post-v1, additive)

- Multi-agent visual cues (nodes pulse when referenced by a persona) — additive
  polish, not a v1 gate.

## Consequences

**Positive**

- Timeless, distraction-free aesthetic with WCAG contrast.
- One-click theme and light/dark switching; power-user graph control parity.

**Negative / costs**

- The spec covers UI/UX and physics only — **no access control** — the gap
  ADR-064 later raises.
- Two render engines to maintain against one graph contract.

## Alternatives rejected

- **The generic "AI app" aesthetic** — dark-purple neon glows, heavy
  glassmorphism, sluggish Electron-style shells. Rejected: visual fatigue, poor
  contrast, no customization, heavy runtime.
