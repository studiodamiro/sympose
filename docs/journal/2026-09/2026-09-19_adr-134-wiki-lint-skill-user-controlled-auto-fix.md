---
title: "ADR-134 — wiki_lint Skill, With User-Controlled Auto-Fix"
created: 2026-09-19
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-134 — wiki_lint Skill, With User-Controlled Auto-Fix

- **Status:** Implemented.
- **Date:** 2026-09-19
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

The last of Karpathy's three operations: lint — a health check across the
wiki for contradictions, stale claims, and orphan pages. damiro's own
answer to the earlier open question ("should lint auto-fix or only
report?") was explicit: **"it should be knobed, it should be users
discretion if he allows/trust his agent."** That's a persona-scoped
setting, not a global one — trust is a property of a specific persona a
user has configured, not a blanket policy.

Implementing that knob surfaced a real gap: **skills are static markdown,
injected verbatim regardless of persona settings — there is no per-persona
templating.** A skill's own playbook text has no way to know, at the
model's own read-time, whether *this* persona's `lint_auto_fix` is on or
off. `build_system_prompt` had no existing mechanism to surface an
arbitrary persona-scoped setting into the prompt at all (confirmed by
searching for it before assuming otherwise).

## Decision

- **`sympose/config_settings_persona.py`**: new persona-scoped
  `lint_auto_fix` (bool, default `False`) — the user-trusted opt-in
  damiro specified.
- **`sympose/profiles.py:build_system_prompt`**: a small, targeted
  addition — when a persona's `skills` list includes `wiki_lint`, one
  extra block is appended, mirroring the exact style the existing
  `share_memory`/`sharing_desc` conditional already uses (computed early,
  branched on to build a short description): a `### Wiki Lint Mode:`
  section stating plainly whether *this* persona, right now, "must stay
  report-only" or "may also directly edit flagged pages," reading
  straight from `profile.get("lint_auto_fix", False)`. Absent entirely
  for any persona without the `wiki_lint` skill active, so this costs
  nothing for personas that don't use it. This is the actual mechanism
  that makes the knob real — without it, `lint_auto_fix` would be a
  setting with no way to reach the model that's supposed to obey it.
- **`sympose/wiki_lint_support.py`** (29 lines): `wiki_pages`/
  `orphan_pages` — pure functions over the manifest `VaultManager.
  get_manifest()` already persists (ADR-078), scoped to `wiki.root`, no
  new indexing.
- **`skills/wiki_lint/SKILL.md`**: `minimum_capability_tier: standard`,
  a playbook that reads its own `Wiki Lint Mode` block rather than
  guessing, asks a `vault_read` sub-agent for the orphan list instead of
  reconstructing the link graph by eye, always logs every finding to
  `log.md` regardless of mode, and only edits a flagged page directly
  when its mode block says auto-fix is on — still confined to `wiki.root`
  either way (the mode never widens the sandbox, only what's allowed
  inside it).
- 3 new tests (`tests/unit/test_profiles.py::TestWikiLintModePromptInjection`)
  confirming the block is absent without the skill active, says
  report-only by default, and says auto-fix when the setting is true; 8
  new tests for `wiki_lint_support.py`'s orphan detection.

## Consequences

**Positive**
- The knob is now actually enforceable at the prompt level, not a config
  value with nothing reading it — the gap was caught and closed within
  this same ADR rather than shipping a decorative setting.
- The fix follows an existing, already-reviewed pattern
  (`share_memory`/`sharing_desc`) instead of inventing a new "surface
  arbitrary persona settings" mechanism — the smallest change that
  actually closes the gap.
- Orphan detection reuses the existing manifest graph — no parallel index
  to keep in sync.

**Negative / costs**
- This is still prompt-level trust, not a hard code-enforced gate — a
  sufficiently determined or confused model could ignore its own stated
  mode (the same category of risk every other prompt-level convention in
  this codebase already carries, e.g. the pre-ADR-something Daily/ folder
  guard that was prompt-only until a real violation was observed live).
  No violation has been observed here yet; if one is, the sandbox
  guarantee (ADR-132) still holds regardless — the worst case is an
  unwanted edit *inside* `wiki.root`, never outside it.
- `profiles.py` grew by ~15 lines (already over the 200-LOC guidance,
  pre-existing debt this ADR didn't set out to fix).

## Alternatives rejected

- **Leaving `lint_auto_fix` as config-only, trusting the skill's own
  prose to "know" the setting.** Rejected once the actual mechanism was
  checked — skills have no per-persona templating, so this would have
  shipped a setting with no way to reach the model, silently
  non-functional.
- **Building a general-purpose "inject all persona settings into the
  prompt" mechanism.** Rejected as bigger than this ADR needs — one
  targeted conditional, scoped to the one skill that actually needs it,
  costs nothing for every other persona and skill.
- **Hard-coding a hook in `actions.py`'s `WRITE_NOTE`/`APPEND_NOTE`
  handlers that checks `lint_auto_fix` before allowing a write.**
  Rejected — those tags are used by many skills for many purposes; there
  is no way to know from inside a generic action handler that a
  particular write originated from a `wiki_lint` pass specifically,
  without new bookkeeping machinery well beyond this ADR's scope.
