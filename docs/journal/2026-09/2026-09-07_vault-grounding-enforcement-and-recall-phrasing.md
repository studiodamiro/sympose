---
entry: 2026-09-07
created: 2026-09-07 21:10
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/vault
  - sympose/grounding
  - sympose/retrieval
---

# Sympose Engineering Log: Vault-Grounding Enforcement & Recall Phrasing (round 2)

> **Date:** Sunday, September 7, 2026
> **Topic:** Anaïs, on a 14B abliterated local model, invented a `People/` entry
> verbatim — wrong birthday, wrong tags, wrong relationship — and then confirmed
> the user's memory against her own fabrication. The grounding *rule text* had
> survived the ADR-076 compression; the grounding *guarantee* had not.
> **Participants:** damiro (Lead Architect), Claude (Sonnet 5) (Engineering Partner)
> **Status:** Implemented, tested (202 passing)
> **Reinforces:** [ADR-024](./../2026-08/2026-08-25_adr-024-ground-truth-sovereignty-axiom.md)
> (Ground-Truth Sovereignty Axiom),
> [ADR-071](./2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md)
> (bracket-tag dispatch). Follows
> [Vault Recall vs. Conversational Phrasing](./2026-09-07_vault-recall-conversational-phrasing.md).

## Symptom

Asked to "pull up Dylan's People entry and check my memory," Anaïs streamed a
fully invented note — `Created: 2021-06-15`, `Tags: #people #friend`, "a close
friend who enjoys music, hiking…" — then "Your memory seems correct." The real
`People/Dylan.md` is a child (b. 2015-09-08), `#person`, `son`, linked `[[Tin]]`.
Part of the reply was in Chinese ("清扫中…请稍候"). The real `vault_recall` worker
*did* run and read the correct file; its report was appended **after** the
fabrication.

## Root cause — three failures stacked, none of them the compression

1. **Pre-turn retrieval handed her the wrong "Ground-Truth" payload.**
   `resolve_turn_context` case 5 (the random daily-note sampler) fired on
   *"entry"* + *"pull"* and injected an unrelated 2025 journal note stamped
   `### Ground-Truth Sandboxed Vault Note`. Case 8 (conversational fallback)
   never recovered the real note: `_extract_recall_subject` does not strip a
   leading *"can you"* (so the *"pull up"* lead-in never matched), and *"dylans"*
   / *"dylan's"* is not a substring of *"Dylan"*.
2. **The model kept talking after emitting the tag.** A retrieval tag's result
   is injected by the runtime *after* the stream; a strong cloud model halts
   after emitting `[SPAWN_WORKER: …]`, a 14B abliterated model narrates the note
   it has not seen yet. Nothing in the runtime stopped it.
3. **The axiom was prompt-only.** ADR-024's own cost line — *"requires strong,
   repeated prompt directives across souls, skills, and workspace rules to hold
   small models in line"* — had quietly stopped being true: ADR-076 collapsed
   the five-point `ZERO TOLERANCE FOR FABRICATION` block to one line and reduced
   `vault_recall`'s standalone grounding paragraph to a parenthetical (correct
   for cloud models, its stated bet), and Anaïs had moved to an *abliterated*
   model whose refusal capacity — the muscle "candidly say I have no record"
   uses — is trained out.

## Changes

### Retrieval (`sympose/vault.py`)

- **`_extract_recall_subject`** now strips a leading politeness/modal wrapper
  (`can you`, `could you`, `please`, `let's`, …) before the lead-in scan;
  normalises the `'s` possessive; splits on sentence terminators and picks the
  clause that actually carries a recall lead-in ("*i wish i could. can you pull
  up my note on grief*" → `grief`); drops a trailing `and …` clause; and treats
  a subject made only of sample/chrono filler (`random`, `daily`, …) as *no
  subject*.
- **Case 5** (random sampler) now requires an *explicit* ask for an arbitrary
  note (`random`, `surprise me`, `pick one`, …) **and** no named subject —
  `pull` / `grab` / `get` alone no longer qualify.
- **Case 7 / Case 8** route through a new **`_recall_hit`**: a single result, or
  a title match on the top hit, returns the note's **full verbatim body** as a
  `### Ground-Truth Sandboxed Vault Note` (the strongest grounding payload);
  broader matches return the ranked digest. Shared candidate ordering lives in
  `_recall_candidates` (full phrase → longest/earliest token → de-pluralised
  stem, so `dylans` → `dylan`).
- **`has_recall_intent`** — a lightweight public classifier the engine uses to
  decide *not* to reuse a prior turn's injected context on a fresh, unanswered
  vault question.

### Runtime enforcement (`sympose/engine.py`)

- **`_visible_stream`** gates the user-facing stream: the moment the model emits
  `[SEARCH` / `[SPAWN_WORKER` (matched across chunk boundaries via a 24-char
  hold-back), visible output stops. The full raw text still reaches
  `ActionProcessor`; the runtime then injects the real report. A model that
  fabricates *after* its own tag can no longer be seen doing it.
- When a retrieval ran, the recorded/streamed answer is trimmed to the
  pre-tag lead-in with any fabricated note body (`#`, `>`, `---`, fences)
  removed.
- Stale-context guard: a fresh recall question that retrieves nothing clears the
  carried-over `active_vault_ctx` instead of answering from an unrelated note.

### Worker → primary-agent handoff (`sympose/actions.py`, `engine.py`, `worker_system.md`)

A second fabrication surfaced on the `[SPAWN_WORKER: vault_recall]` path: asked to
"pull a random daily note", the worker read the real file but surfaced it with
`[READ_NOTE]`, which renders only to the terminal Rich panel. The report handed
back to the primary agent — and to Slack — held just the command list, **no note
text**. The weak primary model then quoted a plausible fabrication ("*fixing my
journal entries*" / "*fixing this website*"; the real entry was about "*fixing the
layout of Benn's resume*"), inventing a different version each turn.

- **`ActionProcessor.execute_actions`** — when `[READ_NOTE]` runs inside a
  **worker** (`handle == "worker"`), the note's verbatim text is folded into the
  worker's returned synthesis as a `### Ground-Truth Sandboxed Vault Note` block
  (≤4000 chars), so it reaches the primary agent's context and the Slack
  transcript, not only the terminal panel. A primary agent's own `[READ_NOTE]`
  is unchanged — that transcript is already user-facing.
- **`PersonaEngine.chat_stream`** — the grounded synthesis pass now runs on
  **every** worker turn (the `has_rendered_note` exemption is gone); the report
  carries the real text for the model to quote on terminal and Slack alike.
- **`worker_system.md`** — the `[READ_NOTE]` directive notes the runtime attaches
  the verbatim text, so the worker adds only a one-line orientation; the
  extract-facts branch is told to quote exact words/dates/names.

### `vault_grounding` knob — model-derived enforcement (`sympose/engine.py`)

Even with the retrieval and handoff fixes, `qwen2.5-14b-abliterated` still
fabricated when the ask was split across turns ("*you may pull his entry*" →
"*would you like me to summarise?*" → "*yes, just summarise*"): by the second turn
the subject and trigger word are gone, nothing fires pre-turn, and an abliterated
model — trained never to decline — invents a summary rather than emitting
`[SPAWN_WORKER: vault_recall]`. Prompt directives cannot force tag discipline on a
model that will not follow them.

- **`_grounding_mode(profile, model)`** returns `strict` or `trust`. An explicit
  persona `vault_grounding: strict|trust` wins; a global
  `config.yaml` `vault.grounding_default` is next; otherwise **`auto`** derives
  it from the model — a local backend (`ollama*`, `lm_studio`, …) or a localhost
  `api_base` → `strict`, cloud → `trust`. So the knob is "per agent" without a
  hand-set flag: Anaïs (local) is strict, Samantha/Grace (Gemini) are trust.
- **`strict` mode** (`engine.chat_stream`): the model's text is held, not
  streamed. If no worker ran and no pre-turn context was injected, the runtime
  looks for a vault subject — in the current message, or in a "*yes / go ahead /
  just summarise*" affirmation of a prior turn's retrieval promise (`_entity_guess`
  pulls the name), or in the model's own reply if it asserts vault content
  (`_VAULT_CLAIM_RE`). Found → it emits `[SPAWN_WORKER: vault_recall | <subject>]`
  itself, discards the model's un-retrieved answer, and the grounded synthesis
  pass answers from the report. Nothing found but the reply still claims to
  report the vault → the reply is withheld and replaced with a candid "*I haven't
  pulled that yet — which note or name?*". `trust` mode is unchanged (today's
  behaviour); a strict persona with successful pre-turn context also streams
  normally.

### Worker tool-budget backstop (`sympose/workers.py`)

A Samantha turn (*"i spoke with tin also… i miss her"*) fired `vault_recall`; the
worker read `People/Tin.md` and `People/Dylan.md`, then spent its remaining turns
on redundant `grep`s, hit `max_worker_tool_turns` (8), and returned "*reached
maximum tool turns without completing final synthesis*" — discarding the notes it
had already gathered. Samantha then correctly said she had no quotes (honest
failure), but the answer was recoverable.

- The worker's **final allowed turn** now runs with `tools` removed and a
  `_LAST_TURN_NUDGE` appended ("*no more tool calls — synthesise from what you
  have, quote verbatim, say what's missing*"), so it produces a deliverable
  instead of another `grep`.
- If that still yields empty content, **`_forced_synthesis`** makes one more
  `tool_choice="none"` call over the same transcript as a backstop. Only the bare
  "*hit its tool budget; retry with a narrower ask*" notice remains for a genuine
  empty-handed run.

### Prompts

- **`workspace_rules.md` — Grounding & Anti-Hallucination** rewritten (≈+180
  tokens over the ADR-076 low-water mark, a deliberate re-thickening of the
  load-bearing rule): "a document you read, never one you remember"; state a
  note fact *only* from a payload given this turn, quoted verbatim; no payload →
  say so and spawn `vault_recall`, or "I have no record of that in your vault";
  **after emitting `[SEARCH]` / `[SPAWN_WORKER]`, stop** (pairs with the runtime
  gate). Conduct "Vault before web" slimmed to a pointer.
- **`vault_recall/SKILL.md`** — the standalone ground rule restored: every claim
  about a note is a verbatim quote; never reconstruct from the topic; empty
  retrieval → the fixed sentence, nothing more.

## No ADR

Parsing hardening + one prompt restructure + a bounded gate on the *existing*
ADR-071 dispatch path. No new dependency, no new service, pure string work on the
hot path (within ADR-070's budget). It reinforces ADR-024 and ADR-071 rather
than deciding anything new; elevate to an ADR only if the stream gate grows
policy knobs.
