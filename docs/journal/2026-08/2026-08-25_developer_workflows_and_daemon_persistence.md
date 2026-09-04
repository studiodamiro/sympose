---
entry: 2026-08-25
created: 2026-08-25 21:05
type: journal
project: sympose
tags:
  - workflow
  - developer-guide
  - daemon
  - persistence
  - vscode
  - antigravity
  - slack
---

# Developer Workflow Architecture & Daemon Persistence Standard

> **Date:** 2026-08-25  
> **Author:** damiro & Grace Hopper  
> **Status:** Ratified & Documented  
> **Affected Documents:** `docs/wiki/guides/developer-workflows.md`, `docs/wiki/index.md`, `docs/PROJECT_JOURNAL.md`

---

## Executive Summary

As Sympose expanded across multiple execution environments (Antigravity IDE rules, native terminal CLI, and Slack mobile Socket Mode), establishing clear operational ergonomics, tool boundaries, and daemon lifecycle management became paramount.

This entry records the architectural standard and developer operating playbook for pair-programming with the **Grace Hopper** persona across local and remote contexts.

---

## Key Principles & Architectural Decisions

### 1. Dual Local Execution Ergonomics
- **In-IDE Agent Mode (Antigravity)**: Leverages workspace rules ([`.agents/rules/identity.md`](../../../.agents/rules/identity.md)) to bind Grace's soul directives directly to the IDE's autonomous tool layer (file edits, live diff inspection, test execution).
- **Integrated Terminal REPL (`./chat.sh --persona grace`)**: Runs Sympose's native Python engine inside VS Code / Antigravity terminal splits, providing instant clickable jump-to-file paths in terminal output while maintaining live access to `VaultManager` and `WorkerEngine`.

### 2. Multi-Environment Tool Boundaries
- Clarified tool boundaries: Sympose CLI and Slack daemons execute deterministic workspace tasks via `NativeTools` (`run_command`, `read_file`) and `WorkerEngine` MCP bindings without coupling to proprietary editor UI hooks.

### 3. Background Daemon Persistence Standard
- Established 4 supported operational modes for keeping `./chat.sh --slack` active 24/7 on macOS:
  1. **`tmux` session**: Interactive, inspectable, and zero-dependency (`tmux new -s sympose-slack`).
  2. **`nohup` process**: Lightweight background logging job (`nohup ./chat.sh --slack &`).
  3. **`pm2` supervisor**: Monitored daemon with auto-restart on network/process drop.
  4. **macOS `launchd` LaunchAgent (`com.sympose.slack.plist`)**: Native operating system startup daemon that boots on macOS login.

---

## Verification & Documentation Sync
- Published comprehensive guide at [`docs/wiki/guides/developer-workflows.md`](../../wiki/guides/developer-workflows.md).
- Updated master wiki index at [`docs/wiki/index.md`](../../wiki/index.md).
- Updated project master journal index at [`docs/PROJECT_JOURNAL.md`](../../PROJECT_JOURNAL.md).
