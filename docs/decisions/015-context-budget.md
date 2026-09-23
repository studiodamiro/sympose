# 015 — Context budget: an overflowing prompt is cut silently, so the engine must size it

> **Scope of the measurements: Ollama and `gemma2:9b` only.** Every number below was measured on one runtime (Ollama 0.33.3) with one model (`gemma2:9b`, the default local model), at temperature 0, with synthetic chat turns. Other Ollama models, other Ollama versions (its default window and its truncation rule are Ollama's to change), and cloud models (which have their own, usually much larger, windows and their own overflow behavior, typically an error instead of a silent cut) were not measured. Treat the figures as the local default's behavior, not as a property of Sympose or of models in general, and re-measure before generalizing.

## Context

Nothing in the engine sets the model's window or checks that a prompt fits it. The prompt is the system prompt (soul, engine rules, the grounding block) followed by up to 20 turns of history (`session.history_as_messages`, a count and not a size) and the new message, and the reply must fit in the same window. Grounding passages (ADR 014) made the system prompt larger than the earlier one-line snippets, so this was measured before anything was built on top.

## Measured (Ollama 0.33.3, `gemma2:9b`)

**The window is 4096 tokens by default.** Ollama reports it in `ollama ps`; the model itself supports 8192, and Sympose never asks for more (no `num_ctx` is set anywhere). One token is roughly three quarters of an English word, so 4096 tokens is roughly 3,000 words.

**What the prompt costs.** The shipped soul plus the engine rules is about 450 tokens. Retrieved notes are part of that same system prompt and count toward the window: only passages are sent, never whole notes, each capped at 400 characters and carrying its title, path, and heading. Five passages of about 200 characters (what was measured) add about 280 tokens, roughly 55 each; at the 400-character maximum they add an estimated 450 to 550 (not measured), so the system prompt is about 730 tokens typically and up to roughly 1,000 in the worst case. The passages are not stored in the session history and are retrieved fresh each turn, so they do not accumulate across turns. That leaves about 2,700 to 3,000 tokens for history once room for the new message and the reply is set aside.

**How many turns fit** (with the typical 730-token system prompt; the worst case fits about 10 percent fewer; one turn is a user message plus a reply; the 20-turn history cap applies first for short chats):

| Reply length | Tokens per turn | Turns that fit |
|---|---|---|
| about 60 words | about 95 | 30 or more, so the cap of 20 applies and nothing overflows |
| about 120 words | about 160 | about 19 |
| about 200 words | about 240 | about 12 |

Measured directly with the real prompt builder and 20 turns: about 2,600 tokens at 60-word replies, 3,900 at 120 words (at the limit), 5,600 at 200 words (over it). Only three real replies existed to sample (average 15 words), too few to say what typical use looks like.

**An overflow is silent and not safe.** Beyond the window Ollama cuts the prompt without an error. A fact stated in the oldest turn was lost, and returned when the window was raised to 8192. The system prompt was not protected: at 56 turns it was partly gone (a "end every reply with a given word" rule stopped being followed and the model invented a detail), and at 70 turns it was entirely gone (asked to quote its instructions, the model quoted the chat). The soul and the engine's grounding rules live in the system prompt, so an overflow can silently remove the honesty rules.

**The reported token count cannot show an overflow.** Ollama's `prompt_eval_count`, which litellm returns as `prompt_tokens` on a streamed call when usage is requested, is the size after the cut: it stayed at about 4,070 to 4,090 or fell to about 2,050, never above the window. A meter fed only this number reads full or fine exactly when the prompt is being cut.

## Decision (direction agreed; design finished when built)

The engine sizes the prompt itself and never relies on the runtime's cut.

- **A window-size setting**, in `settings_store` like other user-facing defaults, passed to Ollama as `num_ctx`. Proposed default 8192 for local Ollama models (the model's native limit), at the cost of more memory; users on small machines can lower it. For cloud models the window is the provider's, not ours to set.
- **History trimmed by size, not by turn count**: oldest turns are dropped first, against the window minus the system prompt, the new message, and room for the reply, so the soul and rules are never what gets cut. The user is told when older turns are being left out.
- **A context meter** (percentage, CLI first; the web UI waits for the dashboard work) computed from the engine's own count of the full prompt, since the runtime's reported count is post-cut. Provider-reported usage is a cross-check where it is trustworthy, not the source.

Follow-up grounding (a separate slice, still to be recorded) adds a model call whose prompt also has to fit, which is why this comes first.

## Consequences

Not built yet; this record holds the measurements and the direction. Token counting for the engine's own count needs a method that is good enough for a percentage across models (an estimate with a safety margin is likely enough); that choice, and how the window is discovered for non-Ollama models, are to be settled when it is built and re-measured on more than one model.

## Alternatives rejected

- **Do nothing and rely on Ollama's default cut.** Rejected on the measurements above: it removes the oldest turns first and can remove the soul and the grounding rules, silently.
- **Only raise the window.** Delays the problem and costs memory for everyone, and a longer chat still reaches any fixed window.
- **Keep the 20-turn cap as the only guard.** A count is not a size; 20 long turns overflow, 20 short ones leave most of the window unused.
- **Read the runtime's token count for the meter.** It is post-cut and cannot show the overflow it is meant to warn about.
