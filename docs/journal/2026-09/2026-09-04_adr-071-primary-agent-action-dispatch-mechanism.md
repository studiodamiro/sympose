---
title: "ADR-071 — Primary-Agent Action Dispatch: Bracket-Tag DSL vs Native Function Calling"
created: 2026-09-04
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - action-protocol
---

# ADR-071 — Primary-Agent Action Dispatch: Bracket-Tag DSL vs Native Function Calling

- **Status:** Partially implemented, core decision still Proposed — F6 and F7
  fixed 2026-09-04 (correct regardless of A/B); the dispatch-mechanism choice
  itself was superseded mid-review by a third framing not captured in the
  original A/B and remains undecided. See **Implementation Note** below.
  Revisits
  [ADR-037](../2026-08/2026-08-26_adr-037-pure-declarative-markdown-prompting.md)
  (pure declarative markdown prompting) and
  [ADR-049](../2026-08/2026-08-29_adr-049-code-fence-action-tag-parsing.md)
  (code-fence tag parsing) in light of
  [ADR-024](../2026-08/2026-08-25_adr-024-ground-truth-sovereignty-axiom.md)
  (ground-truth sovereignty). Source:
  [2026-09-04 Backend Architecture & Objective-Effectiveness Review](./2026-09-04_backend-architecture-effectiveness-review.md) (F5–F7).
- **Date:** 2026-09-04
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Sympose runs **two different tool paradigms**:

1. **Primary conversational agent** — emits actions as free-text tags in the
   response stream (`[WRITE_NOTE: path | body]`, `[SPAWN_WORKER: spec | task]`,
   `[CONFIG_SET: key | value]`, `[CREATE_PERSONA: …]`, …), parsed **after**
   streaming by a hand-rolled bracket matcher
   ([actions.py:31](../../../sympose/actions.py#L31)), executed by
   `ActionProcessor.execute_actions` ([engine.py:189](../../../sympose/engine.py#L189)).
2. **Ephemeral worker** — uses standard OpenAI-style function calling
   (`tools=[…]`, `tool_choice="auto"`,
   [workers.py:217](../../../sympose/workers.py#L217)).

The fragile paradigm is the one on the user-facing path. Observed costs in the
code:

- **No schema, no validation.** `CONFIG_SET` infers types with
  `try: int / except: try: float` ([actions.py:207-217](../../../sympose/actions.py#L207-L217))
  and writes straight to `config.yaml`. `CREATE_PERSONA` writes raw model YAML to
  `profiles/`.
- **Grammar collides with prose about the grammar.** `parse_action_tags`
  carries a regex to *skip documentation placeholders* like `<handle>`
  ([actions.py:59](../../../sympose/actions.py#L59)) because the model quoting the
  tag syntax would otherwise trigger it.
- **Intent-guess file writes (F6).** [actions.py:291-308](../../../sympose/actions.py#L291-L308)
  scrapes the model's prose for `Reflection:` / `Key Themes:` and *infers* a
  `DAILY_NOTE` write when the user's message matched `log|save|write … journal` —
  writing to the vault on a regex guess, directly against ADR-024 ("merely
  printing markdown does not write files").
- **Unbounded recursion (F7).** `SPAWN_WORKER` → `execute_worker_task` →
  `execute_actions(pm, "worker", synthesis)` re-parses worker output for tags
  ([actions.py:166](../../../sympose/actions.py#L166)); a worker synthesis
  containing `[SPAWN_WORKER: …]` spawns again, with no depth counter.

ADR-037's "pure declarative markdown, zero code injection" goal is still valid
for *soul / rules* content. It does not require the *action channel* to be
unstructured free text.

## Decision

Proposed — one of the following, decided by damiro:

- **ADR-071-A (recommended) — Migrate state-changing actions to function
  calling.** Give the primary agent the same `tools=[…]` path the worker uses for
  `write_note`, `append_note`, `daily_note`, `config_set`, `create_persona`,
  `spawn_worker`. Keep the prose turn streaming; execute tool calls on the
  follow-up completion. Deletes `parse_action_tags`, the placeholder regex, and
  the F6 inference fallback. `[REACT: …]` (Slack-only, cosmetic) may stay a tag.
- **ADR-071-B — Harden the DSL, delete the guesswork.** Keep tags for their
  token/latency profile but (1) switch to an unambiguous delimiter that cannot
  occur in prose (a fenced `⟦ACTION name⟧ … ⟦/ACTION⟧` block or a single trailing
  JSON line), (2) **delete** the F6 "model forgot the tag" fallback outright —
  no tag, no write, and (3) add a `depth` parameter to `execute_actions`, capped
  at 1.

Either way: **F6 (intent-guess writes) and F7 (recursion cap) are fixed
regardless of A or B.**

## Consequences

**Positive**

- A: schema-validated arguments, no parser heuristics, one paradigm in the
  codebase, native provider support.
- B: keeps the low-token action channel; removes the two behaviours most likely
  to corrupt the vault or loop.

**Negative / costs**

- A adds one round-trip on turns that take an action (already true for
  `SPAWN_WORKER` synthesis today); some cheap local models have weaker
  tool-calling than others — mitigated by keeping `[REACT:]` as a tag and by the
  worker path already depending on tool calling.
- B still relies on the model emitting exact syntax; it only narrows the failure
  surface.

## Implementation Note (2026-09-04)

- **F6 and F7 — fixed, independent of the A/B choice.** The intent-guess
  `DAILY_NOTE` fallback (scraping the model's prose and writing to the vault on
  a regex guess) is deleted outright. `execute_actions` now takes a `depth`
  parameter (`MAX_ACTION_DEPTH = 1`) capping `SPAWN_WORKER`'s recursive
  re-parse of worker output. Commit `c8b0e7f`.
- **The A vs B decision did not happen as scoped.** A same-day conversation
  about round-trip cost surfaced a distinction this ADR's two options both
  missed: split actions into **fire-and-forget** (`WRITE_NOTE`, `REMEMBER`,
  `DAILY_NOTE`, `CONFIG_SET`, `REACT` — the model doesn't need to see the
  result to finish answering) versus **answer-gating** (vault retrieval the
  model needs before it can respond, `SPAWN_WORKER` synthesis). Several
  providers support emitting prose text and a tool call in the *same*
  completion, so fire-and-forget actions could get schema validation via a
  structured tool-call with **zero added round-trips** — neither pure
  option A (full function-calling, a round-trip on every action) nor pure
  option B (harden the free-text grammar) captures that. This third shape is
  the live candidate but was never formally decided; `parse_action_tags` and
  the bracket-tag grammar are unchanged. Revisit before touching the dispatch
  mechanism itself.

## Alternatives rejected

- **Status quo.** The F6 fallback writing files on a regex guess is not
  compatible with ADR-024 and must change independent of the A/B choice.
- **Both channels in parallel long-term.** Doubles maintenance and test surface;
  acceptable only as a short migration window under ADR-071-A.
