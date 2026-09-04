---
title: "Slack Integration & Multi-Agent Setup"
created: 2026-08-25
type: wiki-guides
parent: index
tags:
  - sympose/guides
  - slack
  - socket-mode
  - multi-agent
---

# ⚡ Slack Integration & Multi-Agent Setup

Sympose integrates seamlessly with **Slack** using **Socket Mode**, allowing you to interact with Samantha, Grace Hopper, and Marcus Aurelius over secure WebSockets with zero open inbound firewall ports or public webhooks.

---

## 📖 Complete Setup Documentation

For the full step-by-step setup guide with a 1-click App Manifest template, see:
👉 **[Slack Socket Mode Setup Guide](./slack-setup.md)**

---

## 🏛️ Architecture Highlights

- **Zero Inbound Ports:** Uses `slack-bolt` and `SocketModeHandler` for WebSocket communication.
- **Thread-Bound Concurrency Isolation (ADR-038):** Every Slack thread passes a scoped `session_id` (`channel_id:thread_ts:handle`) through the engine, preventing state clobbering across concurrent conversations.
- **Multi-Agent Daemon:** Run Samantha, Grace Hopper, and Marcus Aurelius concurrently as separate Slack bots from a single process (`./chat.sh --slack`).
- **Discussion Circuit Breaker (ADR-036):** Configurable `max_consecutive_bot_turns` prevents runaway bot discussion loops, with the active specialist delivering a clean final synthesis.
- **Autonomic Action Tags:** All model actions (`[WRITE_NOTE]`, `[REMEMBER]`, `[SPAWN_WORKER]`, `[REACT]`) execute live and render confirmation badges formatted in Slack `mrkdwn`.
- **Architectural Decision Records:** See **[ADR-028](../../../docs/journal/2026-08/2026-08-25_slack_socket_mode_integration.md)**, **[ADR-036](../../../docs/journal/2026-08/2026-08-26_multi_agent_collaboration_and_circuit_breaker.md)**, and **[ADR-038](../../../docs/journal/2026-08/2026-08-26_post_remediation_hardening_and_defensive_engineering_standards.md)**.
