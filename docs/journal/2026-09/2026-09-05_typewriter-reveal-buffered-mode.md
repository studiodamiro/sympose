---
entry: 2026-09-05
created: 2026-09-05 05:40
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/ui
---

# Sympose Engineering Log: Typewriter Reveal for `buffered` Render Mode

> **Date:** Friday, September 5, 2026
> **Topic:** Animating the completed reply into view instead of dumping it
> all at once, in `buffered` render mode
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Implemented, tested, verified visually in a real terminal.

---

## 1. The observation

Following up on the [animated thinking status](./2026-09-05_animated-thinking-status.md),
damiro asked whether the reply text itself could animate in "like by the
letter" — the kind of typewriter reveal other AI chat products use — while
wondering out loud what animation is even possible in a plain terminal.

The answer is that `buffered` mode (damiro's own `config.yaml` setting,
ADR-060's "visual polish" option) is exactly where this matters: `hybrid`
and `raw` modes already write each stream chunk to stdout as it arrives, so
they already look "animated" — that's real token streaming, not a visual
effect. `buffered` mode instead holds the whole reply in `buffered_chunks`
until the stream ends, then renders it as Markdown in one `console.print()`
call. That single instant dump, right after the spinner stops, is what read
as "did it just sit there and then dump everything."

## 2. What shipped

- **`sympose/ui.py`**: new `TerminalUI.render_markdown_typewriter()` reveals
  the completed reply progressively through `rich.live.Live`, re-rendering
  the growing Markdown prefix in a handful of chunks (capped at 120 steps,
  regardless of reply length) rather than reprinting raw text — headers,
  bold, links, and bullets resolve correctly as they're revealed, the same
  as the instant `render_markdown()` path.
  - **Bounded to a fixed `duration` (1.4s) no matter the reply length**: a
    long reply doesn't typewriter proportionally slower than a short one.
    Uses a wall-clock deadline schedule per step (`start + (step/steps) *
    duration`) rather than a fixed per-step sleep — a fixed sleep drifted
    past the nominal duration by ~30% on longer replies once each step's
    own Markdown-parse/diff overhead is accounted for.
  - **Defensive fallbacks to the existing instant `render_markdown()`**:
    replies under 24 characters (nothing worth animating), non-terminal
    output (`console.is_terminal` false — piped/redirected stdout, matching
    `raw` mode's existing "debugging, piping, transparency" purpose), or if
    `Live`/`Markdown` aren't importable. The animation is cosmetic, never a
    dependency for getting the reply onto the screen.
  - `KeyboardInterrupt` propagates rather than being swallowed by the
    method's own fallback exception handling, so Ctrl+C mid-reveal still
    reaches `cli.py`'s existing interrupt handler.
- **`sympose/cli.py`**: the `buffered`-mode final render call switched from
  `render_markdown` to `render_markdown_typewriter`. `hybrid`/`raw` modes
  untouched — they already stream live.

No new dependency (`rich.live.Live` ships with `rich`, already a
dependency) and no new config key — the duration is a fixed, sensible
default rather than another knob, consistent with the Zero-Maintenance
Mandate for a purely cosmetic feature.

## 3. Verification

- 4 new tests in `tests/unit/test_ui.py`: short replies and non-terminal
  consoles skip the animation and return near-instantly; a long reply
  (~7,500 characters) stays well under a generous ceiling instead of
  scaling with length; a `KeyboardInterrupt` raised mid-reveal propagates
  rather than being caught by the method's own exception fallback.
- Ran it directly against a `force_terminal=True` console with mixed
  Markdown (headers, bold, italic, a link, a bullet list) and watched every
  element resolve correctly as it was revealed; separately timed a ~4,800
  and a ~75-character reply against the same `duration` and confirmed both
  land within ~20ms of the target instead of the long reply overrunning it.
- `.venv/bin/pytest` — 151/151 (147 prior + 4 new).

## 4. Why no ADR

Same reasoning as the animated thinking status: presentation-only, no
architectural trade-off, trivially reversible, drop-in call-site swap.
Journaled per the documentation standard.
