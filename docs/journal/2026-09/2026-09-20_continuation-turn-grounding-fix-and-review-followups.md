---
entry: 2026-09-20
created: 2026-09-20 01:13
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/grounding
  - sympose/reliability
  - model-routing
  - code-review
---

# Sympose Engineering Log: The Continuation-Turn Title Check Was Discarding Good Answers, Plus a Full Code-Review Sweep

> **Date:** Sunday, September 20, 2026
> **Topic:** A follow-up to the 2026-09-19 "Vault Roulette" transcript
> review: the `_vault_ctx_title_missing` grounding check (built that same
> day to catch a real fabrication) turned out to over-fire on ordinary
> follow-up turns, discarding correct answers. Fixed, then ran a full
> self-review + `/code-review` pass on the change plus some adjacent
> cleanup (model roster, a public-facing skill file), which surfaced a
> real regression in an already-shipped guard and nine smaller findings.
> **Status:** All fixed and live-verified.

## 1. `_vault_ctx_title_missing` was punishing natural paraphrasing

`_vault_ctx_title_missing` (added 2026-09-15) exists to catch a specific
fabrication: handed a real note, a model narrates an unrelated or
invented title in prose instead of actually using what it was given. It
works by checking whether the real note's own filename stem appears
anywhere in the reply — a presence check, deliberately not a meaning
check, to avoid a second model call.

The problem: it applied that same rule to two very different moments.

- **A fresh introduction** ("let's roll the dice again" — a brand-new note
  just got pulled) — expecting the reply to name the note is reasonable.
- **A follow-up about a note already on the table** ("so, what can you say
  about that note?") — the model is expected to describe it in its own
  words. There's no reason a good answer needs to repeat the literal
  filename again.

The check couldn't tell these apart, because it only ever saw the note
content and the reply text — never whether the note was new-this-turn or
carried over from before.

**Verified with a 6-trial reliability comparison**, not assumed: the same
two-turn scenario (introduce a note, then an ambiguous follow-up) run 6
times each with the check on and off, against a local model:

- **Check on:** 5 of 6 follow-up replies were accurate, on-topic
  paraphrases — and all 5 got discarded for the canned "I couldn't fully
  verify that, here's the exact note instead" fallback anyway.
- **Check off:** 6 of 6 replies were legitimate, and zero were
  fabrications.

**Fix:** an `is_fresh` signal, computed where the turn already knows the
answer — `_resolve_turn_vault_context` (a genuine new-this-turn structural
match) and the "roll the dice" ritual-pull path (also a genuine
new-this-turn introduction) both set it True; every carried-over/refreshed
path leaves it False. `_vault_ctx_title_missing` now takes `is_fresh` as a
real parameter — not a docstring-only convention a future call site could
silently forget — and only runs its title check when it's True.

Re-ran the live 3-trial comparison after the fix: 0 of 3 continuation
replies discarded, versus the prior all-discarded behavior. Both fabricated
and legitimate cases now resolve correctly.

## 2. Model roster cleanup

An abliterated Qwen 2.5 14B variant that had been Samantha's configured
`local_model` fallback was removed from the local Ollama install. Every
reference to it — the persona's own `local_model` setting, the
`capability_tiers` registry entry, and the `recommended_models` list in
three skill files (both the shipped templates and the live workspace
copies) — was retargeted to the plain, already-installed `qwen2.5:14b`,
so nothing in the repo points at a model that no longer exists locally.

## 3. `vault_write`'s skill instructions were written for one vault, not any vault

Reviewing the skill file surfaced that its folder-routing table hardcoded
one specific personal folder taxonomy as if it were the only one Sympose
supports — directly contradicting the product's own stated design (Sympose
adapts to whatever taxonomy a vault already uses: flat, PARA, Johnny
Decimal, Zettelkasten). The wikilink/tag examples also named real personal
entities and interests.

**Fix:** the folder-routing guidance now tells the model to route against
*this vault's own existing folders* rather than a fixed list, and to ask
the user rather than invent an unfamiliar category. `[DAILY_NOTE]`'s own
code-enforced destination path was kept as-is (that part is mechanical,
not a taxonomy choice). Wikilink/tag examples switched to generic
placeholders. Added explicit guidance to weigh existing notes' structure,
tone, and any in-vault template before writing, and to ask the user when
genuinely unclear — rather than silently guessing at either. Also
documented a real fallback path that existed in code but was undocumented:
a vault with no `Templates/` collection at all still gets a generated
minimal frontmatter block, never a bare note.

## 4. Full code-review pass — one real regression, nine smaller findings

Ran self-review plus the `/code-review` skill against the accumulated
diff (the fix above, the model cleanup, and the skill rewrite). Verified
every finding against real code or a live repro before accepting it — the
review has produced at least one non-reproducing claim in a past session,
so each one was checked rather than trusted outright.

**The real regression**, confirmed by direct reproduction: `sub_agents.py`'s
task-alignment guard (added in yesterday's ADR-139 work) discards a sub-
agent's answer whenever its task named a real note that was never opened
via `read_file`/`vault_sample` — but a sub-agent that answers correctly
using only `vault_search` legitimately never populates that read-tracking
set by design (a ranked snippet isn't a full body). The guard couldn't
tell "never looked at the right note" apart from "looked it up a different
way and got it right," and discarded correct, search-grounded answers for
a raw note dump instead. **Fix:** the guard now also credits any note path
that shows up for real inside the turn's own tool-call outputs — genuine
evidence the note's content was surfaced, just not via a full read — not
only paths in the narrower read-tracking set. Live-reproduced before and
after: the correct answer was discarded before the fix, preserved after.

**A public-facing privacy leak**, caught by re-checking the review's own
claim against the actual file: the 2026-09-19 journal entry embedded a
real session-log filename, real personal ratings, and a real vault note
path — all things `documentation_standards.md` explicitly requires stay
generic before a journal entry reaches the public remote. Fixed by
genericizing every instance; the commit carrying it hadn't been pushed
yet, so nothing was ever actually exposed.

**Eight smaller findings**, all fixed:
- `_swap_in_task_mismatch` was re-resolving a note it had already resolved
  once, with no fallback if the second resolution ever disagreed with the
  first — now takes the already-resolved content directly instead.
- `_vault_ctx_title_missing`'s `is_fresh` requirement (§1) was
  docstring-only rather than an actual parameter — now enforced by the
  signature itself.
- `_apply_grounding_and_stream_result` had grown to four consecutive
  unlabeled positional booleans — now keyword-only.
- A config lookup in `commands.py`'s capability-gap check was re-fetched
  once per loaded skill in a loop instead of once — hoisted out.
- Two branches in the vault-context resolver ran byte-identical recovery
  logic — merged into one shared helper.
- The same subject/lead-in extraction underlying vault-recall detection
  was being computed up to three times per turn on the hot path — added
  a single-pass `VaultManager.recall_signal()` and reused one result
  across both call sites instead.
- That same refactor addressed a related architectural note: the
  "intent + subject + lead-in" concept now lives as one canonical
  operation in the module that owns the matching rules, rather than being
  reconstructed piecemeal at each call site — with no change to
  `has_recall_intent`'s own external behavior for its other callers.
- The vault-context-resolution module had grown past this project's own
  200-line-per-file guidance as a direct result of these fixes — split
  the turn-context-resolution logic into its own module, both files well
  under the limit afterward.

**Final verification:** full suite (1212 tests) and `ruff check` clean
after every step; both live scenarios (the continuation-turn fix and the
task-alignment fix) re-verified end-to-end with no mocking after the
module split and refactor landed, confirming neither introduced a
regression.
