---
title: "ADR-075 — Persona Soul Content in CREATE_PERSONA"
created: 2026-09-05
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - action-protocol
  - onboarding
---

# ADR-075 — Persona Soul Content in CREATE_PERSONA

- **Status:** Accepted — implemented 2026-09-05.
- **Date:** 2026-09-05
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

damiro's actual persona-creation habit is to pattern a new agent on a
well-known real or fictional figure — his own words: "she has a reference on
what kind of person she's creating," citing Grace herself (patterned on
Admiral Grace Hopper) as the example. Auditing `[CREATE_PERSONA]`
end-to-end (`sympose/actions.py`
[actions.py:245-279](../../../sympose/actions.py#L245-L279)) surfaced why
that technique can silently fail to actually land:

`[CREATE_PERSONA]`'s handler writes **only the YAML manifest** to
`profiles/<handle>.yaml`, then calls `profile_manager.reload_profiles()`.
`ProfileManager.reload_profiles()`
([profiles.py:161](../../../sympose/profiles.py#L161)) calls
`bootstrap_missing_artifacts()` for every loaded profile, which — seeing
`<handle>_soul.md` doesn't exist yet — writes this, once, permanently, on
the spot:

```
f"# {name}: Core Directives\n\nYou are **{name}**, the {title} in Sympose.\n"
```

One sentence. So the moment a user asks Samantha to "model this on Admiral
Grace Hopper," she can pick a good name and title, but the actual richness —
values, communication style, domain instincts, the entire point of the
reference — has no field to go in. It's discarded by the runtime before it's
ever written anywhere, replaced by a near-empty placeholder that then exists
on disk and won't regenerate. This isn't a prompt-wording problem; the action
tag has no carrier for soul content at all.

## Decision

- **ADR-075.1 — `soul_content` field in the `[CREATE_PERSONA]` manifest.**
  If the YAML payload includes a `soul_content` key, `actions.py` pops it out
  and writes it directly to `profiles/<handle>_soul.md`; the remaining
  manifest (without `soul_content`) is what gets saved as
  `profiles/<handle>.yaml`. One tag emission, same completion, zero added
  round-trips — consistent with the round-trip-frugal fire-and-forget
  dispatch model ADR-071 settled on.
- **ADR-075.2 — Raise the no-`soul_content` fallback floor.**
  `bootstrap_missing_artifacts`'s generic soul template
  ([profiles.py:91-99](../../../sympose/profiles.py#L91-L99)) goes from one
  sentence to a short scaffold (first-principles framing, proactive memory
  checkpointing, the same anti-hallucination boundary every other soul file
  carries). Still generic — it can't know what "Grace Hopper" or "Dieter
  Rams" means — but it's a floor, not a discard, for the path where a
  manifest is hand-dropped without a soul (`creating-agents.md`'s "Quick
  Genesis" 4-line YAML case).
- **ADR-075.3 — Instruct the model to actually use it.**
  `skills/sympose_mastery/SKILL.md`'s persona-creation flow gains an explicit
  step: when the user names a reference figure, write 3-6 sentences of real
  grounding — specific values/style/instincts, not adjectives — into
  `soul_content`, with a worked example. `prompts/workspace_rules.md` and its
  `sympose/bootstrap.py` fresh-workspace counterpart both document the field
  in the `[CREATE_PERSONA]` action line itself, so every persona (not just
  Samantha) knows to use it, kept in sync as the dual-template pattern
  established in ADR-074 already requires.

## Consequences

**Positive**

- The persona-creation technique damiro already relies on now actually
  works as intended — a described reference figure produces a soul grounded
  in that figure, not just a borrowed name.
- Hand-authored manifests (the "Quick Genesis" doc path) get a better
  floor even without a `soul_content` field.

**Negative / costs**

- One more field for the model to remember to populate; mitigated by making
  it explicit in the skill playbook and the base action-tag documentation
  every persona's system prompt already carries.
- `soul_content` quality is only as good as what the model writes in one
  shot — no verification pass. Acceptable: soul files were always meant to
  be edited by hand afterward if the result isn't right (same as any
  auto-bootstrapped file today).

## Alternatives rejected

- **New triple-pipe tag syntax** (`[CREATE_PERSONA: handle | yaml |||
  soul_markdown]`). Rejected in favor of a YAML field — no new delimiter
  syntax for the model to learn, and `soul_content` reads naturally as "one
  more field in the manifest" rather than a special case of the tag grammar.
- **A `[WRITE_NOTE]`-style second tag** for the soul file. Rejected —
  `WRITE_NOTE` is vault-scoped by design (`profiles/` isn't a vault folder,
  intentionally, so a persona can't accidentally rewrite another persona's
  soul via a vault-write path); reusing it would blur that boundary for one
  narrow case.
