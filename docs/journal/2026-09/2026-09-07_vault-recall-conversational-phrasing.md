---
entry: 2026-09-07
created: 2026-09-07 20:05
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/vault
  - sympose/retrieval
---

# Sympose Engineering Log: Vault Recall vs. Conversational Phrasing

> **Date:** Sunday, September 7, 2026
> **Topic:** A persona on a local model "couldn't read the vault" and answered
> from the web instead — a long-standing brittleness in pre-turn retrieval,
> exposed by moving Anaïs to a 14B local model
> **Participants:** damiro (Lead Architect), Claude (Sonnet 5) (Engineering Partner)
> **Status:** Implemented, tested (176 passing)

## Symptom

After Anaïs was switched to a local `ollama/…qwen2.5-14b` model, vault questions
over Slack ("pull up my notes on \<name\>", "what did I write about \<topic\>")
came back with web-search answers instead of vault content.

## Root cause — not a regression from the skills work

No commit in the skills-compression / prompt-cache work touched
`sympose/vault.py`. Two independent facts combined:

1. **`VaultManager.resolve_turn_context` case 8** (the conversational fallback
   that injects `### Vault Search Results` before inference) extracted the search
   term with a chain of prefix-strip regexes that knew `pull` but not `pull up`.
   "pull up my notes on Rilke" was reduced to `"up my notes on Rilke"`, then
   passed whole to `search()`, which is substring-based — so it matched nothing.
   `search("Rilke")` alone would have matched every note mentioning him. Every
   natural phrasing fell through to `return None`, so no vault context was ever
   injected.
2. **A strong cloud model** used to paper over this by emitting
   `[SPAWN_WORKER: vault_recall | …]` on its own initiative when it had no
   pre-turn context. A 14B local model does not — it takes the base rules'
   encouragement to use `[SEARCH]` (web) literally.

## Changes

- **`_extract_recall_subject(message) -> (subject, had_leadin)`** — a single
  best-effort extractor: strips a greeting, then the longest matching recall
  lead-in (`what did i write about`, `pull up`, `tell me about`, `remind me`,
  `recall`, …), prefers the object of a trailing `about/on/regarding X`, drops a
  trailing `in my journal/vault/notes` clause, and trims stop-word tokens from
  both ends.
- **Case 8 rewrite** — fires on either a trigger keyword *or* a consumed recall
  lead-in, then tries the extracted subject and, on a miss, its most specific
  single tokens (longest first, earliest as tiebreak) so "meridian project"
  falls back to "meridian", not the generic "project". Still returns `None` when
  nothing matches — it only ever adds context on a real hit.
- **Base rule (`workspace_rules.md` Conduct §4, "Vault before web")** — personal
  / journal / "what did I…" questions go to `[SPAWN_WORKER: vault_recall | …]`
  if not already in pre-turn context; `[SEARCH]` is for public/current info
  only. Gives a weak local model an explicit rule instead of a judgement call.
- **`vault_recall` skill** — added the one line it never had: *how* to trigger a
  retrieval (`[SPAWN_WORKER: vault_recall | …]`), and not to fall back to web.
- The stale `~/.sympose/prompts/workspace_rules.md` (an Aug-29 pre-compression
  copy that `ensure_workspace` never refreshes once it exists) was overwritten
  with the current packaged file so the running daemon actually gets §4.

## No ADR

A parsing bug fix plus one Conduct directive; no architectural decision, no new
dependency, within ADR-070's hot-path budget (the extractor is pure string work).
