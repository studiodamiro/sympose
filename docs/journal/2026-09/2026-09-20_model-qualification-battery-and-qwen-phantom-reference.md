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
> **Status:** Battery built and run against four candidates.
> `gemma2:9b` validated as reliable; `qwen2.5:14b` found to be a
> long-standing dead reference and removed; `gemma4:12b` ruled out on
> practicality (not quality) grounds; `gemma3:4b` found unreliable on
> the same fresh-announcement failure mode `e4b` has, masked by the
> battery's own safety-net blind spot until caught and fixed.
> `gemma4:e4b`'s vision claim verified live (color/position and OCR
> both genuinely work); `gemma3:4b`'s OCR verified live to be
> unreliable by contrast. `gemma4:26b` (MoE) and `qwen3:8b` identified
> as the next candidates worth testing, pending download.

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
audio capability, unlike Gemma 4's edge variants.

## 6. Verified `e4b`'s vision claim live — genuinely real, not just a label

Rather than trust `ollama show`'s capability tags (which didn't even
list "vision" for `e4b` despite it being real - see below), generated
two real test images locally with no external files and no AI involved
in creating them, then sent each directly through Ollama's own chat API:

- A raw-pixel PNG (left half solid red, right half solid blue): `e4b`
  correctly named both colors and which side each was on.
- A hand-drawn bitmap-font image reading "OCR42" (a manually-defined
  5×7 pixel font, no real font rendering, no antialiasing): `e4b` read
  it back exactly right.

The same two images sent to `gemma2:9b` were rejected outright by
Ollama itself - `"Multimodal data provided, but model does not support
multimodal requests"` (HTTP 400) - confirming it's genuinely text-only,
not just unlabeled either way.

`gemma3:4b` was checked the same way: the color/position test passed
correctly, but the OCR test did not - it read the "OCR42" image as "I I
D E S," a clear miss on the identical test `e4b` passed exactly.
Genuine vision, unreliable text-reading, at this smaller 4B tier.

Audio input couldn't be tested the same way: a real WAV tone generated
locally and sent via an `audios` field was silently ignored by Ollama
for both models (each replied as if no audio had been sent at all) -
litellm's own Ollama integration code has no audio-handling logic at
all, and Ollama's chat API has no documented audio parameter in this
version. This is a gap in Ollama's own API surface, not a verdict on
either model's underlying capability.

## 7. `gemma3:4b`'s battery numbers looked fine — until the raw text was read

The battery's raw pass counts for `gemma3:4b` looked reasonable at a
glance (5/5, 5/5, 4/5 across the checks). Reading the actual reply text
told a different story: in 4 of 5 trials, turn 1's reply began with the
exact swap-in message Sympose's own safety net (`_vault_ctx_title_missing`,
see the 2026-09-19/20 continuation-turn work) substitutes when it
discards a model's reply and shows the real note instead - "I couldn't
fully verify that against what's actually on file." That's the same
fresh-announcement failure mode `e4b` was originally caught on: naming
the note's title on the very turn it was introduced. The battery's own
`on_topic` check couldn't tell this apart from a genuine answer, because
the swapped-in raw note dump itself contains the same topic keywords a
real answer would.

**Fix, applied to the battery script itself:** added a `was_swapped()`
check for the exact swap-in lead-in text, and excluded that case from
`on_topic` rather than let it read as a pass. Sanity-checked against
`gemma2:9b` (already known to be genuinely clean) to confirm the new
check doesn't introduce a false positive there - 0/2 swapped, matching
the prior finding.

**Revised verdict:** `gemma3:4b` is not a clean pass, despite being a
newer generation than `gemma2:9b` - at this smaller 4B size it's
noticeably less reliable, closer to `e4b`'s known failure pattern than
to `gemma2:9b`'s genuinely clean run. Also showed unexplained
unprompted "updated private memory" badges on 3 of 5 turn-2 replies to
an ordinary follow-up question, and one fully empty completion.
`gemma2:9b` remains the validated candidate.

## 8. Next candidates identified, download interrupted by a transient network fault

Checked Gemma's own generational lineup directly rather than assumed:
neither Gemma 3 nor Gemma 4 has a 9B-class tag at all (Gemma 3: 270m,
1b, 4b, 12b, 27b; Gemma 4: e2b, e4b, 12b, 26b, 31b) - there's a real gap
between the small edge/lightweight tiers and the next dense tier in
both families. `gemma4:26b` stood out as worth testing specifically
because it's a Mixture-of-Experts model - 25.2B total parameters but
only 3.8B *active* per token, the same rough active-compute ballpark as
`e4b` (which stayed fast) rather than the dense `12b` tier (which
didn't). For Qwen, `qwen3:8b` was identified as the fair equivalent
weight class to `gemma2:9b` - dense, 8B, current generation.

Both downloads failed identically on the first attempt: a DNS lookup
failure on Ollama's own blob-storage host, confirmed transient (the
same host and general connectivity resolved fine moments later). A
retry then crawled at 439 KB/s (a 10+ hour ETA) instead of the ~15-25
MB/s every earlier pull achieved - abandoned rather than left running
blind. Both cancelled pulls left orphaned partial-blob fragments under
`~/.ollama/models/blobs/`; deleted only the fragments matching the two
incomplete downloads' own hashes (35 files, ~3GB), leaving the
legitimate installed models' blobs untouched. Downloads handed off to
be run manually outside this session; testing to resume once either
lands.

**Final verification:** every code change from this thread of work
(the `qwen2.5:14b` retargeting) re-run through the full test suite and
`ruff check`, both clean. The battery script's `was_swapped` fix is a
scratchpad tool change, not a Sympose code change, and needed no test
suite of its own - verified instead by the live sanity re-run above.
