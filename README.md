# Sympose: Multi-Model AI Agent Hub

> **Sympose** (_from Symposium: a forum of gathering experts_) is a zero-bloat, sub-second latency (`<0.8s TTFT`), and local-first multi-agent ecosystem engineered for **macOS Terminal** and **Slack (Socket Mode)**.

---

## 🌟 Core Architectural Pillars

1. **Agnostic Flat-File Engine:** Agent personalities (`_soul.md`), working memories (`_memory.md`), and settings (`.yaml`) are simple Markdown and YAML files in `profiles/`. Adding, customizing, or retiring agents requires zero Python changes.
2. **Modular Skills Engine (`SKILL.md`):** Reusable, procedural domain playbooks with YAML frontmatter and mandatory deliverable schemas that eliminate vague hand-waving across code, research, and strategy tasks.
3. **Model Context Protocol (MCP) & Ephemeral Workers:** Primary conversational agents remain fast and token-efficient (~400–800 tokens). Heavy tools (GitHub, Web Search, SQL, Shell) run in isolated child-process workers via standard MCP JSON-RPC over `stdio`, preventing context bloat and saving 5,000+ tokens per turn.
4. **Sub-Second Performance SLA (<0.8s TTFT):** Smart sliding window memory, GCE probe bypasses, HTTP chunked streaming at 60 FPS, and deterministic native execution tools.
5. **Autonomic Natural Language Lifecycle:** Non-technical users can tune runtime configuration (`[CONFIG_SET]`), spawn new specialist agents (`[CREATE_PERSONA]`), and safely retire agents (`[DELETE_PERSONA]`) purely through conversation.

---

## 🎭 Agent Specialists & Roster

| Persona                    | Domain / Role                          | Default Model Backend                   | Obsidian Sandbox             | Key Capabilities & Skills                                                                                                                                                   |
| :------------------------- | :------------------------------------- | :-------------------------------------- | :--------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Samantha** (`@samantha`) | Polymath Strategic Master Orchestrator | **Gemini 3.5 Flash-Lite**               | `General/`, `Strategy/`      | High-level system architecture, task breakdown, Sympose concierge, and worker orchestration. Mounted: `sympose_mastery`, `strategic_analysis`, `system_architecture`.       |
| **Grace** (`@grace`)       | Surgical Software & Systems Engineer   | **Gemini 3.5 Flash-Lite** (`temp: 0.1`) | `Projects/`, `Architecture/` | Zero-bloat code reviews, atomic conventional commits, compiler heuristics, and deterministic systems design. Mounted: `code_review`, `git_workflow`, `system_architecture`. |
| **Aurelius** (`@aurelius`) | Private Stoic Journal & Confidant      | **Local Ollama (Gemma 2 / Qwen)**       | `Journal/`, `Personal/`      | 100% private, offline daily reflections, career clarity, and personal journaling ($0.00 cost, zero cloud transmission).                                                     |

---

## 🧠 Two-Tier Memory & Obsidian Vault Integration

- **Tier 1: Hot / Working Memory (`profiles/*_memory.md`):** Lean, high-signal bullet points injected into the system prompt for immediate (<0.8s) recall.
- **Tier 2: Deep Obsidian Vault Archives (`Projects/Sessions/...`):** Complete, formatted session logs and long-term research notes stored in your Obsidian vault for human browsing and on-demand `/vault` retrieval.
- **Selective Sharing:** Collaborative team agents share project memory (`profiles/_shared_memory.md`), while private companions (`@aurelius`) remain 100% air-gapped (`share_memory: false`).

---

## 🔌 Built-in Skills & MCP Servers

### Starter Skill Playbooks (`skills/`)

- **`sympose_mastery`**: Runtime concierge for conversational config tuning, 7-point agent creation, and retirement.
- **`code_review`**: Zero-bloat static analysis categorizing issues into Blockers, Warnings, and Suggestions.
- **`git_workflow`**: Conventional commit formatting and atomic branch hygiene.
- **`strategic_analysis`**: Reversibility tests (one-way/two-way doors), tradeoff matrices, and kill criteria.
- **`system_architecture`**: Low-latency design, interface segregation, and `<200 LOC per file` modularity.

### Configured MCP Servers (`config.yaml`)

- **`filesystem`**: Secure workspace directory traversal and file inspection.
- **`github`**: Repository search, issue management, and pull request review.
- **`brave_search`**: Real-time live web research and news verification.

---

## 📂 Project Structure (<200 LOC Modularity Standard)

```text
sympose/
├── config.yaml               # Central runtime, performance & MCP configuration
├── README.md                 # Master project overview & quickstart
├── requirements.txt          # Minimal, zero-bloat dependencies
├── .env.example              # Environment variables template
├── app.py                    # 35-line entry point
├── chat.sh                   # macOS quick launcher script
├── skills/                   # Modular procedural skill playbooks
│   ├── sympose_mastery/      # Runtime concierge & sysadmin skill
│   ├── code_review/          # Static analysis & bloat elimination
│   ├── git_workflow/         # Conventional commits & atomic PRs
│   ├── strategic_analysis/   # Tradeoff matrices & kill criteria
│   └── system_architecture/  # Sub-second TTFT & fault isolation
├── sympose/                  # Decoupled Python package (<200 LOC per file)
│   ├── config.py             # ConfigManager with live dynamic override
│   ├── profiles.py           # ProfileManager, auto-soul & auto-memory genesis
│   ├── vault.py              # Multi-folder Obsidian sandboxing & search
│   ├── engine.py             # Sliding window LLM engine & proactive synthesis
│   ├── actions.py            # Autonomic action processor ([SPAWN_WORKER], [CONFIG_SET], etc.)
│   ├── commands.py           # Tactical slash command interceptor
│   ├── skills.py             # SKILL.md discovery and prompt compilation
│   ├── mcp.py                # JSON-RPC 2.0 stdio client bridge & tool schema mapper
│   ├── native_tools.py       # Deterministic subprocess execution (run_command, read_file)
│   ├── workers.py            # Sub-agent worker sandbox & multi-turn tool loop
│   ├── ui.py                 # Rich terminal tables, banners & exit modals
│   └── cli.py                # Interactive CLI loop & streaming controller
├── profiles/                 # Declarative agent manifests & working memory
│   ├── _shared_memory.md     # Team-wide collaborative working memory
│   ├── user_profile.md       # Universal user profile card
│   ├── samantha.yaml / _soul.md / _memory.md
│   ├── grace.yaml / _soul.md / _memory.md
│   ├── aurelius.yaml / _soul.md / _memory.md
│   └── _archived/            # Defensive soft-delete directory for retired agents
└── docs/                     # Documentation, wiki & architectural journals
    ├── PROJECT_JOURNAL.md    # Master index & ADR records (ADR-001 to ADR-016)
    ├── LATENCY_TUNING_GUIDE.md # Performance parameters & latency SLAs
    ├── MEMORY_ARCHITECTURE_STANDARD.md # Triad memory & anti-hallucination standard
    └── wiki/                 # Structured Obsidian-ready documentation hub
```

---

## ⚡ Slash Commands Reference

| Command                          | Purpose                                                 | Example                                        |
| :------------------------------- | :------------------------------------------------------ | :--------------------------------------------- |
| `/skills` (or `/tools`)          | Inspect indexed skill playbooks and active MCP servers  | `/skills`                                      |
| `/worker <skill\|mcp> <task>`    | Dispatch an isolated sub-agent worker with tools/skills | `/worker git_workflow "Check branch status"`   |
| `/switch [@handle]`              | Switch active conversation to another persona           | `/switch @grace`                               |
| `/config`                        | View active runtime, performance & session settings     | `/config`                                      |
| `/config set <key> <val>`        | Tune knobs live in the active terminal                  | `/config set performance.max_context_turns 20` |
| `/delete @<handle>`              | Safely retire and archive an agent persona              | `/delete @curie`                               |
| `/save [memory\|obsidian\|both]` | Synthesize and save session takeaways                   | `/save both`                                   |
| `/vault <query>`                 | Query persona's sandboxed Obsidian notes                | `/vault architecture`                          |
| `/note <file.md> <content>`      | Create or append to a sandboxed vault note              | `/note Ideas.md Roadmap items`                 |
| `/daily <reflection>`            | Append a thought to Daily Notes/YYYY-MM-DD.md           | `/daily Completed worker refactor`             |
| `/remember <fact>`               | Save a durable fact to working memory                   | `/remember Prefers vanilla CSS`                |
| `/reset` (or `/new`)             | Reset active conversation context                       | `/reset`                                       |
| `/clear`                         | Clear terminal screen and reset context                 | `/clear`                                       |
| `/model <provider/name>`         | Temporarily override backend model                      | `/model anthropic/claude-3-5-sonnet`           |
| `/help`                          | Show command reference                                  | `/help`                                        |
| `exit` (or `quit`)               | End session and trigger save flow                       | `/exit`                                        |

---

## 🚀 Quickstart

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for `npx` MCP servers)
- (Optional) [Ollama](https://ollama.com/) for local offline models.

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/studiodamiro/sympose.git
cd sympose

# Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

### 4. Running Sympose

```bash
# Launch interactive macOS Terminal Hub
chmod +x chat.sh
./chat.sh

# Or launch Slack Socket Mode Daemon
./chat.sh --slack
```

---

## 📜 Documentation & ADRs

- **[Master Journal & ADR Index (`docs/PROJECT_JOURNAL.md`)](file:///Users/damiro/Development/sympose/docs/PROJECT_JOURNAL.md)**: Architectural Decision Records from ADR-001 through ADR-016.
- **[Latency & Performance Tuning Guide (`docs/LATENCY_TUNING_GUIDE.md`)](file:///Users/damiro/Development/sympose/docs/LATENCY_TUNING_GUIDE.md)**: Complete parameter catalog governing sub-second SLA.
- **[Autonomous Agent Memory Architecture Standard (`docs/MEMORY_ARCHITECTURE_STANDARD.md`)](file:///Users/damiro/Development/sympose/docs/MEMORY_ARCHITECTURE_STANDARD.md)**: Triad memory management, shadow extraction, and anti-hallucination grounding.
- **[Wiki Documentation Hub (`docs/wiki/index.md`)](file:///Users/damiro/Development/sympose/docs/wiki/index.md)**: Comprehensive guide to skills, MCP workers, and profile systems.
