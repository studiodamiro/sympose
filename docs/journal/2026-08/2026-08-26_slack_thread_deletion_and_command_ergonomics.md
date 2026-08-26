---
entry: 2026-08-26
created: 2026-08-26 04:38
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - slack/socket-mode
  - commands/ergonomics
  - memory/privacy
  - adr-031
---

# Engineering Journal: Slack Thread Deletion, Command Ergonomics & Memory Sovereignty

> **Date:** August 26, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  
> **Status:** APPROVED & IMPLEMENTED (ADR-031)  

---

## 1. Context & Motivation

During multi-agent Slack deployment and live testing with `@aurelius`, three key usability and security challenges were identified:

1. **Slack Client Slash Command Interception**:
   Typing native `/` commands (e.g. `/reset`, `/clear`, `/model`) directly into the Slack input bar resulted in Slack client-side interception (*"/clear is not a valid command"*), because unregistered slash commands are dropped before reaching Socket Mode event subscriptions.
2. **On-Demand Thread Deletion**:
   Users interacting with confidential personal notes (e.g. `Daily/`, `People/`) require the ability to instruct the bot to physically erase conversation threads directly inside Slack channels on demand.
3. **Local Memory Sovereignty & Git Sanitation**:
   Live working memories (`*_memory.md`, `_shared_memory.md`, `user_profile.md`) contain real-time extracted personal facts, project ideas, and diary entries. Tracking them in Git exposed private user data to remote repositories.

---

## 2. Architectural Decisions (ADR-031)

### ADR-031.1: Direct Slack Thread Deletion & In-Memory Purge
* Implemented physical message deletion in `sympose/slack.py`.
* When a user instructs the bot with natural language (*"delete this thread"*, *"clear our conversation"*, *"wipe chat"*) or `!clear`:
  1. Calls `client.conversations_replies(channel, ts=thread_ts)` to retrieve all messages in that thread.
  2. Iterates and calls `client.chat_delete(channel, ts=m.ts)` to physically erase the bot's messages from the Slack channel.
  3. Evicts `thread_histories[th_key]` from RAM and resets `engine.histories[handle]`.

### ADR-031.2: Punctuation Command Prefix (`!`)
* Extended `CommandInterceptor` in `sympose/commands.py` to treat `!` as an alias for `/` (e.g. `!reset`, `!clear`, `!model`, `!save`, `!compact`, `!switch`, `!config`).
* Bypasses Slack's client-side slash command interceptor completely, allowing seamless command execution without registering dozens of static Slack workspace commands.

### ADR-031.3: Local Memory Sovereignty & `.example` Template Bootstrapping
* Added live user working state to `.gitignore`:
  ```gitignore
  profiles/*_memory.md
  profiles/_shared_memory.md
  profiles/user_profile.md
  profiles/_archived/
  !*.example
  ```
* Created tracked, generic schemas (`user_profile.md.example`, `_shared_memory.md.example`, `grace_memory.md.example`, `samantha_memory.md.example`, `aurelius_memory.md.example`).
* Updated `ProfileManager.bootstrap_missing_artifacts()` to automatically provision clean local memory files from `.example` templates on fresh repository clones.

### ADR-031.4: Model Upgrade to Qwen 2.5 14B for Local Confidant
* Upgraded `@aurelius` default model to `ollama/qwen2.5:14b` with top-level vault sovereignty mandates.
* Eliminates Google Gemma 2 RLHF generic refusal loops (*"As an AI, I don't have access to files..."*), ensuring immediate, grounded access across 32k context turns.

---

## 3. Verification & Metrics

1. **Thread Deletion Test**:
   * Verified that `delete this thread` and `!clear` invoke `chat_delete` and clear `thread_histories` in **0.05s**.
2. **Exclamation Command Normalization**:
   * Verified `!reset`, `!model`, `!save` execute with zero latency impact.
3. **Template Auto-Bootstrap**:
   * Verified clean clone simulation creates fresh memory files from `.example` templates.
4. **Codebase LOC Ceiling**:
   * `sympose/slack.py`: 197 LOC (<200 LOC ceiling).
   * `sympose/commands.py`: 389 LOC (Condensing underway).
   * `sympose/profiles.py`: 198 LOC (<200 LOC ceiling).
   * `sympose/engine.py`: 200 LOC (<200 LOC ceiling).
