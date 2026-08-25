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
👉 **[Slack Socket Mode Setup Guide](../../SLACK_SETUP_GUIDE.md)**

---

## 🏛️ Architecture Highlights

- **Zero Inbound Ports:** Uses `slack-bolt` and `SocketModeHandler` for WebSocket communication.
- **Thread Context Isolation:** Every Slack thread maintains an isolated conversation history, eliminating crosstalk across channels.
- **Multi-Agent Daemon:** Run Samantha, Grace Hopper, and Marcus Aurelius concurrently as separate Slack bots from a single process (`./chat.sh --slack`).
- **Autonomic Action Tags:** All model actions (`[WRITE_NOTE]`, `[REMEMBER]`, `[SPAWN_WORKER]`) execute live and render confirmation badges formatted in Slack `mrkdwn`.
- **Architectural Decision Record:** See **[ADR-028: Slack Socket Mode Integration & Thread Context Isolation](../../journal/2026-08-25_slack_socket_mode_integration.md)**.
