---
title: "ADR-076 — Skill Playbook Single-Source & Compression"
created: 2026-09-07
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - skills
  - prompt-budget
---

# ADR-076 — Skill Playbook Single-Source & Compression

- **Status:** Accepted — implemented 2026-09-07.
- **Date:** 2026-09-07
- **Deciders:** damiro (Lead Architect); Claude (Sonnet 5) (Engineering Partner)
- Extends the skills system introduced in
  [ADR-018](../2026-08/2026-08-25_adr-018-multi-model-concierge-integration.md)
  and the round-trip-frugal, hot-path prompt-budget discipline of
  [ADR-070](./2026-09-04_adr-070-hot-path-retrieval-budget-trigger-discipline.md).

## Context

Two problems surfaced while debugging why a local-model persona (Anaïs, on a
14B Ollama model) took ~60 s to first token on every Slack turn.

**1. The skill directory had drifted into two out-of-sync copies.**
`SkillManager` ([skills.py:67-70](../../../sympose/skills.py#L67-L70)) scans
`<workspace>/skills/` and `<package>/sympose/builtin_skills/`. The repo also
carried a top-level `skills/` — tracked, referenced throughout the wiki, and the
place edits actually landed — but **not** one of the two directories the loader
reads (unless the CLI is run from the repo checkout). `sympose/builtin_skills/`
(what ships in the wheel, and what seeds `~/.sympose/skills/`) had fallen behind:

- `subagent_spawn` was **absent entirely** — so every persona that declared it
  (Samantha ships with it) silently received no `[SPAWN_WORKER]` playbook, with
  no error or log line.
- `sympose_mastery` predated [ADR-075](./2026-09-05_adr-075-persona-soul-content-in-create-persona.md)
  (no `soul_content` guidance); `vault_recall` predated its Context-Adaptive
  output modes.

**2. The playbooks re-stated the base rules, per skill, per turn.**
`format_skills_for_prompt` ([skills.py:168-185](../../../sympose/skills.py#L168-L185))
pastes each listed skill's **entire** Markdown body into the system prompt
verbatim, every turn, with no gating. The Universal Workspace Rules
(`prompts/workspace_rules.md`) already carry action-tag syntax, the
anti-hallucination and anti-helplessness axioms, mandatory-tag-emission, and
the no-roleplay rule — yet each `SKILL.md` repeated its own copy, plus
decorative banners and three-to-four fully worked examples. The five-skill
"baseline kit" came to ~4,600 tokens of system prompt on a message as trivial
as "hey, you here?". A separate finding — a per-minute `{{current_datetime}}`
token 6 % into the prompt busting the local model's prompt-cache prefix — is
recorded in the 2026-09-07 engineering log; this ADR is about the payload size
itself.

`prompts/workspace_rules.md` had a third instance of the same class of bug:
`build_system_prompt` reads it at runtime, but `prompts/` is not shipped in the
wheel, so a `pip`/`pipx` install falls back to `bootstrap.DEFAULT_RULES_MD` — a
string that had drifted several rules behind the file. Fresh installs ran a
weaker ruleset.

## Decision

- **ADR-076.1 — `sympose/builtin_skills/` is the single source of truth for
  shipped skill playbooks.** The top-level `skills/` directory is deleted;
  `/skills/` is git-ignored (it is only re-seeded there at runtime when the CLI
  runs from the repo). The dead `recursive-include skills *.md` line is removed
  from `MANIFEST.in`; six wiki pages are repointed at `sympose/builtin_skills/`.
  `subagent_spawn` is added; `sympose_mastery` and `vault_recall` are brought
  current.

- **ADR-076.2 — Playbooks carry skill-specific nuance only; the base rules carry
  everything shared.** Two rules are added to `prompts/workspace_rules.md`
  (no self-narration; no payload-dumping in chat), covering the last cross-skill
  duplications. `vault_write`, `vault_recall`, `slack_interaction`, `web_search`,
  `strategic_analysis`, `subagent_spawn`, and `sympose_mastery` are rewritten to
  drop the re-stated axioms, decorative structure, and redundant examples
  (one per action tag). `vault_write`'s routing table is de-personalised to
  folder *types*. Every action tag remains referenced; the 157-test suite passes.

  | | before | after |
  | --- | --- | --- |
  | baseline five-skill payload | ~4,613 tok | ~2,275 tok |
  | `sympose_mastery` (Samantha) | ~2,568 tok | ~1,123 tok |
  | Anaïs full system prompt | ~5,471 tok | ~2,745 tok |
  | Anaïs first-token latency (14B local, warm) | ~60 s | ~39 s |

- **ADR-076.3 — `bootstrap.DEFAULT_RULES_MD` is kept byte-for-byte identical to
  `prompts/workspace_rules.md`,** guarded by
  `tests/unit/test_bootstrap.py::test_default_rules_md_matches_workspace_rules_file`.
  It is explicitly the wheel-install fallback for the un-shipped `prompts/` file,
  not an independent ruleset.

## Consequences

- One place to edit a skill; the loader, the wheel, and the workspace seed all
  read the same bytes.
- Every persona turn — local **and** cloud — is ~2,300 tokens lighter, lowering
  both first-token latency and per-call cost.
- `prompts/` is still not shipped in the wheel; the `DEFAULT_RULES_MD` mirror +
  its guard test make that safe, but consolidating `prompts/` into the package
  the way `skills/` was consolidated remains open (deferred, low urgency).
- Skill bodies are still injected unconditionally. Keyword-gated injection (only
  loading a skill's full body when the turn plausibly needs it) is a separate,
  optional follow-up — it trades a reliability risk for turn-one latency and was
  not taken here.

## Implementation Note (2026-09-07, cont'd — second compression pass)

Keyword-gated injection was surveyed (five variants: keyword + sticky, keyword +
non-sticky, model-driven progressive disclosure, prior-action stickiness,
per-persona opt-in) and **dropped entirely**. Progressive disclosure — the
industry-standard pattern (Anthropic Skills, the MCP tool-search direction) —
costs a round-trip on the turn a skill is first needed, which is trivial on a
cloud model but ~40 s on a local 14B, i.e. exactly the round-trip-frugality
constraint Sympose is built around. The other variants each add trigger curation
plus per-thread state for a shrinking marginal win (Pass 1 already halved the
baseline; the prompt-cache fix already made turns 2+ instant). Prior-action
stickiness remains the fallback to revisit if local first-turn latency stays a
real irritant.

Instead, ADR-076.2's "nuance only" treatment was extended:

- `prompts/workspace_rules.md` itself (always-on, every persona, every turn):
  the overlapping "emit the literal tag / runtime executes atomically / never
  fake it" rules merged into one Autonomic Action Tags preamble + one Conduct
  rule; every directive tightened to a line. ~1,400 → ~1,080 tokens, every
  distinct rule preserved, `DEFAULT_RULES_MD` mirror + guard test updated.
- The mid-size playbooks untouched in the first pass: `code_review` 488 → 284,
  `discussion_moderation` 560 → 305, `system_architecture` 402 → 249,
  `git_workflow` 466 → 236.
- `vault_write` 827 → 686 and `vault_recall` 564 → 459 (payload-hygiene folded
  into the new Conduct rule).

Baseline five-skill payload is now ~2,028 tokens (from ~2,275 after the first
pass, ~4,613 before). All action tags retained; the 157-test suite passes;
`[DAILY_NOTE]` verified live.

## Implementation Note (2026-09-07, cont'd — `prompts/` shipped in-package)

The "mirror + guard test" resolution above (`DEFAULT_RULES_MD` kept
byte-for-byte in sync with `prompts/workspace_rules.md` by a test) was replaced
outright, applying ADR-076's own single-source principle to the declarative
prompt templates.

The top-level `prompts/` directory was never in `[tool.setuptools.package-data]`
and `MANIFEST.in` only reached the sdist — so every wheel / `pipx` install ran
on the terse inline fallback strings in `bootstrap`, `memory` and `workers`, not
the real templates. `workspace_rules.md` merely had a louder symptom (the guard
test) than `worker_system.md` / `memory_extraction.md` / `session_summary.md`,
which silently degraded.

- All four templates moved to `sympose/prompts/*.md` and added to
  `package-data` (`prompts/*.md`), mirroring `builtin_skills/`. Verified present
  in a built wheel.
- New leaf module `sympose/prompt_assets.py` — `load_prompt(name, fallback)`
  reads from the package directory. `bootstrap`, `profiles`, `memory` and
  `workers` all route through it.
- `DEFAULT_RULES_MD` is now `load_prompt("workspace_rules.md", …)` — the full
  packaged file at import, with a deliberately minimal `_RULES_MD_FALLBACK` for
  a corrupt install only (not a second copy of the ruleset). The
  byte-for-byte drift guard is replaced by two checks: the templates ship inside
  the package, and `DEFAULT_RULES_MD` resolves to the packaged file rather than
  the fallback.
- The workspace-seeded copies (`<workspace>/prompts/`, `<workspace>/skills/`)
  that `ensure_workspace` writes when the CLI runs from the repo are now both
  `.gitignore`d.

## Alternatives rejected

- **Keep both `skills/` and `builtin_skills/`, add a drift-guard test.** Lower
  churn, but preserves two copies of every playbook and the "loader ignores the
  directory people edit" footgun. Rejected for a genuine single source.
- **Make top-level `skills/` canonical; generate `builtin_skills/` at build
  time** (hatch `force-include` / a build hook). Requires build machinery, and
  breaks the `~/.sympose/skills/` seed for editable installs where the generated
  copy doesn't exist. Against the zero-bloat mandate.
- **Symlink `sympose/builtin_skills` → `../skills`.** Fragile across git
  checkouts, sdist/wheel packaging, and Windows. Rejected.
- **Tiered/lazy skill loading now** (stub always, full body on demand). The
  on-demand fetch is an extra round-trip, against
  [ADR-071](./2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md)'s
  frugality; keyword-gating avoids the round-trip but risks a skill being absent
  on the turn it is finally needed. Deferred as an explicit, separately-decided
  optimisation rather than bundled here.
- **Leave `DEFAULT_RULES_MD` as an independent short fallback.** That is exactly
  what caused fresh installs to run stale rules. First resolved with a
  mirror + guard test; superseded on 2026-09-07 by shipping
  `sympose/prompts/workspace_rules.md` in `package-data` and loading it at
  import (see the cont'd implementation note), which removes the second copy
  entirely rather than policing it.
- **Ship `prompts/` only in the sdist via `MANIFEST.in`** (the state before this
  change). `MANIFEST.in` does not affect the wheel, so `pip install` /
  `pipx install` — the actual install paths — never received the files.
  Rejected; `package-data` is what wheels honour.
