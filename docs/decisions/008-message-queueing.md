# 008 — Message queueing: per-persona locks, not one global lock

## Context

`docs/VISION.md` names message queueing as an engine-level requirement, not
just a UI nicety: the composer must never lock while a persona is replying,
and a message sent mid-turn must be queued and handed to the persona at her
next natural checkpoint — never force-interrupted mid-generation, never
silently dropped.

`sympose/engine/turn.py`'s docstring (written in ADR 006) had gestured at a
seam for this: the point between `call_model` returning and `append_turn`
persisting, "where a later queueing milestone would check for newly-arrived
input before finalizing a turn." That seam turns out not to be the right
hook. `call_model` (ADR 007) is a single blocking, non-streaming litellm
call — there is no in-progress generation to check anything against
mid-flight, only a call that's either still running or already returned.
"Absorb new input while still running" given that constraint can only mean:
the composer keeps accepting input, and a message sent while a turn is in
flight is queued and run as its own subsequent turn once the current one
finishes — not merged into it, not steering it.

ADR 006 already left most of the CLI-side groundwork in place, as an
accidental safety fix rather than the real feature: `app.turn_lock` (a
single global `asyncio.Lock`) already serializes engine calls so the
composer never blocks, but ADR 006 explicitly named three gaps this milestone
has to close: no UI indication that a message is queued; a real bug where a
second queued message for the same persona can orphan onto a fresh session
if the user switches personas away-and-back while it's waiting; and a shared
single-slot reply timer (`app.reply_timer`) that a second overlapping
stream would clobber.

A first design pass proposed keeping `app.turn_lock` as one global lock,
reasoning that `sympose/engine/session.py`'s un-hardened read-modify-write
isn't safe against two concurrent writers. That reasoning didn't hold up
under review: sessions are stored one file per persona per conversation
(`sessions/<handle>/<session_id>.jsonl`) — the same shape as Slack threads,
each persona/thread isolated in its own file. Two different personas' turns
never touch the same file and never actually race each other; a global lock
was serializing work that was never going to collide.

## Decision

Replace the single `app.turn_lock` with one lock per persona handle
(`app.turn_locks: dict[str, asyncio.Lock]`, created on first use). Turns for
the *same* persona still queue strictly in submission order — same session
file, must stay serialized, exactly the guarantee the old global lock
provided for that case. Turns for *different* personas can now run
concurrently — different files, no collision — and since every reply is
already labeled `@handle · model` in the transcript, two personas replying
around the same time is never ambiguous about who said what.

Sequenced work:

- **CLI mechanical split** — `sympose/cli/runtime.py` was already past this
  repo's 200-LOC guideline (ADR 006 flagged the split as deferred); this
  milestone's logic lands in a new `sympose/cli/turns.py`
  (`_ENGINE_EXECUTOR`, `_force_exit`, `_show_failure`, `send_message`,
  `_stream_reply`), leaving `runtime.py` with `run_command`/
  `apply_picker_choice`.
- **Session continuity** — the orphaning bug's root cause was
  `send_message` reading `app.session_id` live, at the moment a queued call
  finally starts, which an intervening persona switch-away-and-back could
  have reset even though that reset had nothing to do with the queued
  call's own lineage. Fixed with `app.session_by_generation: dict[int, str
  | None]`, keyed by the same `session_generation` counter ADR 006 already
  introduced for stale-write detection. `send_message` still captures
  `handle`/`model_id`/`generation` before acquiring its persona's lock (
  unchanged from ADR 006's pattern), but `session_id` is resolved from this
  dict *inside* the lock, immediately before dispatch — so a same-generation,
  same-persona predecessor's result is always visible to whatever queues
  behind it, regardless of how many *other* generations were bumped by
  unrelated persona switches in between. This reduces to ADR 006's existing
  single-slot behavior whenever only one generation is ever in play, so
  every existing persona-switch regression test still holds.
- **Queued indicator** — the already-mounted "You" transcript line is
  updated in place with a dim "· queued" suffix while its persona's lock is
  held, cleared once the turn actually starts. Deliberately not a new
  system-speaker transcript line: `sympose/cli/transcript.py`'s
  `_CHAT_SPEAKERS`-gated turn-gap grouping only tracks user/persona
  speakers, and a system line in between would desync the next chat line's
  expected spacing.
- **Reply-timer isolation** — `app.reply_timer` (a single slot) becomes
  `app.active_reply_timers: set`, since two personas' replies (or two
  queued same-persona replies processed back-to-back) can now genuinely
  stream at once post-lock. `/clear` stops and clears every active timer,
  not one slot.
- **Dispatch via a background worker, not a direct `await`** —
  `sympose/cli/dispatch.py`'s `on_input_submitted` now calls
  `app.run_worker(turns.send_message(app, value), group="chat-turn")`
  instead of `await turns.send_message(app, value)`. Caught by live
  verification, not code review: everything above this point was correct
  and fully covered by tests that call `turns.send_message` directly, but
  none of those tests exercise the actual dispatch path a real keypress
  takes. A `tmux` session sending two real messages back to back showed the
  second's transcript line never appearing until the first's reply had
  already fully rendered — no "queued" marker ever visible. A follow-up
  diagnostic (posting two `Input.Submitted` messages directly, no key-press
  simulation noise) confirmed why: Textual's `App` fully awaits one bubbled
  message's handler before it even looks at the next one in its queue.
  Since `on_input_submitted` used to `await` the entire turn (mount, lock,
  the engine call) inline, a second real Enter press couldn't even be
  *received* by `send_message` until the first had completely finished —
  the per-persona lock this record designed was correct but unreachable,
  since two `send_message` calls could never actually be in flight at the
  same time through that path. Dispatching via `app.run_worker` instead
  (`exclusive=False` — turns must be able to run concurrently across
  personas or queue on their own per-persona lock, never cancel each
  other) frees the App's message queue immediately, so a second keypress is
  received and dispatched right away. This is also what ADR 006's own
  Consequences section had already flagged, for different reasons, as "what
  Textual's own worker API is purpose-built for" — the hand-rolled
  `turn_locks`/`session_generation`/`app._exit` guards didn't need to
  change at all; they were already built to tolerate exactly this kind of
  overlap, they just needed the overlap to be reachable.
- **`action_quit` checks a `pending_turns` counter, not lock state** —
  caught by `/code-review`, not live testing: `Lock.locked()` is a
  point-in-time snapshot. `asyncio.Lock.release()` sets its internal
  `_locked` flag to `False` and *schedules* the next waiter to resume on a
  later event-loop tick, rather than handing off atomically — so between
  one queued call releasing its persona's lock and the next one actually
  resuming to re-acquire it, `lock.locked()` genuinely reads `False` for a
  moment, even though a second call is guaranteed to grab it immediately
  after. In that narrow window, `/quit` could have read "nothing's
  in flight," taken the graceful `self.exit()` path, and let the second,
  still-queued call go on to make its own genuinely blocking, uncancellable
  engine call — reproducing the exact hang `_force_exit` exists to prevent.
  Fixed with `app.pending_turns: int`, incremented the instant
  `send_message` starts and decremented only once it's fully done
  (`try`/`finally`, covering queued time and in-flight time alike, with no
  release/reacquire gap for `action_quit` to catch). `turn_locks` is
  unchanged and still the actual serialization primitive — this only
  changes what `/quit` checks to decide whether one is genuinely needed.

## Consequences

`sympose/engine/turn.py` and `sympose/engine/session.py` need no functional
change — queueing is entirely a CLI call-site concern, wrapping `run_turn`
rather than reaching inside it. Both modules' docstrings are updated to stop
pointing at the now-unused seam and to state the real concurrency guarantee
(one turn per persona at a time, not one turn process-wide) that keeps
`session.py`'s unlocked read-modify-write safe.

The worker-based dispatch fix turned out to need no test-suite-wide rewrite:
every existing test that submits a chat message via `pilot.press` and then
`pilot.pause()` continued to pass unmodified — `pilot.pause()`'s
CPU-idle-detection wait (Textual's own `wait_for_idle`, up to a 1-second
window) already reliably captures a single worker's completion in practice.
The one place this needed care was the new
`test_queued_marker_is_reachable_through_a_real_second_keypress`, which
calls `app.workers.wait_for_complete()` directly — that resolves the instant
both `send_message` calls *return*, which is before `_stream_reply`'s
word-by-word reveal timer has had any wall-clock time to fire even once;
`pilot.pause()` right after that exact point isn't reliable, since
"CPU-idle" and "hasn't started a still-pending 0.05s timer yet" can look the
same to that heuristic. Fixed with a short explicit `asyncio.sleep` instead
of `pilot.pause()` for that one assertion, not a general pattern applied
everywhere else.

`test_concurrent_sends_do_not_race_the_engine_call`'s original docstring
claimed calling `send_message` directly was necessary because "`pilot.press`
/`pilot.pause` wait for pending work to settle, which the second call can't
do while genuinely blocked behind the first." That claim was accurate
against the pre-fix code and is no longer true — updated to point at the new
real-keypress test instead, rather than leaving a stale, now-misleading
rationale in place.

The one deliberately deferred question from this milestone: should a
message queued for the *same* persona ever jump ahead of what's already
queued (e.g. a `/clear` or a priority signal)? Nothing in `VISION.md` or
current use asks for this, and FIFO-per-persona is the simplest thing that
satisfies "not silently dropped, not force-interrupted." Revisit only if
real use shows strict FIFO isn't the right order.

**Known, deliberately-not-fixed gap surfaced by `/code-review`:**
`app.session_by_generation` gains one entry every time a turn completes and
is never pruned, so it grows for the process's whole lifetime as the user
switches personas (each switch bumps `session_generation`). Left as-is: a
CLI process is typically restarted often, not run for weeks, and each entry
is a tiny int-keyed string — this would take an implausible number of
persona switches in one sitting to matter. `turn_locks` doesn't have the
same growth (bounded by the small, fixed set of persona handles), so this
is specific to the generation counter's own design, not the locks. Revisit
only if a genuinely long-running CLI process makes this cost real.

A second `/code-review` round raised, then itself flagged as low-confidence,
a narrower theoretical gap in the `pending_turns` fix: `app.run_worker(...)`
creates the underlying `asyncio.Task` synchronously (via `asyncio.create_task`
inside `Worker._start`), but that task's first line — `pending_turns += 1`
— doesn't actually run until the event loop gets to it, one `call_soon` step
later. In principle, a `/quit` dispatched in that exact gap would still see
`pending_turns == 0`. Traced through and accepted as not practically
reachable: `create_task` schedules that first step on the event loop's
ready-callback queue immediately, before the loop goes back to waiting on
real I/O — and a genuine second keypress can only be *posted* once the
corresponding terminal input event actually arrives, which happens after
the loop has already worked through its current ready-callback queue,
including that first step. Hitting the gap would require two messages
already dispatched within the very same synchronous scheduling batch, which
only a diagnostic posting `Input.Submitted` messages back-to-back with no
yield between them (not real keypresses) can construct — not a shape a
human typing produces.

## Alternatives rejected

- **One global `asyncio.Lock` for all personas.** The original draft of
  this design — rejected once the actual session-file partitioning
  (per-handle, per-session-id) was checked: it serializes work that never
  collides, for no correctness benefit over a per-persona lock.
- **A `dict[(handle, session_id), asyncio.Lock]`, finer than per-handle.**
  Rejected as unnecessary complexity: the CLI only ever has one active
  session per persona handle within a process run (a persona switch resets
  `session_id` rather than juggling multiple concurrent sessions for the
  same persona), so per-handle is already the real collision boundary — a
  finer key would add lock-lifecycle bookkeeping for a case that can't
  currently occur.
- **Hooking queueing logic into `run_turn`'s "seam"** (checking for
  newly-arrived input between the model call returning and the turn
  persisting). Rejected because `call_model` is a single blocking,
  non-streaming call — there's no in-progress generation to check against
  mid-flight, so the seam has nothing to hook into; the CLI call site
  already knows everything it needs (whether another message queued behind
  this one) without the engine needing to know about queueing at all.

**Update (#65):** `_force_exit` was removed, so where this record says a quit with a call pending calls it, the quit now takes the normal `self.exit()` path and `main()` ends the process; see the update at the end of ADR 006. `pending_turns` is still what marks a message as queued.
