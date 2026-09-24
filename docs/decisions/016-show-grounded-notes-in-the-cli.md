# 016 — Show which notes grounded a reply, in the CLI reply header

## Context

Grounding (ADR 014) decides which passages of the user's notes reach the model each turn, and the user could not see that decision. That hides which note the model was handed (a wrong note attached to a follow-up is invisible until the answer is wrong). `run_turn`'s result already carries the grounding hits and the CLI already builds a header per reply (ADR 013 put the model and TTFT there), so this needs no engine change. The measurements that motivated the surrounding work (ADR 015) were taken on Ollama and `gemma2:9b` only; this display is model-independent.

## Decision

The reply header gains one more segment after the TTFT: `@samantha · Gemma2:9b · TTFT 0.8s · from Projects/Atlas.md +2`.

- **What it shows.** The note of the top-ranked passage, and `+N` for the number of other distinct notes grounded on. When nothing matched (including when no vault is configured) the segment is left out entirely. A `no notes` label was built first and removed on review: it reads as a claim about the user's vault, when in most such turns the message simply was not about a note, and when it was about one and nothing was found the reply itself says so.
- **Fitting the line.** The path is cut from the front with an ellipsis only when it does not fit the terminal's remaining width (measured in terminal cells, not characters, since a CJK or emoji filename takes two cells per character), so the filename, the part that identifies the note, is what stays visible: `from …ects/Atlas.md +2`. A path that fits is shown whole. The room is computed from the terminal width at render time; a floor (the whole filename, at most 32 cells, and never under 8) keeps a very narrow terminal from cutting the path to nothing. Below that floor the header runs over and wraps rather than losing the filename; that was a deliberate choice, and dropping the segment in a terminal too narrow for it is the alternative if wrapping proves ugly in use.
- **A knob.** The `show_grounding` setting in `settings_store` (a user-facing default belongs in settings, not a constant), on by default, toggled from the CLI with `/grounding`. Only an explicit `false` turns it off, so a hand-edited or malformed value never silently hides it.
- **Display only.** The header is not stored in the session record and does not change what the model sees. It is not colored differently from the rest of the header: the header is one styled string today, and splitting its styles is a larger change than this needs.

Later slices reuse the same segment: when follow-up grounding rewrites a query, the rewritten query is shown here so a wrong rewrite is visible.

## Consequences

The path is fitted once, when the reply lands, against the terminal's width at that moment and a fixed 4-cell margin for the transcript's own padding: resizing the window afterwards re-wraps the header text but does not re-fit the path, and a change to the transcript's CSS margins would need the margin constant to follow. The display is best-effort and never costs a reply: a hit without a path is skipped. The header is longer, which is why it is fitted to the width and can be turned off. It shows the top note and a count, not every note or the passage text, on purpose: one line beside a reply is a signal, and the full set is a possible later view (the dashboard, or a command that lists the last turn's passages). Only the top note is named, so a reply grounded on several notes shows one path and `+N`; which of the others were used is not visible yet.

## Not built yet

- **The full set of grounded notes.** Only the top note and a count are shown; a command or a dashboard view that lists the last turn's passages (title, path, text, as the search bar does) is a possible later addition.
- **Dim or separate styling for the segment.** The header is one styled string; splitting its styles is a larger change.
- **Refitting on resize.** The path is fitted once when the reply lands.
- **The rewritten query.** When follow-up grounding rewrites a query (ADR 017), it is to be shown in this same segment so a wrong rewrite is visible; not built.
- **A grounded-note view in the web dashboard.** Waits for the dashboard's chat panel.

## Alternatives rejected

- **A separate line under the header.** Rejected for now: it doubles the vertical space per reply, and the header line has the room when fitted to width.
- **Showing the passage text.** Too long for a line beside a reply; the search bar's result list already shows that shape, and a condensed version of it is what this line is.
- **Always on, no knob.** Rejected: some users will find it noise once they trust the setup.
- **Storing the display string in the session record.** Rejected: the record already keeps the turn; the grounding hits are recomputable from the vault and are not part of what the user said or the model replied. (The premise did not hold up, since the vault and the retriever change: the notes are now recorded, as paths, not as this string; see ADR 025.)
