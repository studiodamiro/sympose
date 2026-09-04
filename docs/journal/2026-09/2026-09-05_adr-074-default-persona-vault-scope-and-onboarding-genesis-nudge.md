---
title: "ADR-074 — Default Persona Vault Scope & Onboarding Persona-Genesis Nudge"
created: 2026-09-05
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - onboarding
---

# ADR-074 — Default Persona Vault Scope & Onboarding Persona-Genesis Nudge

- **Status:** Accepted — implemented 2026-09-05.
- **Date:** 2026-09-05
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Following the repository-hygiene shareability passes (LICENSE, CI,
`SECURITY.md`), damiro asked to continue the *product* side of
shareability — making Sympose usable by someone who isn't him, not just
legally/procedurally clean to clone.

Auditing the actual first-run path (not the repo's own tracked
`profiles/samantha.yaml`, which is damiro's live instance — the fresh-install
template embedded in `sympose/bootstrap.py`'s `SAMANTHA_YAML`, written to
disk by `ensure_workspace()` on every genuinely new `pipx install`) surfaced
two gaps:

- **`SAMANTHA_YAML` hardcoded `vault_folders: ["General", "Projects",
  "Thoughts", "Templates"]`.** `VaultManager.get_allowed_dirs`
  ([vault.py:56-64](../../../sympose/vault.py#L56-L64)) calls
  `os.makedirs(path, exist_ok=True)` for every listed folder — so the moment
  a new user links their real Obsidian vault in onboarding Step 2, Sympose
  silently creates 4 folders inside it, and Samantha has **zero visibility
  into anything outside them**. A PARA vault's `1-Projects`/`2-Areas` or a
  Zettelkasten vault's numbered-note structure would be entirely invisible
  to her. This directly contradicts the README's own claim — "Sympose
  adapts to any folder taxonomy (Flat, PARA, Johnny Decimal, Zettelkasten)"
  — for the one persona guaranteed to ship, and the wiki's own
  [sandboxed-vault.md](../../wiki/architecture/sandboxed-vault.md#L39)
  already described Samantha as the persona *least* expected to be folder-
  restricted ("to restrict an agent (e.g., Samantha)... simply leave them
  off"), which the shipped default silently contradicted.
- **The onboarding wizard** (`run_first_run_onboarding`,
  [bootstrap.py:210](../../../sympose/bootstrap.py#L210)) is two steps — AI
  provider, vault path — and drops straight into `@samantha` chat with zero
  mention that other personas can be created, or how. A first-run user who
  wants "their own Grace" has no in-app signal that's possible.

## Decision

- **ADR-074.1 — Default Samantha's `vault_folders` to `["*"]` (full vault
  access).** In both `sympose/bootstrap.py`'s `SAMANTHA_YAML` template (the
  real fresh-install path) and the repo's own tracked
  `profiles/samantha.yaml` (the ADR-046 starter seed, which should match the
  generic default rather than carry damiro's personal folder taxonomy —
  the same class of gap ADR-046 already closed for Grace/Anaïs, just one
  layer deeper: the tracked Samantha file itself wasn't generic). No folders
  are created on link; she can read/write anywhere in whatever vault gets
  linked, matching her role as orchestrator. A user who wants to sandbox her
  narrows `vault_folders` themselves — documented as the deliberate
  exception, not the default, in
  [creating-agents.md](../../wiki/guides/creating-agents.md).
- **ADR-074.2 — A third onboarding step nudging persona genesis.** After the
  vault-link step, a panel states Samantha is the only persona shipped, gives
  a one-line natural-language example of asking her to create a companion,
  and reminds the user `/switch @samantha` always comes back. No new
  mechanism — `[CREATE_PERSONA]` already existed — purely a discovery fix.

## Consequences

**Positive**

- Delivers on the "adapts to any folder taxonomy" claim for the one persona
  every install actually has.
- No more silent folder creation inside a new user's real, already-organized
  vault on first link.
- Closes a real discovery gap: persona creation was real and documented, but
  invisible from inside the product itself until now.

**Negative / costs**

- Broadens damiro's own local Samantha's practical vault access too, since
  `profiles/samantha.yaml` is both the tracked starter template and his live
  instance file — a strict widening (nothing she could already reach becomes
  unreachable), not a behavior loss, but worth being explicit about since it
  wasn't scoped to "future users only."
- One more onboarding panel to read before reaching the first chat prompt;
  judged worth it against the alternative (a first-run user never
  discovering persona creation at all).

## Alternatives rejected

- **Keep the scoped default, just widen the folder names** (e.g. add common
  PARA/Zettelkasten aliases). Rejected — any fixed list only covers the
  taxonomies it happens to guess, and still auto-creates folders a
  Flat/Johnny-Decimal/anything-else user never asked for. `["*"]` is the only
  option that's genuinely taxonomy-agnostic.
- **Skip the onboarding nudge, rely on README/wiki docs for discovery.**
  Rejected — the whole point of "shareable" is a stranger who hasn't
  necessarily read the README getting a working, discoverable product from
  inside the CLI itself.
