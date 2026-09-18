---
entry: 2026-09-19
created: 2026-09-19 01:10
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/grounding
  - sympose/reliability
  - model-routing
---

# Sympose Engineering Log: A Live "Vault Roulette" Lapse That Didn't Reproduce, and a Dormant Feature It Surfaced Along the Way

> **Date:** Saturday, September 19, 2026
> **Topic:** damiro shared a live transcript where Samantha, manually
> overridden to `ollama/gemma4:e4b` and freshly `/reset`, had no idea what
> "our favorite game" (Vault Roulette, a random-note-pull ritual - see the
> [2026-09-17 fix](./2026-09-17_ritual-continuation-carries-no-grounding.md))
> was, twice in a row, even after being directly reminded. Investigating
> it did not find a code bug - but it surfaced a real, separate gap: a
> built local/cloud model-routing feature ([ADR-122](./2026-09-14_adr-122-local-cloud-model-complexity-routing.md))
> that no persona has ever actually used, and that a new user has no way
> to discover.
> **Status:** No bug found in the ritual mechanism (see §1). A real
> discoverability gap found and documented (see §2) - not yet fixed.

## 1. The live lapse: investigated, not reproduced

Traced the full mechanism by hand first, against damiro's real profile
files (`~/.sympose/profiles/samantha_memory.md`, real `~/.sympose/config.yaml`):

- `ProfileManager.find_relevant_memory_fact` correctly matched both of
  damiro's messages ("lets play our favorite game" and "dont you remember
  our favorite game?") to the real memory bullet ("Damiro's favorite game
  is 'Vault Roulette'...") - confirmed programmatically, not assumed.
- `VaultManager.describes_random_pull_ritual` correctly recognized that
  bullet as describing the random-pull ritual.
- `_ritual_pull_due` correctly returned `True` for both turns.
- `/reset`'s own `reset_history` correctly clears `active_vault_ctx` and
  `active_ritual` (checked directly in `engine.py`) - no stale carry-over
  state from before the reset was possible.

Every structural/mechanical piece checked out correct. Reproduced the
exact scenario end-to-end against the real local model, real vault, real
memory file, 3 full times (6 real `ollama/gemma4:e4b` calls) - the memory
fact and a real pulled note (`Movies/Her.md`) were injected every single
time, and the model correctly referenced "Vault Roulette" and the real
note in all 6 replies. No failure reproduced.

Also ruled out, directly:

- **Stale install.** Diffed `engine_turn_setup.py`, `engine_grounding.py`,
  and `profiles.py` between the dev checkout and the actual pipx-installed
  package (`~/Library/Application Support/pipx/venvs/sympose`) -
  byte-identical.
- **Different Ollama.** Confirmed a single `ollama serve` process on the
  machine, no `OLLAMA_HOST`/`api_base` override anywhere - both the live
  session and this investigation hit the same server and the same
  downloaded `gemma4:e4b` model file.

**Conclusion:** most likely a genuine local-model sampling lapse rather
than a reproducible defect - damiro's live transcript also showed markedly
slower response times (38.72s/31.12s TTFT) than any of the 6 clean
reproductions here, consistent with the local model being under load at
that moment. Recorded as a known, accepted risk of manually overriding to
a small local model - not something this investigation found a fix for,
because nothing broken was found to fix.

## 2. What the investigation surfaced instead: ADR-122 is real, but dormant and invisible

Working through "isn't Sympose local-first, though?" during this
discussion led to actually reading `model_router.py` and
`engine.py::_select_turn_model` end to end, rather than assuming ADR-122's
design intent was what shipped. Findings:

- **The mechanism is real and correctly wired.** `is_simple_message`
  (length + keyword/pattern check) and `resolve_turn_model` are exactly as
  ADR-122 describes, called from `chat_stream` on every turn.
- **It requires a persona to have a *second*, distinct `local_model` field
  set alongside their main `model`.** Checked all three of damiro's real
  profiles directly - none has one. The feature has been fully built and
  wired since 2026-09-14 and has never actually routed a single message
  for any persona on this install.
- **It does not apply to Samantha at all, structurally, regardless of
  configuration.** Her own `model` field is already `ollama/gemma4:e4b` -
  she isn't a cloud persona with an occasional cheap local shortcut, she's
  a local persona outright. `_select_turn_model`'s own first guard
  (`not local_model`) means this routing logic never engages for her.
  ADR-122's own `local_model` setting description already says as much
  ("Meaningless (leave unset) for a persona whose `model` is already
  local") - this was already documented correctly, just not connected to
  Samantha's specific case until now.
- **What actually protects a local-default persona instead:**
  `_grounding_mode` returns `"strict"` for any local backend - the
  runtime enforces vault retrieval itself deterministically rather than
  trusting the model to decide when to ask for it, plus the post-
  generation citation checks (`_vault_ctx_title_missing`, fixed earlier
  today - see [2026-09-18_folder-digest-answers-wrongly-caught-by-title-citation-guard.md](./2026-09-18_folder-digest-answers-wrongly-caught-by-title-citation-guard.md)).
  That's a different kind of protection than ADR-122's model-selection
  routing - it doesn't change which model answers, it changes how much
  the runtime double-checks whichever model does.
- **It is, however, already a fully working, discoverable *knob* - this
  session got that wrong on the first pass.** `/persona show @<handle>`
  lists `local_model` with its full description and current value, and
  `/persona set @<handle> local_model <value>` writes it - both already
  implemented (`commands.py::_cmd_persona`). The initial claim in this
  conversation that "there's no CLI path, only hand-editing YAML" was
  incorrect and was corrected live once `/persona`, not just `/config`,
  was actually checked.

**The real, still-open gap:** nothing surfaces this knob to a user who
doesn't already know to run `/persona show`. `bootstrap.py`'s persona-
creation flow never mentions it, and no wiki page does either. ADR-122's
own Follow-ups section already flagged "pick the actual per-persona
values... when implementation starts" as unresolved - this adds the
missing half of that: even once someone *does* pick values, nothing in
the product would ever prompt them to.

## 3. Follow-ups (added to ADR-122's own tracked list, not resolved here)

- Add a mention of `local_model`/`/persona show` to `bootstrap.py`'s
  persona-creation flow, for any persona whose `model` is cloud.
- A short wiki page (or a section in an existing one) documenting
  `/persona show`/`/persona set` and what `local_model` actually does,
  since currently the only place this is explained at all is inline
  `Setting` descriptions in `config_schema.py`.
- ADR-122's per-persona `local_model` values still haven't been picked for
  any of damiro's cloud-default personas (Grace) - unchanged since
  2026-09-14, confirmed still true today.
