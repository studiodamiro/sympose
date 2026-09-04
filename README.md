# Sympose: Multi-Model AI Agent Hub

> **Sympose** (_from Symposium: a forum of gathering experts_) is a zero-bloat, sub-second latency (`<0.8s TTFT`), and local-first multi-agent ecosystem engineered for **macOS Terminal** and **Slack (Socket Mode)**.

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ (for `npx` MCP servers)
- (Optional) [Ollama](https://ollama.com/) for local offline models.

### 2. Installation

**Option A — 1-line install (macOS, Windows, Linux):**
```bash
pipx install git+https://github.com/studiodamiro/sympose.git
```

**Option B — local developer clone:**
```bash
git clone https://github.com/studiodamiro/sympose.git
cd sympose
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and fill in your API keys (OpenRouter, Gemini, Anthropic, or OpenAI) and your Obsidian vault path:
```bash
cp .env.example .env
```

### 4. Running Sympose

```bash
# Interactive Terminal CLI Hub (default)
sympose
# or: ./chat.sh

# Web Dashboard & Standalone Vault Explorer
sympose --dashboard
# or: ./chat.sh --dashboard

# 24/7 Slack Socket Mode Daemon
sympose --slack
# or: ./chat.sh --slack
```

On first launch, the dashboard generates a login password into your workspace `.env` (printed once to the console) and serves over a self-signed HTTPS certificate — accept the one-time browser warning and log in with that password.

Full walkthrough, troubleshooting, and upgrade notes: **[Quickstart Guide](docs/wiki/guides/quickstart.md)**.

---

## 🏛️ Architecture: The Triad Pattern

Sympose separates agent intelligence into three specialized, file-based components — plain Markdown and YAML, no database:

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Profile Manifest (yaml)  ──>  RUNTIME / UI METADATA      │
│    • Name, Handle, Title, Icon, Model, Vault Folders        │
│    • thinking_phrases: UI spinner strings (0 token cost)    │
│    • skills: Active procedural skill playbooks              │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│ 2. Agent Soul (_soul.md)   ──>  COGNITIVE DIRECTIVES        │
│    • Injected into LLM System Prompt                        │
│    • Personality, voice cadence, psychological depth        │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│ 3. Working Memory (_memory)──>  DYNAMIC EVOLVING FACTS      │
│    • Updated live by Shadow Extractor & Session Archival    │
│    • Auto-compacted & conflict-resolved at >= 25 lines      │
└─────────────────────────────────────────────────────────────┘
```

Full breakdown: **[Architecture Overview](docs/wiki/architecture/overview.md)**.

---

## 🛡️ The Zero-Maintenance Mandate (The Assistant Paradox)

> **"If the user has to become the sysadmin, curator, or custodian of their AI assistant, the system is actively working against its primary reason for existing."**

1. **Autonomous Memory Hygiene** — memory files are compacted, deduplicated, and pruned in the background; no manual curation.
2. **Self-Healing & Auto-Bootstrapping** — drop a minimal YAML manifest and missing soul/memory files generate on boot.
3. **Dynamic Model Discovery** — `ModelCatalog` queries and caches OpenRouter's live catalog on-demand; zero hardcoded model lists.
4. **Zero Infrastructure Daemons** — Python standard library over local Markdown files; no Postgres, Redis, Docker, or vector DB to run or migrate.
5. **Self-Regulating Context** — sliding context windows prevent token bloat without manual `/clear` micromanagement.
6. **Anti-Helplessness Axiom** — agents have autonomous live web search and native tools; they never punt a question back to you to go search yourself.

---

## 🌟 Core Pillars

- **Agnostic Flat-File Engine** (`profiles/`) — personas, memories, and settings are plain Markdown/YAML; no Python changes to add or retire an agent.
- **Modular Skills Engine** (`skills/`) — reusable procedural playbooks with mandatory deliverable schemas.
- **Native Obsidian `Templates/` Engine** — variable interpolation and dynamic frontmatter tag syncing on daily notes.
- **Autonomous Live Web Search** — real-time search and market data, $0 API key, powered by `ddgs`.
- **Dedicated MCP Server Hub** (`mcp/`) — heavy tools (GitHub, Fetch, Filesystem, SQL) run isolated in child-process workers so the primary agent stays fast and token-light.
- **Slack Socket Mode** — zero open ports, thread-bound memory isolation, `/clear`, expressive emoji reactions.
- **Autonomic Natural-Language Lifecycle** — tune config, spawn, and retire agents purely through conversation.

---

## 🎭 Personas: Clean Slate, Grown by Conversation

Sympose ships with exactly one persona out of the box: **Samantha** (`@samantha`), the master orchestrator. Everything else — a co-engineer, a private journaling companion, a domain specialist — is something *you* create, not product content bundled in.

Ask Samantha in natural language and she emits `[CREATE_PERSONA]` to write the manifest and soul directives, instantly mounting the new agent into `/switch`:

> *"Create an agent modeled after Rear Admiral Grace Hopper for surgical systems engineering and zero-bloat code reviews."*

Persona anatomy, memory model, and hand-authoring a manifest yourself: **[Profile System & Persona Genesis](docs/wiki/agents/profile-system.md)** · **[Creating Custom Agents](docs/wiki/guides/creating-agents.md)**.

---

## 🧠 Two-Tier Memory & Obsidian Vault Integration

- **Hot memory** (`profiles/*_memory.md`) — lean bullet points injected into the system prompt for sub-second recall, auto-compacted at 25+ lines.
- **Deep vault archives** (`Projects/`, `Thoughts/`, `Daily/`) — real Obsidian notes with `[[Wikilinks]]` and YAML frontmatter.
- **Selective sharing** — team agents can share project memory; private companions stay fully air-gapped (`share_memory: false`).

Full standard: **[Memory Architecture](docs/wiki/memory/architecture-standard.md)**.

---

## ⚡ Skills & Action Protocols

Agents act on the world by emitting declarative tags in their response stream — `[WRITE_NOTE: path | content]`, `[REMEMBER: fact]`, `[SPAWN_WORKER: spec | task]`, `[CONFIG_SET: key | value]`, and more — parsed and executed after the model finishes streaming, at zero added round-trips.

Ten built-in skill playbooks ship in `skills/`: `vault_write`, `vault_recall`, `web_search`, `slack_interaction`, `sympose_mastery`, `code_review`, `git_workflow`, `strategic_analysis`, `system_architecture`, `discussion_moderation`.

Full tag reference and skill specs: **[Action Tags Reference](docs/wiki/reference/action-tags.md)** · **[Modular Skills System](docs/wiki/agents/skills-system.md)**.

---

## 📂 Project Structure

```text
sympose/
├── profiles/     # Agent souls, YAML manifests, and working memory
├── prompts/      # Declarative system prompt templates
├── skills/       # Modular procedural skill playbooks
├── mcp/          # MCP server hub & configs
├── sympose/      # Python package, <200 LOC per file
├── docs/         # ADRs, wiki, and engineering journal
├── config.yaml   # Central runtime, performance & memory config
└── app.py        # Entry point
```

Per-file responsibility breakdown: **[Package Layering & Modular Design](docs/wiki/architecture/overview.md#3-package-layering--modular-design)**.

---

## ⌨️ Common Commands

| Command | Purpose |
| :--- | :--- |
| `/switch @handle` | Switch active persona |
| `/model find <query>` | Search and switch live models |
| `/worker <skill\|mcp> <task>` | Dispatch an isolated sub-agent worker |
| `/vault <query>` | Query the sandboxed Obsidian vault |
| `/save [memory\|obsidian\|both]` | Synthesize and save session takeaways |
| `/help` | Full command reference, in-app |

Complete reference: **[CLI Commands & Shortcuts](docs/wiki/reference/cli-commands.md)**.

---

## 📜 Documentation & ADRs

- **[Master Journal & ADR Index](docs/PROJECT_JOURNAL.md)** — the complete, chronological architectural decision record.
- **[Wiki Documentation Hub](docs/wiki/index.md)** — skills, MCP workers, profile system, and full guides.
- **[Slack Setup Guide](docs/wiki/guides/slack-setup.md)** · **[Latency Tuning Guide](docs/wiki/guides/latency-tuning.md)** · **[Memory Architecture Standard](docs/wiki/memory/architecture-standard.md)**
