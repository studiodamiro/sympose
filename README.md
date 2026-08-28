# Sympose: Multi-Model AI Agent Hub

> **Sympose** (_from Symposium: a forum of gathering experts_) is a zero-bloat, sub-second latency (`<0.8s TTFT`), and local-first multi-agent ecosystem engineered for **macOS Terminal** and **Slack (Socket Mode)**.

---

## 🏛️ System Architecture: The Triad Pattern

Sympose separates agent intelligence into three specialized, file-based components:

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

---

## 🛡️ The Zero-Maintenance Mandate (The Assistant Paradox)

> **"If the user has to become the sysadmin, curator, or custodian of their AI assistant, the system is actively working against its primary reason for existing."**

1. **Autonomous Memory Hygiene**: Memory files are compacted, deduplicated, and pruned in non-blocking background daemon threads by the `MemoryCompactor` without requiring user curation.
2. **Self-Healing & Auto-Bootstrapping**: If a new specialist profile is created with a minimal YAML manifest, missing soul and memory files are automatically generated on boot.
3. **Dynamic Model Discovery**: `ModelCatalog` queries and caches OpenRouter's live catalog on-demand. There are zero hardcoded model dictionaries to manually maintain.
4. **Zero Infrastructure Daemons**: Sympose runs directly on Python standard library primitives over local Markdown files. There are zero background Postgres, Redis, Docker, or vector database servers to maintain, crash, or migrate.
5. **Self-Regulating Context**: Sliding context window governors automatically prevent token bloat without requiring manual `/clear` micromanagement.
6. **Anti-Helplessness Axiom**: Agents have autonomous live web search and native tools. They never give canned refusals or ask the user to search the web for them.

---

## 🌟 Core Architectural Pillars

1. **Agnostic Flat-File Engine (`profiles/`):** Agent personalities (`_soul.md`), working memories (`_memory.md`), and settings (`.yaml`) are simple Markdown and YAML files. Adding, customizing, or retiring agents requires zero Python changes.
2. **Modular Skills Engine (`skills/`):** Reusable, procedural domain playbooks (`SKILL.md`) with YAML frontmatter and mandatory deliverable schemas that eliminate vague hand-waving.
3. **Native Obsidian `Templates/` Engine & Dynamic Frontmatter Tag Syncing:** Automatically renders user templates from `/Templates/` with variable interpolation (`{{date}}`, `{{time}}`, `{{title}}`), and dynamically merges topic tags into YAML frontmatter on daily note appends.
4. **Autonomous Live Web Search (`web_search`):** Real-time web search and market data lookup ($0 API key required, powered by `ddgs`) executing in <0.5s with automatic in-turn synthesis.
5. **Dedicated MCP Server Hub (`mcp/`):** Primary conversational agents remain fast and token-efficient (~400–800 tokens), while heavy tools (GitHub, Fetch, Filesystem, SQL) run in isolated child-process workers via standard MCP JSON-RPC over `stdio`.
6. **Slack Socket Mode & Multi-Agent Collaboration:** Native Slack integration with zero open ports, clickable `@mention` pills, thread-bound memory isolation, thread reset commands (`/clear`), and expressive emoji reactions (`[REACT]`).
7. **Autonomic Natural Language Lifecycle:** Non-technical users can tune runtime configuration (`[CONFIG_SET]`), spawn new specialist agents (`[CREATE_PERSONA]`), and safely retire agents (`[DELETE_PERSONA]`) purely through conversation.

---

## 🎭 Agent Specialists & Roster

| Persona | Domain / Role | Default Model Backend | Obsidian Sandbox | Key Capabilities & Skills |
| :--- | :--- | :--- | :--- | :--- |
| **Samantha** (`@samantha`) | Polymath Strategic Master Orchestrator | **Gemini 3.5 Flash-Lite** | `General/`, `Projects/`, `Thoughts/`, `Templates/` | High-level system architecture, task breakdown, Sympose concierge, and worker orchestration. Mounted: `sympose_mastery`, `strategic_analysis`, `system_architecture`, `slack_interaction`, `vault_write`, `vault_recall`, `web_search`. |
| **Grace** (`@grace`) | Surgical Software & Systems Engineer | **Gemini 3.5 Flash-Lite** (`temp: 0.1`) | `Projects/`, `Code/`, `Templates/` | Zero-bloat code reviews, atomic conventional commits, compiler heuristics, and deterministic systems design. Mounted: `code_review`, `git_workflow`, `system_architecture`, `slack_interaction`, `vault_write`, `vault_recall`, `web_search`. |
| **Anaïs Nin** (`@anais`) | Literary Sensualist & Intimate Diarist | **Qwen 2.5 14B Abliterated** (or Ollama) | `Thoughts/`, `Daily/`, `Quotes/`, `Templates/` | Psychological depth, emotional truth, intimate daily reflections, creative exploration, and personal growth. Mounted: `vault_write`, `vault_recall`, `slack_interaction`, `strategic_analysis`, `web_search`. |

---

## 🧠 Two-Tier Memory & Obsidian Vault Integration

- **Tier 1: Hot / Working Memory (`profiles/*_memory.md`):** Lean, high-signal bullet points injected into the system prompt for immediate (<0.8s) recall. Automatically pruned and compacted at $\ge 25$ lines.
- **Tier 2: Deep Obsidian Vault Archives (`Projects/`, `Thoughts/`, `Daily/`):** Authentic Obsidian markdown notes, daily journals, and visual canvases formatted with standard `[[Wikilinks]]` and YAML frontmatter.
- **Selective Sharing:** Collaborative team agents share project memory (`profiles/_shared_memory.md`), while private companions remain 100% air-gapped (`share_memory: false`).

---

## 🔌 Built-in Skills Suite (`skills/`)

- **`vault_write`**: Sovereign Obsidian note writing, standard 6-category Wikilink Taxonomy (People, Dates, Projects, Tech, Collections, Media), native `Templates/` resolution, and dynamic YAML frontmatter tag syncing.
- **`vault_recall`**: Pre-turn high-density folder digests, hierarchical daily notes recall, and instant local-first grounded retrieval (<3ms).
- **`web_search`**: Autonomous real-time internet search and cryptocurrency/stock market data lookup with zero API keys required.
- **`slack_interaction`**: Slack Socket Mode protocol, thread deletion & reset commands, silence protocols, native dynamic mentions, and multi-agent moderation.
- **`sympose_mastery`**: Runtime concierge for conversational config tuning, 7-point agent creation, and retirement.
- **`code_review`**: Zero-bloat static analysis categorizing issues into Blockers, Warnings, and Suggestions.
- **`git_workflow`**: Conventional commit formatting, atomic PR hygiene, and branch safety.
- **`strategic_analysis`**: Reversibility tests (one-way/two-way doors), tradeoff matrices, and kill criteria.
- **`system_architecture`**: Low-latency design, interface segregation, and `<200 LOC per file` modularity.
- **`discussion_moderation`**: Multi-agent discussion timeboxing (1–2 turns), scope creep prevention, and synthesis handoffs.

---

## ⚡ Autonomic Action Protocols

Sympose agents can execute real-world operations by emitting declarative bracketed tags in their response stream:

| Tag | Purpose | Example |
| :--- | :--- | :--- |
| `[DAILY_NOTE: <content>]` | Appends a reflection to today's daily note with dynamic frontmatter tag syncing | `[DAILY_NOTE: Reflected on [[Project X]] with [[Virginia]]. #growth]` |
| `[WRITE_NOTE: <path> \| <content>]` | Creates or overwrites an Obsidian note with template frontmatter | `[WRITE_NOTE: Thoughts/creativity.md \| # Creativity\n\nNotes...]` |
| `[APPEND_NOTE: <path> \| <content>]` | Appends content to an existing vault note | `[APPEND_NOTE: Projects/roadmap.md \| - [ ] Ship v2]` |
| `[WRITE_CANVAS: <path> \| <json>]` | Creates visual Obsidian `.canvas` diagrams and mindmaps | `[WRITE_CANVAS: architecture.canvas \| {...}]` |
| `[SEARCH: <query>]` | Executes real-time live internet search ($0 API key) | `[SEARCH: AXS price USD]` |
| `[SPAWN_WORKER: <spec> \| <task>]` | Dispatches an ephemeral sub-agent with tools/skills | `[SPAWN_WORKER: web_search \| Research market trends]` |
| `[REMEMBER: <fact>]` | Saves a durable bullet point to working memory | `[REMEMBER: Prefers vanilla CSS over Tailwind]` |
| `[REACT: <emoji>]` | Adds an expressive emoji reaction to a Slack message | `[REACT: rocket]` |
| `[CONFIG_SET: <key> \| <val>]` | Updates and persists runtime settings in `config.yaml` | `[CONFIG_SET: performance.max_context_turns \| 20]` |
| `[CREATE_PERSONA: <handle> \| <yaml>]` | Autonomously creates a new agent in the ecosystem | `[CREATE_PERSONA: archimedes \| name: Archimedes...]` |
| `[DELETE_PERSONA: <handle>]` | Safely archives a retired agent profile | `[DELETE_PERSONA: archimedes]` |

---

## 📂 Project Structure (<200 LOC Modularity Standard)

```text
sympose/
├── profiles/                 # Agent Souls, YAML Manifests, and Memories
│   ├── _shared_memory.md     # Team-wide collaborative working memory
│   ├── user_profile.md       # Universal user profile card
│   ├── samantha.yaml / _soul.md / _memory.md
│   ├── grace.yaml / _soul.md / _memory.md
│   ├── anais.yaml / _soul.md / _memory.md
│   └── _archived/            # Defensive soft-delete directory for retired agents
├── prompts/                  # Declarative system prompt templates
│   ├── workspace_rules.md    # Universal base rules & action physics
│   ├── worker_system.md      # Sub-agent worker sandbox prompt
│   ├── session_summary.md    # Session distillation prompt
│   └── memory_extraction.md  # Shadow memory extractor prompt
├── skills/                   # Modular procedural skill playbooks
│   ├── vault_write/          # Sovereign note writing & wikilinks standard
│   ├── vault_recall/         # Folder digests & daily notes recall
│   ├── web_search/           # Autonomous live web search ($0 key)
│   ├── slack_interaction/    # Slack Socket Mode & moderation playbook
│   ├── sympose_mastery/      # Runtime concierge & sysadmin skill
│   ├── code_review/          # Static analysis & bloat elimination
│   ├── git_workflow/         # Conventional commits & atomic PRs
│   ├── strategic_analysis/   # Tradeoff matrices & kill criteria
│   ├── system_architecture/  # Sub-second TTFT & fault isolation
│   └── discussion_moderation/# Multi-agent loop limiter & timeboxing
├── mcp/                      # Master MCP server hub & configs (servers.json)
├── sympose/                  # Decoupled Python package (<200 LOC per file)
│   ├── config.py             # ConfigManager with live dynamic override
│   ├── profiles.py           # ProfileManager, auto-soul & auto-memory genesis
│   ├── vault.py              # Obsidian templates engine, tag sync & search
│   ├── actions.py            # Autonomic action tag processor & parser
│   ├── engine.py             # Sliding window LLM engine & live synthesis loop
│   ├── slack.py              # Slack Socket Mode daemon & mention router
│   ├── compactor.py          # Autonomous working memory compactor & deduplicator
│   ├── models.py             # Live OpenRouter model catalog & disk cache
│   ├── memory.py             # Heuristic gated shadow extraction & session archival
│   ├── skills.py             # SKILL.md discovery and prompt compilation
│   ├── mcp.py                # JSON-RPC 2.0 stdio client bridge & tool schema mapper
│   ├── native_tools.py       # Deterministic execution (run_command, read_file, web_search)
│   ├── workers.py            # Sub-agent worker sandbox & multi-turn tool loop
│   ├── completer.py          # Readline tab auto-completion for commands, models & skills
│   ├── commands.py           # Tactical slash command interceptor
│   ├── ui.py                 # Rich terminal tables, banners & exit modals
│   └── cli.py                # Interactive CLI loop & streaming controller
├── docs/                     # Architectural Decision Records & Guides
│   ├── PROJECT_JOURNAL.md    # Master index & ADR records (ADR-001 to ADR-043)
│   ├── SLACK_SETUP_GUIDE.md  # 1-click Slack app manifest & socket setup
│   ├── LATENCY_TUNING_GUIDE.md # Performance parameters & latency SLAs
│   ├── MEMORY_ARCHITECTURE_STANDARD.md # Triad memory & grounding standard
│   └── journal/              # Daily engineering logs by month
├── config.yaml               # Central runtime, performance & memory config
├── requirements.txt          # Minimal, zero-bloat dependencies
├── .env.example              # Multi-provider API keys template
├── app.py                    # 35-line entry point
└── chat.sh                   # macOS quick launcher script
```

---

## ⚡ Slash Commands Reference

| Command | Purpose | Example |
| :--- | :--- | :--- |
| `/skills` (or `/tools`) | Inspect indexed skill playbooks and active MCP servers | `/skills` |
| `/worker <skill\|mcp> <task>` | Dispatch an isolated sub-agent worker with tools/skills | `/worker git_workflow "Check branch status"` |
| `/switch [@handle]` | Switch active conversation to another persona | `/switch @grace` |
| `/config` | View active runtime, performance & session settings | `/config` |
| `/config set <key> <val>` | Tune knobs live in the active terminal | `/config set performance.max_context_turns 20` |
| `/compact [shared\|@persona]` | Consolidate duplicates, resolve conflicts & prune memory | `/compact shared` |
| `/delete @<handle>` | Safely retire and archive an agent persona | `/delete @curie` |
| `/save [memory\|obsidian\|both]` | Synthesize and save session takeaways | `/save both` |
| `/vault <query>` | Query persona's sandboxed Obsidian notes | `/vault architecture` |
| `/vault backlinks <note>` | Inspect incoming backlinks/references for a note | `/vault backlinks OAuth` |
| `/note <file.md> <content>` | Create or append to a sandboxed vault note | `/note Ideas.md Roadmap items` |
| `/daily <reflection>` | Append a thought to today's Daily Notes | `/daily Completed worker refactor` |
| `/remember <fact>` | Save a durable fact to working memory | `/remember Prefers vanilla CSS` |
| `/model [list\|find\|reset]` | Inspect active model, search live OpenRouter, or switch | `/model find sonnet` |
| `/reset` (or `/new`) | Reset active conversation context | `/reset` |
| `/clear` | Clear terminal screen and reset context | `/clear` |
| `/help` | Show command reference | `/help` |
| `exit` (or `quit`) | End session and trigger save flow | `/exit` |

---

## 🚀 Quickstart

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for `npx` MCP servers)
- (Optional) [Ollama](https://ollama.com/) for local offline models.

### 2. Installation

#### Option A: 1-Line Install directly from GitHub (macOS, Windows, Linux)
```bash
pipx install git+https://github.com/studiodamiro/sympose.git
```

#### Option B: Local Developer Clone
```bash
# Clone the repository
git clone https://github.com/studiodamiro/sympose.git
cd sympose

# Create virtual environment & install in editable mode
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
# Launch interactive Terminal CLI Hub (Default)
sympose
# or: ./chat.sh

# Launch Web Dashboard & Standalone Vault Explorer
sympose --dashboard
# or: ./chat.sh --dashboard

# Launch 24/7 Slack Socket Mode Daemon
sympose --slack
# or: ./chat.sh --slack
```

---

## 📜 Documentation & ADRs

- **[Master Journal & ADR Index (`docs/PROJECT_JOURNAL.md`)](docs/PROJECT_JOURNAL.md)**: Complete record of architectural decisions from ADR-001 through ADR-043.
- **[Slack Socket Mode Setup Guide (`docs/SLACK_SETUP_GUIDE.md`)](docs/SLACK_SETUP_GUIDE.md)**: Step-by-step 1-click App Manifest and multi-agent setup guide for Slack.
- **[Latency & Performance Tuning Guide (`docs/LATENCY_TUNING_GUIDE.md`)](docs/LATENCY_TUNING_GUIDE.md)**: Complete parameter catalog governing sub-second SLA.
- **[Autonomous Agent Memory Architecture Standard (`docs/MEMORY_ARCHITECTURE_STANDARD.md`)](docs/MEMORY_ARCHITECTURE_STANDARD.md)**: Triad memory management, shadow extraction, and anti-hallucination grounding.
- **[Wiki Documentation Hub (`docs/wiki/index.md`)](docs/wiki/index.md)**: Comprehensive guide to skills, MCP workers, and profile systems.
