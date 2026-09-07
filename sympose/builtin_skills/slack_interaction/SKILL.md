---
name: "slack_interaction"
title: "Slack Integration & Conversation Protocol"
description: "Slack Socket Mode conduct: thread lifecycle and reset commands, the silence protocol, @mentions, and multi-agent etiquette."
tags:
  - slack
  - conversation
  - thread-management
  - multi-agent
---

# Slack Interaction & Conversation Protocol

Sympose keeps isolated memory per Slack thread (`channel_id:thread_ts`).

## Thread reset

When the user says "delete this thread", "clear conversation", "wipe chat",
"purge history", `/clear`, or `/reset`:

- **Silent variant** ("do not reply", "stay quiet", "no acknowledge"): the daemon
  wipes memory, deletes past bot messages, adds a `🧹` reaction, and emits **no
  text**.
- **Standard**: the daemon confirms with `🧹 Conversation history deleted for
  @<persona>.`

## Silence protocol

If the user tells you not to reply, or the message is a bare acknowledgement,
emit **no text** — not `(no response)`, not `*acknowledged*`. Optionally leave one
reaction (`[REACT: white_check_mark]`, `[REACT: broom]`).

## DMs (1-on-1)

- Speak directly and naturally. Never append `@user` or a persona handle as a
  sign-off.
- Don't pull other agents into a DM unless the user explicitly asks.

## Shared channels & group threads

- Write natural `@mentions` (`@<handle>`, `@<user>`) — the runtime renders them as
  native Slack pills.
- State your own view, then `@mention` the relevant agent with a direct question
  so they answer in their own turn. Never script their reply.
- Keep group exchanges tight: 1–2 turns, synthesise, hand back.

## Reactions

Use `[REACT: <emoji>]` (e.g. `eyes`, `rocket`, `rose`, `bulb`, `fire`) to signal
presence, resonance, or agreement without adding a chat message. Use them
naturally, not on every turn.
