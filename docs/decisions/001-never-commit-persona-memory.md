# 001 — Never commit persona memory, regardless of handle

## Context

The original `.gitignore` un-ignored `samantha_memory.md` specifically, on the reasoning that Samantha ships as the only default persona, so her config is the one committed exception. That reasoning conflated persona *config* (soul/identity — fine to ship as a template) with persona *memory* (durable facts extracted from real conversations, accumulated from actual use) under the same exception. Memory is personalization that grows from a specific person's real usage — genuinely personal content, never product content — so leaving that exception in place would mean shipping real conversational history into a public repo the moment a memory file is created at onboarding.

## Decision

`profiles/*_memory.md` is always gitignored, for every persona including Samantha. No exception, no template variant. `profiles/*_soul.md` keeps its `!profiles/samantha_soul.md` exception — soul is the shipped baseline personality, distinct from memory.

## Consequences

A fresh clone or install never ships with a memory file — memory files are created at onboarding / agent-creation time and live purely locally, consistent with `CONTRIBUTING.md`'s repository-hygiene rules for any personal, non-product artifact. Anyone editing `.gitignore` later needs to preserve this distinction (soul = committable template, memory = never committable) rather than re-collapsing it into one blanket persona exception.

## Alternatives rejected

Keeping `!profiles/samantha_memory.md` and relying on the user to simply never commit further changes to it once personalized. Rejected because it depends on remembering not to broadly stage a file that's tracked by default — a single accidental broad `git add` would commit real personal conversation content. Untracking the file entirely removes the failure mode instead of relying on discipline to avoid triggering it.

**Path update (docs/decisions/011):** personas are now one directory each, so the ignore rule is `profiles/*/memory.md` (and `profiles/*/sessions/`) rather than `profiles/*_memory.md`, with Samantha's `persona.yaml` and `soul.md` the only committed files under `profiles/`. The invariant recorded here is unchanged: no persona's memory is ever committed.
