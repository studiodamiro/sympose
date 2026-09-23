# 013 — Record time-to-first-token on every turn

## Context

Latency is central to Sympose's promise of a cheap, fast local companion, and the choices ahead (which local model to recommend, whether a bigger soul or more grounding is affordable, when to add round-trips) all trade against it. Today nothing is measured. The obvious number is time to first token (TTFT): how long the user waits before the reply starts, which is what a person actually feels, and which, unlike total time, does not grow with how long the answer is. `call_model` is deliberately non-streaming (ADR 007: the CLI animates a complete reply client-side, so token streaming was not needed), and a non-streaming call has no "first token" moment to time; the only number available would be total generation time, a different quantity that mostly measures reply length.

## Decision

**Stream the model call internally, still return the complete reply.** `call_model` requests a streamed response and joins the chunks into the same full string callers always got; the CLI still animates that string exactly as before. The only change visible outside `engine/model.py` is that it returns a small `ModelReply(text, ttft_ms)` instead of a bare string.

**What is measured.** TTFT is the time from just before the request is sent to the first piece of *reply* text. A reasoning model's thinking is deliberately not counted: it is not what the user is waiting to read, and counting it would make a model that thinks for twenty seconds look as responsive as one that answers at once. It therefore includes everything the user waits through: connecting, processing the prompt, any thinking, and, for a local model that is not already loaded, loading it. A cold first turn showing a long TTFT is the real experience, not noise to filter out. It is stored as whole milliseconds (`ttft_ms`).

**Where it is recorded.** Every turn record in the session JSONL gains `ttft_ms` and `model` (the model that actually ran, after the precedence in ADR 010). The model is recorded because a latency number is meaningless without knowing what produced it, which is exactly what a later comparison across models needs. Older records lack both fields and every reader tolerates that. `run_turn`'s result carries both. A failed model call records nothing, since there is no turn.

**Where it is shown.** The CLI's reply header shows it beside the model: `@samantha · Gemma2:9b · TTFT 0.8s` (milliseconds under one second, one decimal of seconds above). The dashboard is out of scope until its chat panel is wired to the engine.

## Consequences

The model call now depends on litellm's streaming path, so failures can surface mid-stream; they are wrapped in the same `EngineModelError` as before, and an empty stream is still an error. A stream that ends without a finish signal (a connection closed cleanly mid-generation) is also an error, so a cut-off reply is never saved as a whole one, which the old non-streaming call guaranteed by raising; verified that a real Ollama stream ends with `finish_reason: stop`. The 120-second timeout now bounds how long the model may go silent, not the whole turn, since a slow model that keeps producing text should not be killed. Only time to first token is recorded, not total duration; total is a one-field addition later if wanted. Because output varies with the model and the machine, single numbers are noisy; the value is in the accumulated history, which is what the session record provides. ADR 007's "non-streaming" statement is superseded in its mechanics only: the reply the rest of the system sees is unchanged.

## Alternatives rejected

- **Timing the whole non-streaming call and calling it latency.** Rejected: it is total generation time, dominated by reply length, and says nothing about how responsive the model feels.
- **Streaming tokens through to the UI** so the reply appears as it is generated. Rejected here as a separate feature: it changes the CLI's rendering and the queueing model (ADR 008), and TTFT does not need it.
- **A separate metrics file.** Rejected: the session record is where the turn already lives, is what the request asked for, and keeps a measurement next to the exchange it measures.
- **Recording only the number, without the model.** Rejected: it could not be compared across models later.
