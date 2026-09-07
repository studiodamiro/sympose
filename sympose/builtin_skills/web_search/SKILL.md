---
name: "web_search"
title: "Live Internet Search & Real-Time Intelligence"
description: "Fetching live prices, news, docs, and online research via the [SEARCH] and [SPAWN_WORKER: web_search] action tags."
tags:
  - web-search
  - internet
  - real-time-data
---

# Live Internet Search

You have live internet access. The "never tell the user to search it himself"
rule is in the Universal Workspace Rules — this playbook is just *which* tag to
use and the flow.

## Which tag

- **`[SEARCH: <query>]`** — quick lookups: a current price, a fact, a headline, a
  spec.
- **`[SPAWN_WORKER: web_search | <task>]`** — deeper work: multi-query research,
  cross-referencing, anything that would otherwise spill many tokens of
  intermediate results into the main thread.

## Flow

1. In one sentence, say you're fetching live data.
2. Emit the tag at the end of the turn.
3. The runtime runs the search and feeds results back; deliver the final
   answer/calculation directly.
