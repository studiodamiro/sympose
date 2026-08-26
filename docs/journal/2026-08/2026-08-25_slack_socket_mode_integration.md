---
entry: 2026-08-25
created: 2026-08-25 19:20
type: adr-log
project: sympose
tags:
  - adr
  - architecture
  - slack
  - socket-mode
  - daemon
---

# Architecture Decision Record: Slack Socket Mode Integration & Thread-Bound Multi-Agent Routing

> **Date:** 2026-08-25  
> **Author:** damiro & Grace Hopper  
> **Status:** Ratified & Implemented  
> **Affected Modules:** `sympose/slack.py`, `sympose/__init__.py`, `app.py`, `config.yaml`, `requirements.txt`

---

## Executive Summary

Phase 2 of the Sympose roadmap specifies extending the zero-bloat multi-agent ecosystem from the local macOS Terminal REPL to **Slack** via **Socket Mode**.

This journal establishes **ADR-028**, covering the architecture of the `SlackDaemon` module, thread-isolated conversational sessions, automatic persona dispatch, immediate reaction feedback, and action tag execution in Slack channels and direct messages.

---

## ADR-028: Slack Socket Mode Integration & Thread Context Isolation

### Context
In team and personal messaging environments like Slack:
1. **Public Webhook Vulnerability & Port Forwarding Bloat**: Traditional HTTP webhook integrations require exposing open inbound firewall ports, configuring reverse proxies, or running third-party tunneling daemons (like `ngrok`), violating the zero-infrastructure mandate.
2. **Context Bleed Across Concurrent Threads**: Multiple users or distinct threads interacting with agents simultaneously will cause catastrophic conversation context bleeding if session histories are global per persona.
3. **Latency & Response Feedback**: Real-time token streaming character-by-character is restricted by Slack API rate limits (~1 update/second per message). The user needs immediate acknowledgment (<0.8s) and clean message delivery with action badges.

### Decision

1. **Zero Inbound Ports via Socket Mode:**
   - Implemented `SlackDaemon` (`sympose/slack.py`) utilizing `slack-bolt` and `SocketModeHandler`.
   - Communication operates over an outbound secure WebSocket using `SLACK_APP_TOKEN` (`xapp-1-...`) and `SLACK_BOT_TOKEN` (`xoxb-...`).

2. **Thread-Bound Session Context Isolation:**
   - Every incoming event derives a unique thread identifier: `thread_id = f"{channel_id}:{thread_ts}"`.
   - Conversation histories are isolated per thread and persona (`thread_histories[f"{thread_id}:{handle}"]`), preventing context collision between separate Slack threads.

3. **Intelligent Persona Mention Routing:**
   - Mentions within messages (e.g. `@grace check this code`, `@aurelius reflect on today`, `/switch @grace`) dynamically route the thread to the target persona.
   - Subsequent replies within the same thread automatically inherit the active thread persona.
   - Defaults to `runtime.default_persona` (`samantha`) when no specific persona is referenced.

4. **Instant Reaction SLA & Action Badging:**
   - Immediately adds an `eyes` reaction on receiving an event for instant visual feedback (<0.8s SLA).
   - Collects engine stream chunks, executes all autonomic tags (`[WRITE_NOTE]`, `[REMEMBER]`, `[SPAWN_WORKER]`), converts Markdown to Slack-compatible mrkdwn (`convert_md_to_slack_mrkdwn()`), posts the threaded reply, and replaces the reaction with `white_check_mark`.

5. **Strict Modularity (<200 LOC Standard):**
   - `sympose/slack.py` is implemented in 162 LOC, maintaining complete separation of concerns and testability.

### Verification
- **Import & Contract Validation:** Verified clean initialization and module exports via `sympose.__all__`.
- **Unit Test Suite (`scratch/test_slack_daemon.py`):**
  - Verified persona extraction, `@handle` mention parsing, and thread persona inheritance.
  - Verified bot message filtering and reaction lifecycle (`eyes` $\to$ `white_check_mark`).
  - Verified token validation and descriptive configuration error messaging.
- **Entry Point Integration:** Verified `python3 app.py --slack` correctly hooks into `SlackDaemon.start()`.
