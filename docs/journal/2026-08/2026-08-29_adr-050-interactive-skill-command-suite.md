---
title: "ADR-050 — Interactive Skill Command Suite (/skill & /skills) with Tab Auto-Completion"
created: 2026-08-29
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-050 — Interactive Skill Command Suite (`/skill` & `/skills`) with Tab Auto-Completion

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

`/skills` was a read-only viewer. Equipping or removing a skill meant opening
`~/.sympose/profiles/<handle>.yaml` in an external editor.

## Decision

1. **Profile manifest skill mutation.** `ProfileManager.update_persona_skills(handle, skill_name, action)`
   safely edits `skills:` in the YAML, writes to disk, and triggers
   `reload_profiles()`.
2. **Interactive interceptor (`sympose/commands.py`).** `/skills` (or
   `/skill list`) shows all playbooks and which agents have them equipped;
   `/skill add <name> [@handle]` (aliases `mount`, `install`);
   `/skill remove <name> [@handle]` (aliases `unmount`, `uninstall`, `rm`);
   `/skill show <name>` (aliases `view`, `info`).
3. **Context-aware multi-argument tab completion (`sympose/completer.py`).**
   `/skill ` → subcommands + skill names; `/skill add ` → skill names;
   `/skill add git_workflow ` → persona handles.

## Consequences

**Positive**

- Skills are mounted / unmounted live from the CLI, with hot reload.
- Discoverable via tab completion at every argument position.

**Negative / costs**

- Programmatic YAML mutation must preserve formatting / comments carefully.

## Alternatives rejected

- **Keeping `/skills` read-only and editing YAML by hand.** Rejected: friction
  for a routine operation; no hot reload.
