---
title: "ADR-122 — Local/Cloud Model Routing by Message Complexity"
created: 2026-09-14
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - model-routing
  - performance
  - ollama
---

# ADR-122 — Local/Cloud Model Routing by Message Complexity

- **Status:** Accepted — implementation in progress (config schema, Ollama
  warm-check/warm-up helpers, classifier + decision function, and
  `chat_stream` wiring shipped; per-persona `local_model` values, tests
  around concurrent local-model requests, and Slack transparency-indicator
  follow-ups still open — see Follow-ups).
- **Date:** 2026-09-14
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Every message a persona answers today goes to whichever model is configured
for that persona — full stop. A one-word greeting and a genuinely hard
question cost the same cloud-model round-trip. This surfaced as a parked
idea during the pre-agent-layer architectural review (2026-09-14): route
the everyday small stuff — definitions, quick math, grammar, a casual "hi,
how are you" — to a free local model via Ollama, and only spend a cloud
call on messages that actually need it.

Design constraints established through discussion, each with a concrete
reason:

- **The decision must not touch ADR-071.** Routing which model answers is
  a model-selection question, not a dispatch-mechanism one — nothing about
  it makes any action answer-gating. Confirmed explicitly: the router
  decides before any model is called, so it never waits on a model to
  report its own confidence.
- **No model — local or cloud — ever judges its own reliability.** A small
  local model is bad at knowing what it doesn't know; it tends to be
  confidently wrong rather than honestly uncertain. The routing decision
  has to be made by something that isn't a model at all.
- **The risk that actually matters is message weight, not conversation
  position.** Early in this design, "never switch models mid-conversation"
  was proposed to protect a persona's voice consistency, then walked back:
  a casual aside mid-conversation is exactly as safe to route cheap as a
  cold-open one. The real risk is a message doing real emotional or
  intellectual work getting misjudged as simple — a narrower thing to
  guard against than conversation position.

## Decision

### Routing mechanism (revised during implementation, 2026-09-14)

Originally scoped as: adopt LiteLLM's `ComplexityRouter` (`litellm.Router`
with a `model_list` entry pointing at `auto_router/complexity_router`)
wholesale. Verified that config shape directly against the installed
`litellm==1.98.0` source — it's real and it works as documented. But
implementing against it surfaced a better option sitting right next to it:
`sympose/engine.py::PersonaEngine._build_kwargs` already correctly
resolves `keep_alive`, per-backend timeout, API keys, and temperature for
whichever model a turn calls — every `litellm.completion()` call in the
app already goes through it. Adopting the full `Router` object would mean
re-deriving that same resolution a second time, in the Router's own
`litellm_params` config shape, instead of reusing code this project
already trusts — and trusting a materially more complex object verified
only by reading its source, not by running it.

**Revised mechanism:** a small, self-owned classifier
(`sympose/model_router.py::is_simple_message`) — deterministic
regex/keyword/length checks, no model call, same shape and spirit as
LiteLLM's own heuristic (and as the vault-query-trigger check Sympose
already ships) — decides SIMPLE-or-not before anything is called. The
turn then reuses the existing `_build_kwargs` + `litellm.completion()`
path with whichever model that decision points to, with fallback-to-cloud
implemented directly as a plain try/except around the local call rather
than the Router's `fallbacks` config. Same behavioral contract as the
original plan (free, instant, deterministic, never a model judging its
own reliability) — smaller, more testable mechanism, no new dependency
surface. This is the version actually implemented; the paragraph above is
kept for the record, not deleted, per this project's own convention of
revising ADRs in place rather than rewriting history.

Only genuinely **SIMPLE** messages route local. Everything else stays on
the persona's existing configured (cloud) model — unchanged from today,
and this is the default for every persona until `local_model` is
explicitly set on one.

### Fallback

A plain try/except around the local `litellm.completion()` call, retrying
on the persona's normal cloud model on any exception — e.g. the exact
`ollama/qwen2.5:7b not found` error hit live during this design, from a
model that was never actually pulled. No router config needed to express
this; it's the same shape as any other error-handling path already in
`engine.py`.

### Warm-up (the cost this design actually has to manage)

Measured live against this machine's own Ollama install before deciding
anything, rather than assumed:

| | Cold | Warm |
|---|---|---|
| Loading the model into memory | ~4–8s | ~0s |
| Processing a persona's full system prompt (Samantha's is 41,816 characters / 2,051 tokens) | ~14s | ~0.4s (Ollama caches the matching prompt prefix) |
| Writing the reply itself | ~13–14 tokens/sec, regardless of warm/cold | unchanged |

Total measured: **~45s cold, ~2s warm**, for the same real request. So:

- Before routing to local, check Ollama's `/api/ps` (free, near-instant —
  lists currently-loaded models). If the target model isn't warm, route
  *this* message to cloud instead and fire a background warm-up request,
  so the next SIMPLE message is fast. Never make the user pay the cold-load
  cost directly.
- Extend `keep_alive` past Ollama's 5-minute default so a normal pace of
  casual messages doesn't let the model go cold between them.
- Optionally warm the configured local model(s) once at Sympose startup.
- **Warming does not fix generation speed.** ~13–14 tok/s is this
  model/hardware's actual writing speed, warm or cold — a genuinely long
  reply still takes real time to produce. This is why the SIMPLE tier also
  gets a response-length cap (below): bounding tier eligibility to things
  that were never going to be long anyway is what actually keeps worst-case
  wait short, not warming alone.

### Response-length cap on the SIMPLE tier

Cap `num_predict`/`max_tokens` for SIMPLE-tier calls. This is the one lever
that constrains worst-case wait independent of hardware or warm state —
appropriate anyway, since SIMPLE is scoped to things that should be short.

### Slack gets no streaming benefit — factor this in

Checked directly: `sympose/cli.py`'s REPL streams `chat_stream`'s chunks to
the terminal as they arrive. `sympose/slack.py::_process_message` does not
— it fully drains the generator (`chunks = [c for c in
self.engine.chat_stream(...)]`) before posting anything via `say()`. So a
Slack user feels the *entire* generation time as one silent wait, with none
of the CLI's progressive-reveal cushioning. The response-length cap above
matters more on Slack than anywhere else in the app for exactly this
reason.

### Persona-specific exception: Aurelius never auto-escalates to cloud

Aurelius's persona is deliberately air-gapped (`share_memory: false`,
100% local by design, per his own profile and
`docs/wiki/personas/aurelius.md`). An automatic local→cloud fallback
firing for him — even just on a transient Ollama error — would silently
send private journal content to a cloud API, defeating the one guarantee
his persona exists for. He must be excluded from the fallback path
entirely, or at minimum require explicit confirmation before ever leaving
local, never a silent automatic escalation. (Not a concern for Samantha or
Grace, who already run cloud by default and are only gaining a cheaper
SIMPLE-tier option, not losing a privacy guarantee.)

### Config surface

Every new knob this introduces (which local model per persona, keep-alive
duration, SIMPLE-tier token cap, whether routing is enabled at all) is
declared once in `sympose/config_schema.py`, per ADR-077 — no literal
defaults at call sites, no second copies.

## Consequences

**Positive**

- Genuinely free, near-instant handling for the everyday small stuff this
  was built for, once warm.
- No new dependency — the classifier and decision function are a few dozen
  lines of stdlib-only Python sitting next to the `_build_kwargs` path
  every model call already goes through.
- Confirmed zero interaction with ADR-071's dispatch-mechanism decision —
  this is a model-selection question, resolved before any model call, with
  no model ever asked to self-assess.
- The `/model`-list Ollama-availability fix (2026-09-14, already shipped)
  and the Slack DM-memory fix (2026-09-14, already shipped) both surfaced
  directly from working through this design — real, independent bugs this
  investigation was worth doing for on its own.

**Negative / costs**

- Keeping a local model warm continuously costs several GB of RAM/VRAM for
  as long as Sympose runs — a real, ongoing resource tradeoff, not a one-
  time cost.
- Local-model output quality is measurably weaker than cloud for anything
  beyond trivial — confirmed appropriate to scope to SIMPLE only, not a
  general-purpose cost-saver.
- Concurrency is untested: what happens when two personas (or two Slack
  threads) hit the same local model at once is unknown and needs an actual
  test before this is trusted, not assumed to be fine.
- Slack's lack of streaming means this design's success is more exposed
  there than on the CLI/dashboard — the length cap is load-bearing, not
  optional, for that surface specifically.

## Alternatives rejected

- **Let the model decide its own confidence and self-escalate.** Rejected
  — the specific failure mode of a small model is being confidently wrong,
  not honestly uncertain; self-assessment is exactly the thing small
  models are worst at.
- **Always try local first, escalate to cloud on low confidence.**
  Rejected — wastes real time on every message that was always going to
  need cloud anyway, since the local model's full response time gets paid
  as pure overhead before the cloud call even starts. Deciding the lane
  upfront, before calling anything, avoids this entirely.
- **Adopt LiteLLM's `Router`/`ComplexityRouter` object wholesale.**
  Initially the plan (see "Routing mechanism" above) — verified real and
  workable directly against installed source, not just documentation.
  Reversed once implementation started: it would require re-deriving
  `_build_kwargs`'s already-correct, already-tested config resolution a
  second time inside the Router's own `litellm_params` shape, and would
  mean trusting a materially more complex object never run live in this
  codebase. A small, self-owned classifier reusing `_build_kwargs`
  achieves the identical behavioral contract with less surface area.
- **Pin one model for the whole conversation once it starts.** Rejected/
  refined mid-discussion — the real risk is a specific message's weight,
  not its position in the conversation; a trivial aside deep into a
  conversation is exactly as safe to route cheap as a cold-open one.
- **Apply the same auto-fallback-to-cloud behavior uniformly to every
  persona.** Rejected for Aurelius specifically — his persona's entire
  reason for existing is air-gapped privacy; a uniform policy would
  silently break that guarantee the first time his local model hiccuped.

## Follow-ups (not yet resolved, tracked here rather than lost)

- Test concurrent local-model requests (two personas / two Slack threads at
  once) before trusting this in production.
- Confirm whether Slack shows any post-reply model/latency indicator
  equivalent to the CLI's `[X.Xs TTFT | Y.Ys total | model]` footer; if not,
  decide whether one is worth adding for transparency into which tier
  answered.
- Pick the actual per-persona SIMPLE-tier local model(s) and the specific
  keep-alive/token-cap values when implementation starts — this ADR
  decides the mechanism, not the exact numbers.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in
the same change.
