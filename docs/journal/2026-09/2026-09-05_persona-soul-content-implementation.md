---
entry: 2026-09-05
created: 2026-09-05 03:15
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - adr
---

# Sympose Engineering Log: Persona Soul Content in CREATE_PERSONA

> **Date:** Friday, September 5, 2026
> **Topic:** A real functional gap in `[CREATE_PERSONA]` found while damiro
> described his own persona-creation habit
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Implemented, tested end-to-end, documented as ADR-075.

---

## 1. How this surfaced

Continuing the shareability thread (after
[ADR-074](./2026-09-05_adr-074-default-persona-vault-scope-and-onboarding-genesis-nudge.md)),
damiro described how he actually creates personas: pattern them on a
well-known figure so the model "has a reference on what kind of person she's
creating" — citing Grace herself, patterned on Admiral Grace Hopper, as the
example. That's a genuine prompt-engineering technique (concrete reference >
abstract adjectives), and it prompted a wider question: how effective are
this project's hardcoded prompts, and is there an actual standard for
writing them?

Tracing `[CREATE_PERSONA]` end-to-end to answer that concretely found a real
bug, not a style issue: the tag writes **only the YAML manifest**. The
`reload_profiles()` call right after it triggers
`ProfileManager.bootstrap_missing_artifacts()`, which — seeing no soul file
yet — writes a single generic sentence, permanently, before the persona is
ever used. Every persona created through natural conversation, regardless of
how richly a reference figure was described, got that one sentence. The
technique damiro relies on daily had no path to actually work.

## 2. What shipped (ADR-075)

- **`sympose/actions.py`**: `[CREATE_PERSONA]` now parses the manifest YAML,
  and if it contains a `soul_content` field, writes that directly to
  `profiles/<handle>_soul.md` and strips it from the saved `.yaml`. Falls
  back to the previous raw-write behavior if parsing fails or the field is
  absent — no persona-creation path regresses.
- **`sympose/profiles.py`**: raised `bootstrap_missing_artifacts`'s fallback
  soul from one sentence to a short scaffold (first-principles framing,
  proactive memory checkpointing, the anti-hallucination boundary every
  other soul carries) — the floor for personas created without
  `soul_content` (e.g. a hand-dropped 4-line manifest).
- **`skills/sympose_mastery/SKILL.md`**: the persona-creation flow now
  explicitly instructs writing 3-6 sentences of *specific* grounding
  ("insists on empirical replication before accepting a result" — not
  "meticulous, disciplined") into `soul_content` when a reference figure was
  named, with a worked Marie Curie example.
- **`prompts/workspace_rules.md`** and its `sympose/bootstrap.py`
  fresh-workspace counterpart both document the field on the
  `[CREATE_PERSONA]` action line itself, kept in sync per the dual-template
  pattern ADR-074 already established.
- **`docs/wiki/reference/action-tags.md`** updated to match.

## 3. Verification

- 9 new tests: `test_actions.py` (`soul_content` extracted and written to the
  soul file, stripped from the yaml, badge reflects "custom soul"; no
  `soul_content` leaves the yaml untouched and writes no soul file;
  malformed YAML still falls back to a raw write rather than losing the
  persona) and `test_profiles.py` (the raised fallback floor is a real
  scaffold not one line; an existing soul file is never overwritten; an
  explicit `soul_file` path is respected).
- A real end-to-end run against a scratch `profiles/` directory: emitted an
  actual `[CREATE_PERSONA: hopper | ...]` tag with a Grace-Hopper-grounded
  `soul_content` field through `ActionProcessor.execute_actions` directly (no
  mocks) and confirmed the resulting `hopper_soul.md` carried the real
  grounding and `hopper.yaml` carried a clean manifest with `soul_content`
  absent.

`.venv/bin/pytest` — 143/143 (137 prior + 6 new in `test_actions.py`, 3 new in
`test_profiles.py`).

## 4. Commits

Three commits on `feat/persona-soul-content` (branched off `main`; author
`damiro <hello.damiro@gmail.com>`, no AI attribution trailer):

```
b96783d feat(actions): soul_content field in CREATE_PERSONA (ADR-075)
54dee0d docs: instruct Samantha to actually use soul_content (ADR-075.3)
84d7a2f docs: ADR-075, journal the CREATE_PERSONA soul-content fix
```

## 5. Next Immediate Objective

The product-shareability thread (persona creation UX for someone who isn't
damiro) now covers: default persona vault scope, onboarding discovery, and
the actual soul-grounding mechanism. No further gaps identified in this
thread; next work is whatever damiro prioritizes next.
