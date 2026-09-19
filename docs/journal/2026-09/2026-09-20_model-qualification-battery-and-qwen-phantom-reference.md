---
entry: 2026-09-20
created: 2026-09-20 02:59
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/reliability
  - model-routing
  - model-capability
---

# Sympose Engineering Log: Building a Real Model-Qualification Battery, and a Model That Was Never Actually Installed

> **Date:** Sunday, September 20, 2026
> **Topic:** Following up on the session's earlier finding that `gemma4:e4b`
> is unreliable for Sympose's vault work, built a concrete qualification
> battery (a 3-turn scripted conversation combining this session's
> real, confirmed failure modes) to test candidate local models
> objectively instead of by impression. Found a genuine phantom
> reference in the config along the way, and validated a real, working
> local candidate.
> **Status:** Battery built and run against three candidates;
> `gemma2:9b` validated as reliable, `qwen2.5:14b` found to be a
> long-standing dead reference and removed, `gemma4:12b` ruled out on
> practicality (not quality) grounds.

## 1. A bigger, newer model isn't automatically a better fit

`gemma4:12b` (dense, same family as the already-disqualified `e4b`, one
tier up) was downloaded as the first candidate. The battery's own crude
"did it respond" check showed mostly failures, all bearing the same
`litellm.APIConnectionError` signature — easy to misread as "the model
gave bad answers," but reading the actual preview text showed Sympose's
own wrapped runtime-error banner, not a real reply.

**Root-caused, not assumed:** a direct, isolated call with a
~3,600-token prompt (roughly Samantha's real system-prompt size) took
**174.7 seconds** to produce a single word. Ollama's own server log for
the same window showed why: `gemma4:12b` was "forcing full prompt
re-processing due to lack of cache data" on every call — no reuse of
work already done earlier in the same conversation — combined with a
measured ~9.4 tokens/second generation rate. Both compound into a
timeline that reliably exceeds Sympose's 120-second local-model timeout
on any realistically-sized turn.

**Conclusion:** `gemma4:12b`'s actual answer *quality* was never
measured — it never got the chance to finish. This is a genuine,
disqualifying finding on its own terms (a companion model that can't
reply within a reasonable window fails the "cheap, low-latency" premise
this project is built on), independent of whether its judgment would
otherwise have been good.

## 2. `qwen2.5:14b` was never actually installed

Pivoting to `qwen2.5:14b` — already referenced as a "standard"-tier
local option in `config.yaml`, Samantha's `local_model` fallback, and
five skill files' `recommended_models` lists, some of that predating
this session — the battery failed every trial in under 3 seconds each.
That's too fast to be a real model call at all.

A direct call confirmed it immediately: `"model 'qwen2.5:14b' not
found"`. `ollama list` showed only `gemma4:12b`, `gemma4:e4b`, and
`gemma2:9b` actually present on this machine. The reference had been
sitting in the config as a phantom for some time — accepted at face
value in an earlier fix this session (retargeting a since-deleted
abliterated model to it) without verifying it was real, compounding a
pre-existing gap rather than being its origin.

**Fix:** every dead reference retargeted to `gemma2:9b`, the one
already-installed "standard"-tier model actually present. A stale
`skills/vault_recall/` directory — a leftover from before the
`vault_recall → vault_read` skill rename, orphaned and unreferenced by
any code path or persona — was removed outright rather than patched.

## 3. `gemma2:9b`, run through the same battery, passed cleanly

With a genuinely available, appropriately-sized candidate, the battery
finally produced a clean signal: 5/5 on-topic across both conversation
turns, 5/5 non-empty replies, no runaway sub-agent spawning on a casual
acknowledgment ("yeah.. lol.") — the same over-eager-delegation shape
that has repeatedly failed for `e4b` throughout this session. The one
non-perfect flag (a "malformed tag" hit in one trial) traced to the
battery's own crude heuristic misreading a correctly-formatted sub-agent
report badge, not a real model defect.

This is the first genuinely valid quality signal produced all session —
both `e4b` and `gemma2:9b` finish comfortably within timeout, so the
comparison isn't confounded by speed the way `gemma4:12b`'s was.

## 4. Why a smaller, older model beat a newer one — verified, not assumed

`gemma4:e4b` is Gemma 4's "Edge" variant: built to run on phones and
small devices, and to also handle image and audio input, not just text.
Verified live, not just from its `ollama show` capability label
(`completion, tools, thinking` — vision wasn't even listed despite being
real):

- A real PNG generated locally (no external image, no AI involved in
  making it — raw pixel bytes, left half solid red, right half solid
  blue) sent directly through Ollama's chat API: `e4b` correctly
  identified both colors and which side each was on.
- A hand-drawn bitmap-font image reading "OCR42" (a manually-defined
  5×7 pixel font, no real font rendering, no antialiasing): `e4b` read
  it back exactly right.
- The same two images sent to `gemma2:9b` were rejected outright by
  Ollama itself — `"Multimodal data provided, but model does not
  support multimodal requests"` (HTTP 400) — confirming it's genuinely
  text-only, not just unlabeled.

So the comparison isn't "newer model is worse" in any general sense —
it's that `e4b`'s specific design trades away some depth and judgment
reliability to stay small and multi-purpose enough for edge hardware.
For Sympose's actual job (reasoning carefully about text-only vault
notes), that tradeoff loses to a plain, non-edge model that just does
one thing solidly. The multimodal capability itself is real and could
still be useful for a narrowly-scoped task this vault companion
actually has — describing or transcribing an image attachment in the
vault — rather than as the general reasoning model; noted as a future
direction, not started.

## 5. Gemma 2 has no newer version — Gemma 3 is the real next generation

Checked directly against Ollama's own listing rather than assumed:
Gemma 2's three tags (2b/9b/27b) haven't been updated since the
family's original release, about two years ago. The actual generational
succession is Gemma 2 → Gemma 3 → Gemma 4, so `gemma3:4b` (a
similarly-sized, faster-tier candidate rather than the 12b tier that
already proved impractical) was pulled as the next thing to qualify.
`ollama show` confirms `completion, vision` capabilities — no explicit
audio capability, unlike Gemma 4's edge variants. Testing in progress.

**Final verification:** every code change from this thread of work
(the `qwen2.5:14b` retargeting) re-run through the full test suite and
`ruff check`, both clean.
