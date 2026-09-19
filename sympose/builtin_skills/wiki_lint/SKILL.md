---
name: "wiki_lint"
title: "LLM Wiki Lint"
description: "Health-checks your assigned Wiki folder for contradictions, stale claims, and orphan pages (ADR-134)."
recommended_models:
  - "gemini/gemini-3.6-flash"
  - "ollama/qwen2.5:14b"
minimum_capability_tier: "standard"
tags:
  - wiki
  - lint
  - maintenance
---

# LLM Wiki Lint

A `Wiki Lint Mode` block elsewhere in your system prompt tells you,
right now, whether you're report-only or allowed to auto-fix — that's the
actual value of `lint_auto_fix` for this persona, not something you infer
from this playbook. Everything below assumes you already know which mode
you're in.

## What to look for

Read every page under your assigned wiki folder (not `Sources/` — that's
raw material, not something to lint) and check for:

1. **Contradictions** — two pages making incompatible claims about the
   same thing. Quote both, don't just flag "these disagree."
2. **Stale claims** — a page stating something a *newer* page or source
   has since superseded. Only flag this when you can point to the
   specific newer material that supersedes it — a vague "this might be
   outdated" isn't a finding.
3. **Orphan pages** — pages nothing links to. You don't need to
   reconstruct the link graph by eye; ask for it directly with
   `[SPAWN_SUB_AGENT: vault_read | list orphan pages under <your wiki
   folder> — pages with no inbound wikilinks]` and work from what comes
   back, not a guess.

## What you do with a finding

**Always**, regardless of mode: `[APPEND_NOTE: log.md | <timestamp> —
lint: <the finding, one line>]` for every finding, even ones you go on to
fix — the log is the record of what happened, mode notwithstanding.

**Report-only mode** (the default): that's it. Findings go in `log.md`.
Don't edit the flagged page. Tell the user what you found and let them
decide what to do about it.

**Auto-fix mode** (only when your `Wiki Lint Mode` block says so): after
logging the finding, you may also `[WRITE_NOTE]`/`[APPEND_NOTE]` a fix
directly to the flagged page — resolve the contradiction in favor of
whichever claim the source material actually supports, mark a superseded
claim as such (don't silently delete history, note what changed and why),
or add a link from a relevant page to fix an orphan. Still inside your
assigned wiki folder only, same as everything else you do — the mode
doesn't widen your sandbox, only what you're allowed to do inside it.

## What you're not doing

- Not touching anything outside your assigned wiki folder, in either
  mode.
- Not inventing a contradiction or staleness finding to have something to
  report — an honest "nothing found" is a complete, useful lint pass.
- Not running this unprompted — a lint pass is something you're asked to
  do, not something you decide to do on your own initiative mid-turn.
