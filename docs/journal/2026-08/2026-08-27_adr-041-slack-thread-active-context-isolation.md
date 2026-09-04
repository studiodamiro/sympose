---
title: "ADR-041 — Multi-Turn Slack Thread Active Context Isolation & Single-Source Action Execution"
created: 2026-08-27
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-041 — Multi-Turn Slack Thread Active Context Isolation & Single-Source Action Execution

- **Status:** Accepted — hardens the action parser from
  [ADR-009](./2026-08-24_adr-009-autonomous-agent-vault-access-action-protocol.md)
  in the Slack path from
  [ADR-028](./2026-08-25_adr-028-slack-socket-mode-thread-context-isolation.md)
- **Date:** 2026-08-27
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

In Slack threads, `slack.py` passes thread history into `user_prompt`. The action
processor's keyword fallback scanned the whole prompt, so a journaling request
from three turns ago triggered ghost daily-note writes on later turns. Both
`engine.py` and `slack.py` were executing actions independently — duplicate
badges.

## Decision

1. **Active turn isolation.** `ActionProcessor` evaluates heuristics only against
   `active_prompt = user_prompt.split("User Request:")[-1].strip()`.
2. **Single source of action execution.** `engine.py` alone executes actions;
   `slack.py` only calls `strip_action_tags()` for clean display.
3. **Balanced-bracket parsing & code-block masking.** `parse_action_tags()`
   masks fenced code blocks and uses depth-counted bracket parsing for nested
   `[[wikilinks]]`.

## Consequences

**Positive**

- No ghost writes from stale thread history.
- Exactly one badge per action.

**Negative / costs**

- Code-block masking in `parse_action_tags()` was later found to also swallow
  fenced `[CREATE_PERSONA]` tags — corrected by
  [ADR-049](./2026-08-29_adr-049-code-fence-action-tag-parsing.md).

## Alternatives rejected

> Not captured in the original decision record.
