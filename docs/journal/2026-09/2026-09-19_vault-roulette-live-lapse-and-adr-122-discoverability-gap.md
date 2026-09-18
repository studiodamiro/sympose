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

# Sympose Engineering Log: The "Vault Roulette" Lapse Was a Real, Deterministic Matcher Bug — Not Model Non-Determinism

> **Date:** Saturday, September 19, 2026
> **Topic:** damiro shared a live transcript where Samantha, manually
> overridden to `ollama/gemma4:e4b` and freshly `/reset`, had no idea what
> "our favorite game" (Vault Roulette, a random-note-pull ritual - see the
> [2026-09-17 fix](./2026-09-17_ritual-continuation-carries-no-grounding.md))
> was, twice in a row, even after being directly reminded. The first pass
> at this investigation (below, in the original §1, now corrected) tested
> against the wrong workspace and concluded "no bug, likely model
> non-determinism." That conclusion was wrong. Re-testing against the
> actual live workspace found a real, deterministic, 100%-reproducible
> matcher bug and fixed it. Investigating it also surfaced a real,
> separate gap: a built local/cloud model-routing feature
> ([ADR-122](./2026-09-14_adr-122-local-cloud-model-complexity-routing.md))
> that no persona has ever actually used, and that a new user has no way
> to discover.
> **Status:** §1's matcher bug found and fixed, verified live. §2's
> discoverability gap found and documented - closed separately via
> README/`/help`/`/setup` changes the same day.

## 1. Corrected: the real root cause was testing against the wrong workspace

The original pass here traced the mechanism against
`~/.sympose/profiles/samantha_memory.md` and concluded everything checked
out, chalking the live failure up to local-model sampling non-determinism.
That workspace choice was never actually verified against which
installation produced damiro's live transcript - it was assumed.

`sympose/workspace.py::resolve_workspace_dir()` uses "Local Project Mode"
- the current working directory itself, not `~/.sympose` - whenever that
directory already has its own `profiles/`/`config.yaml`. This repo
checkout does. Three independent, concrete signals confirmed damiro's
real `sympose` sessions actually run from here, not `~/.sympose`:

- This repo's own `.env` has `MASTER_VAULT_PATH` pointing at damiro's real
  Obsidian vault - the same path used everywhere else in this
  conversation.
- A live edit damiro described making directly in "sam's yaml"
  (uncommenting `local_model: 'ollama/gemma4:e4b'`) landed as an
  uncommitted change to *this repo's* tracked `profiles/samantha.yaml`,
  not `~/.sympose/profiles/samantha.yaml`.
- This repo's git-ignored `sessions/` directory holds weeks of real,
  dated session transcripts, including Slack-channel-tagged files
  (`D0BTCPLJNL8:...samantha.jsonl`) - not a stale template.

Re-tested against this repo's *actual* `profiles/samantha_memory.md`,
whose only relevant bullet reads "Enjoys playing a movie game called
'Vault Roulette.'" - markedly thinner than `~/.sympose`'s version, and
critically: it never says "favorite," and uses "movie"/"playing" where
damiro's real messages said "Movies"/"play". Running
`ProfileManager.find_relevant_memory_fact` against this real content with
damiro's exact real messages returned `None` for both - deterministically,
every time, no model involved yet. `find_relevant_memory_fact` only ever
compared exact word forms; it never had a chance to fire, so the model
was never shown the fact at all. This fully explains the live failure and
required no theory about model sampling.

**Fix:** `ProfileManager._memory_match_tokens` (`profiles.py`) now widens
each token with a crude stem - trailing `'ing'` or `'s'` stripped - mirroring
the de-pluralisation already used in `vault_recall.recall_candidates`.
Generic across any fact/phrasing, not a phrase list tied to this one
ritual. Verified live against the real local model
(`ollama/gemma4:e4b`) and this repo's actual memory file, in a sandboxed
vault (never the real one, to avoid repeating an earlier accidental
live-write-during-testing incident): asked twice in one session
("hey sam lets play our favorite game g!" then "dont you remember our
favorite game?"), Samantha now names "Vault Roulette" unprompted on the
first reply and again on the second, entirely without a code path that
relies on the model's own memory.

**Known, deliberately unfixed limitation:** this repo's memory bullet
still doesn't trigger `VaultManager.describes_random_pull_ritual`'s
"actually fetch a real random note" path, because that function requires
the fact to say "random" plus a pull-ish verb ("pull", "picked", …) and
this bullet says neither - it only names the game, not what it does.
That's a content gap in the memory bullet's own wording, not a matcher
bug, and loosening `describes_random_pull_ritual` to guess ritual intent
from a bare game name would be exactly the kind of per-user phrase-list
special-casing this codebase avoids. Left alone; the recognition failure
that was actually reported is fixed and verified.

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
