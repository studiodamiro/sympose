# 018 — A context meter under the chat box

> **Scope: the counting is the engine's own estimate (ADR 015), measured against Ollama's real counts on `gemma2:9b` only** (prose under-counted by 2 to 4 percent, code by 12, Japanese over-counted by 64, before the 15 percent safety margin). So the percentage is an estimate that leans high, and how close it is on cloud models and other local models is unmeasured.

## Context

ADR 015 made the engine fit every prompt to the model's window, dropping the oldest turns and then the weakest grounding passages when it does not fit, and the header says so after the fact (`3 older turns out of context`). What the user still cannot see is how close a conversation is to that point before it happens. The runtime's own token count cannot show it, because it is measured after the runtime has cut an overflowing prompt (ADR 015). The engine's own count is taken before the call, so it can.

## Decision

**A one-line meter under the chat box:** `context ██████░░░░ 62%`, dim, in the line the composer already leaves free below it, so the screen does not grow.

- **What 100% means.** The share of the *prompt budget* in use: the window minus the room kept for the reply (ADR 015). At 100% the next turn starts leaving older turns out, so the number answers "how long until it forgets", not "how full is the raw window" (which could never reach 100% because the reply room is always reserved). The bar and the percentage never exceed 100: once trimming has started the header's notice says how much was left out.
- **Rounding.** To the nearest whole percent, except that a hair under the budget reads 99: 100 means the budget is reached (the next turn may start dropping), so it is never shown while there is still room.
- **What is counted.** The prompt the model was sent on the last turn (soul, rules, grounding, the kept history, the message) plus the reply it wrote, counted by the same function and with the same 15 percent margin as the fitting (`budget.count_tokens`), so the meter and the trimming can never disagree. It is the size of the conversation as the next turn will start from it, plus that turn's own grounding block (which does not carry over), so it leans slightly high. The engine returns it on the turn result as the tokens used and the budget it was measured against; nothing is stored in the session record.
- **When it is shown.** After each reply, for the conversation in front of the user. It is empty before the first reply of a chat (nothing was sent, and the model's window may not even be looked up yet), and it is cleared when the persona or the model is switched, since the number belongs to the previous model's window, and comes back with the next reply. A turn that fails leaves it as it was. A reply that was already being produced when the model or persona was switched is ignored when it lands (each reset bumps a counter the reply captured when it was sent), so an old model's percentage never shows against the new window. It is not shown when the model's window is unknown (then nothing is trimmed either).
- **Colour.** The theme's own colours: normal below 70%, warning from 70%, error from 90%.
- **A knob.** `show_context_meter` in the settings file, on by default, only an explicit `false` turns it off (the same rule as the other display knobs). No slash command for it: there is no settings screen yet and one command per knob does not scale.
- **Where the code lives.** `cli/meter.py` holds the widget, the formatting and the knob; `turns.py` hands it the turn result. The web dashboard's version waits for the dashboard's chat panel, and reuses the same two numbers from the result.

## Checked

Live on `gemma2:9b` through the real CLI with a 1024-token window (prompt budget 768): five turns showed 44%, 47%, 46%, 56% and 76%, the second and fifth beside a follow-up rewrite (ADR 017). Turn 3 reads a point lower than turn 2 because turn 2 carried a grounding block that does not carry over. The meter sits on the screen's last row directly under the composer with the composer's total height unchanged. Counting the reply adds about 0.3 ms per 1,500 words. Not measured: how close the percentage is to the real prompt on cloud models and other local models.

## Consequences

The number is an estimate that leans high (the margin), so a conversation can look nearly full while the model still has room; that is the safe direction, since the failure it warns about is silent loss. It moves in steps, once per turn, not while typing: the size of a message being written is not counted until it is sent. After a model switch it is blank until the next reply, not recomputed for the new window. A long conversation on a large window climbs slowly, so most short chats will show a small percentage most of the time; that is the honest picture.

## Not built yet

- Counting the message being typed.
- Recomputing the number for the new window right after a model switch, instead of blanking it.
- Showing raw token counts (`3.8k of 6.1k`) beside the percentage, and a command that explains the number.
- The web dashboard's meter.
- Restoring the meter when a saved session is resumed (it appears after the first reply).

## Alternatives rejected

- **The runtime's reported prompt token count.** Post-cut: it can never show the overflow the meter is for (ADR 015).
- **A percentage of the raw window.** It tops out at the reserve line and would show 75 percent for a conversation that is already dropping turns.
- **Counting the typed message live.** A token count on every keystroke, for a number that only matters once the message is sent.
- **A status bar or header line instead of under the composer.** The header already carries per-reply facts (TTFT, notes, trim notice), which is what fills its width; the meter describes the conversation, not one reply, so it sits by the box the user types into.
