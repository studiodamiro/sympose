---
title: "ADR-031 — Slack Thread Deletion, Command Ergonomics & Memory Sovereignty"
created: 2026-08-26
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---

# ADR-031 — Slack Thread Deletion, Command Ergonomics & Memory Sovereignty

- **Status:** Accepted
- **Date:** 2026-08-26
- **Deciders:** damiro (Lead Architect); Grace (Engineering Partner)

## Context

Native `/` commands typed into Slack's input bar are intercepted client-side and
never reach Socket Mode. Users handling confidential notes need to erase
conversation threads on demand. And live working-memory files
(`*_memory.md`, `_shared_memory.md`, `user_profile.md`) contain real personal
facts that must not be committed to Git.

## Decision

- **ADR-031.1 — Direct thread deletion & in-memory purge.** Natural language
  ("delete this thread", "wipe chat") or `!clear` calls
  `conversations_replies` + `chat_delete` to erase the bot's messages, then
  evicts `thread_histories` and resets `engine.histories`.
- **ADR-031.2 — Punctuation command prefix (`!`).** `CommandInterceptor` treats
  `!` as an alias for `/` (`!reset`, `!model`, `!save`, ...), bypassing Slack's
  client-side interceptor with no registered workspace commands.
- **ADR-031.3 — Local memory sovereignty & `.example` bootstrapping.** Add live
  working-state files to `.gitignore`; ship tracked generic `*.example`
  templates; `bootstrap_missing_artifacts()` provisions clean memory files from
  them on fresh clones.
- **ADR-031.4 — Local confidant model upgrade.** `@aurelius` default →
  `ollama/qwen2.5:14b`, eliminating Gemma 2 RLHF refusal loops over 32k context.

## Consequences

**Positive**

- Conversations can be physically erased from Slack in ~0.05 s.
- All slash commands work in Slack without registering dozens of workspace
  commands.
- Private facts never leave the machine via Git.

**Negative / costs**

- `.example` bootstrapping adds a first-run provisioning step (automated).
- A larger local model raises local RAM / latency for `@aurelius`.

## Alternatives rejected

- **Registering every slash command as a Slack workspace command.** Rejected:
  dozens of static registrations to maintain; `!` prefix sidesteps the whole
  problem.
- **Tracking working-memory files in Git.** Rejected: exposes real personal data
  on the public remote.
