---
title: "CLI Commands & Shortcuts Reference"
created: 2026-08-24
type: wiki-reference
parent: index
tags:
  - sympose/reference
  - cli-commands
  - shortcuts
---

# ⌨️ CLI Commands & Shortcuts Reference

Sympose intercepts slash commands directly in the REPL execution loop, executing them locally without sending them to the LLM.

---

## 1. Navigation & Persona Switching

| Command | Shortcut | Description |
| :--- | :--- | :--- |
| `/switch <@handle>` | `@<handle>` | Switch active conversational persona (e.g. `/switch @grace` or `@grace`). |
| `/switch` | *(none)* | Displays interactive persona selection table. |
| `/exit` | `exit`, `quit`, `:q` | Triggers session archival modal, cleans history, and exits terminal cleanly. |
| `/clear` | `/reset` | Clears conversation context window for the active persona and refreshes banner. |

---

## 2. Memory & Archival Commands

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/save` | `[memory\|obsidian\|both]` | Synthesizes current session transcript and persists to target immediately. |
| `/remember` | `<fact>` | Explicitly persists a permanent bullet point to the active persona's `_memory.md`. |

---

## 3. Sandboxed Vault Commands

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/note` | `<file.md> <content>` | Creates or appends Markdown content into the persona's sandboxed vault folder. |
| `/daily` | `<reflection text>` | Appends timestamped reflection to `Daily Notes/YYYY-MM-DD.md` in your vault. |
| `/vault` | `<query>` | Performs fast search over notes in the active persona's domain folder. |

---

## 4. Configuration & Delegation

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/config` | *(none)* | Displays current `config.yaml` parameters and active runtime values. |
| `/config set` | `<key> <value>` | Dynamically updates a configuration value live in-session. |
| `/model` | `[model_name]` | Inspects or overrides the LLM model for the active persona. |
| `/ask` | `<@peer> <prompt>` | Spawns an isolated sub-agent task to a peer agent without polluting active context. |
| `/help` | *(none)* | Displays command cheat sheet and active shortcuts. |
