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
| `/compact` | `[shared\|@persona]` | Deduplicates, resolves conflicts, and consolidates working memory into high-density bullets. |

---

## 3. Sandboxed Vault Commands

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/note` | `<file.md> <content>` | Creates or appends Markdown content into the persona's sandboxed vault folder. |
| `/daily` | `<reflection text>` | Appends timestamped reflection to `Daily Notes/YYYY-MM-DD.md` in your vault. |
| `/vault` | `<query>` | Performs structured search over whitelisted vault folders and opens the interactive reader. |
| `/vault back` / `/vault list` | *(none)* | Re-displays the last search results list without re-running search queries. |
| `/read` / `/view` | `<#\|name>` | Renders a note in-terminal inside the stylized `MultiSectionPanel` box with frontmatter styling. |
| `/open` / `/vault open` | `<#\|name>` | Launches the note directly in the Obsidian desktop application via OS handler. |
| `/vault backlinks` | `<note_name>` | Instantly inspects incoming backlinks/references with line numbers and snippets (also `/backlinks <note>`). |

---

## 4. Configuration & Delegation

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/config` | *(none)* | Displays current `config.yaml` parameters and active runtime values. |
| `/config set` | `<key> <value>` | Dynamically updates a configuration value live in-session. |
| `/model` | `[name\|reset\|list\|find <q>\|refresh]` | Inspects active model, searches OpenRouter catalog, switches models, or resets to default. |
| `/skills` / `/skill` | `[list]` | Inspects loaded skill playbooks (`skills/`), active agent mounts, and MCP servers (`config.yaml`). |
| `/skill add` | `<name> [@handle]` | Equips skill to active persona (or target `@handle`) and persists to YAML manifest (`/skill mount`, `/skill install`). |
| `/skill remove` | `<name> [@handle]` | Unmounts skill from active persona (or target `@handle`) and persists to YAML (`/skill unmount`, `/skill rm`). |
| `/skill show` | `<name>` | Previews markdown playbook directives and metadata for a skill (`/skill view`, `/skill info`). |
| `/worker` | `<skill\|mcp> <task>` | Dispatches an ephemeral sub-agent worker sandbox with skills and MCP tools. |
| `/ask` | `<@peer> <prompt>` | Spawns an isolated sub-agent task to a peer agent without polluting active context. |
| `/help` | *(none)* | Displays command cheat sheet and active shortcuts. |

---

## 5. Keyboard & Signal Shortcuts

| Shortcut | Context | Behavior |
| :--- | :--- | :--- |
| `Ctrl + C` | During Thinking / Streaming | Immediately aborts active LLM token stream / spinner, prints `^C [Interrupted]`, and preserves session. |
| `Ctrl + C` | During Slash Commands | Cancels active tool/search command without exiting the CLI. |
| `Ctrl + C` | At Input Prompt | Clears the current input line without exiting the session. |
| `Ctrl + D` | At Input Prompt | Cleanly exits the session and triggers memory persistence. |
