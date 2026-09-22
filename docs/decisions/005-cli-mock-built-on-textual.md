# 005 — CLI mock built on Textual, not `prompt_toolkit`

## Context

The CLI channel needs a persistent, always-live input line that stays
typeable while a reply streams into the transcript above it — the thing
legacy's `rich.prompt.Prompt`-based loop couldn't do, since `Prompt.ask`
blocks the whole thread until Enter is pressed (`docs/VISION.md`,
lines 46-50, already named this as the reason a full CLI rewrite would
need a different input model). This first pass is a presentational mock
only — canned replies, no `PersonaEngine` wired in — built to preview
that interaction before the engine exists. `VISION.md` named two
candidates for the underlying toolkit: `prompt_toolkit` and Textual.

## Decision

Built on Textual (`textual>=0.60.0`, `pyproject.toml`'s main
`dependencies`, not `dev` — it ships as part of the real CLI entry
point, same tier as `fastapi`/`uvicorn`). Textual owns the whole
terminal surface as a widget tree with its own event loop, so the
persistent `Input`, the scrolling transcript, and the boxed/numbered
selection panels are all just widgets composed together, each with
async access to the same app state.

## Consequences

Textual pulls in `rich` transitively (already a `fastapi`-adjacent
ecosystem package, not new surface). The whole terminal is now owned by
Textual's render loop rather than plain stdout writes, which is a bigger
footprint than the minimal blocking CLI (`docs/CHECKLIST.md`'s separate
"CLI — minimal" item) needs — that one stays a plain blocking loop
calling the engine directly, deliberately not built on Textual, so a
lightweight scripted/piped use of the CLI never has to pull in a full
TUI framework. Digit-key selection and other keybindings are scoped to
whichever widget currently holds focus, which is Textual's own focus
model rather than anything hand-rolled — verified live that a picker's
digit keys only fire while the picker itself is focused, and type
literally into the input otherwise.

## Alternatives rejected

- **`prompt_toolkit`.** The other candidate `VISION.md` already named.
  Lighter-weight (no full-screen widget tree, no owned render loop) and
  would have been enough for a single persistent input line with a
  separate print-based transcript. Rejected in favor of Textual because
  the numbered/boxed/color-coded selection panel is reused across four
  call sites (the `/`-autocomplete overlay, and the `/model`, `/persona`,
  `/history` pickers) and benefits from being a real, composable widget
  with its own focus-scoped key bindings and CSS-driven styling —
  `prompt_toolkit` would mean hand-rolling that widget's layout, focus
  handling, and theming from lower-level primitives instead of getting
  them from a widget framework built for exactly this.
- **Keep legacy's blocking `rich.prompt.Prompt` loop and defer the real
  fix.** Rejected outright: it's the specific limitation this mock exists
  to move past, and `VISION.md` already ruled it out for the target
  experience.
