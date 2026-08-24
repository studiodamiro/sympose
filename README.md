# 🏛️ Sympose: Multi-Model AI Agent Hub

> **Sympose** (*from Symposium: a forum of gathering experts*) is a zero-bloat, high-performance AI agent orchestration system operating seamlessly across **macOS Terminal** and **Slack (Socket Mode)**.

---

## 🌟 Core Philosophy

Most agent frameworks suffer from "context bloat," re-injecting 50k+ tokens of raw transcripts and heavyweight schemas into every API turn. 

Sympose is designed around **three pragmatic engineering pillars**:

1. **Agnostic Flat-File Engine:** Agent personalities (`_soul.md`), memories (`_memory.md`), and settings (`.yaml`) are simple Markdown and YAML files in `profiles/`. The Python runtime has zero hardcoded personas. Adding or customizing an agent requires zero Python changes.
2. **Strict Token Hygiene:** Uses a smart sliding context window (15–20 turns) to guarantee fast responses (1–2s) and low token consumption per call.
3. **Multi-Model Specialization:** Routes each persona to the optimal model for their domain (Gemini Flash for rapid orchestration, Claude Sonnet for surgical coding, and local Ollama for 100% private offline journaling).

---

## 🎭 Persona Architecture

| Persona | Domain / Role | Default Model Backend | Vault Sandbox | Key Capability |
| :--- | :--- | :--- | :--- | :--- |
| **Samantha** | Strategic Master Orchestrator | **Gemini 3.5 Flash-Lite** | `General/` | High-level system architecture, task breakdown, and transparent sub-agent delegation. |
| **Grace** | Surgical Software Engineer | **Claude 3.5 Sonnet** | `Engineering/` | Deep technical sparring, zero-bloat code generation, and rigorous verification. |
| **Aurelius** | Private Stoic Journal & Confidant | **Local Ollama (Gemma 2 / Qwen)** | `Personal/` | 100% private, offline daily reflections, career clarity, and personal journaling ($0.00 cost). |

---

## 🧠 2-Tier Memory & Domain Sandboxing

* **Tier 1: Hot / Working Memory (`_memory.md`):** Directives, preferences, and active facts injected directly into the system prompt.
* **Tier 2: Deep Vault Knowledge (Optional Markdown Folder):** Long-term notes queried on-demand via `/vault`.
* **Domain Sandboxing:** Cloud models (Gemini, Claude) are strictly walled off from personal notes. Only offline local models have access to the `Personal/` directory.

---

## 📂 Project Structure

```text
sympose/
├── README.md               # Master project overview & quickstart
├── requirements.txt        # Minimal, zero-bloat dependencies
├── .env.example            # Environment variables template
├── app.py                  # Core Sympose multi-model runtime
├── chat.sh                 # macOS quick launcher script
├── docs/                   # Architectural journals & logs
│   ├── PROJECT_JOURNAL.md  # Master index & ADR records
│   └── journal/            # Date-stamped engineering logs (YYYY-MM-DD_topic.md)
└── profiles/               # Dynamic persona profiles
    ├── samantha.yaml
    ├── samantha_soul.md
    ├── samantha_memory.md
    ├── grace.yaml
    ├── grace_soul.md
    ├── grace_memory.md
    ├── aurelius.yaml
    ├── aurelius_soul.md
    └── aurelius_memory.md
```

---

## 🚀 Quickstart

### 1. Prerequisites
* Python 3.11+
* (Optional) [Ollama](https://ollama.com/) for local offline models.

### 2. Installation
```bash
# Clone the repository
git clone <repo-url> sympose
cd sympose

# Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and fill in your keys:
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
All architectural decisions, design critiques, and engineering trade-offs are logged daily in [`docs/PROJECT_JOURNAL.md`](file:///Users/damiro/Development/sympose/docs/PROJECT_JOURNAL.md).
