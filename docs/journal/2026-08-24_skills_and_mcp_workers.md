---
entry: 2026-08-24
created: 2026-08-24 23:25
type: daily-log
project: sympose
tags:
  - sympose/skills
  - sympose/mcp
  - sympose/workers
  - architecture/sub-agents
---

# 🧠 Engineering Journal: Modular Skills & MCP Ephemeral Sub-Agent Worker Architecture

> **Date:** August 24, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Grace (Rear Admiral Grace Hopper Persona)  

---

## 🎯 Focus & Objectives
1. Implement a zero-bloat, open-standard **Modular Skills System (`SKILL.md`)** for procedural playbooks.
2. Build an **Ephemeral Sub-Agent Worker Engine** using Anthropic's **Model Context Protocol (MCP)** standard over local `stdio` JSON-RPC 2.0 pipes.
3. Prevent context pollution and token bloat on primary conversational agents (Samantha, Grace, Aurelius).
4. Implement **Deterministic Native Execution Tools (`run_command`, `read_file`)** to guarantee ground-truth reality and prevent LLM hallucination.
5. Create an **In-Turn Proactive Synthesis Loop** where primary agents immediately deliver executive summaries and next steps right after sub-agent tool runs.

---

## 🏗️ Architectural Decisions Recorded (ADR Index)

### ADR-012: Modular Procedural Skills System (`SKILL.md`)
* **Context**: Agents needed reusable domain heuristics (Git Hygiene, Code Review, Strategic Decision-Making) without modifying their core identity souls (`_soul.md`).
* **Decision**: Adopt the open standard `skills/<skill_name>/SKILL.md` format (YAML frontmatter + markdown playbook body).
* **Implementation**:
  * [`sympose/skills.py`](file:///Users/damiro/Development/sympose/sympose/skills.py): `SkillManager` automatically discovers, parses, and formats skills into system prompt blocks.
  * Manifest integration: Profiles specify `skills: [git_workflow, code_review]` in `profiles/*.yaml`.
  * Built starter skills: `skills/git_workflow/SKILL.md`, `skills/code_review/SKILL.md`, `skills/system_architecture/SKILL.md`, `skills/strategic_analysis/SKILL.md`.

---

### ADR-013: Model Context Protocol (MCP) & Ephemeral Sub-Agent Worker Sandbox
* **Context**: Dumping 50 tool schemas into primary agents costs 5,000+ tokens per turn and pollutes conversation history with raw terminal/JSON outputs.
* **Decision**: Adopt the **Supervisor-Worker Pattern** combined with **MCP (Model Context Protocol)**.
* **Implementation**:
  * [`sympose/mcp.py`](file:///Users/damiro/Development/sympose/sympose/mcp.py): Standard-library JSON-RPC 2.0 client over `stdio` subprocesses connecting to local/community MCP servers (Filesystem, GitHub, Brave Search).
  * [`sympose/workers.py`](file:///Users/damiro/Development/sympose/sympose/workers.py): `WorkerEngine` executes isolated multi-turn tool loops. Context memory and child processes are freed upon task completion.
  * Autonomic tag: `[SPAWN_WORKER: <skill_or_mcp> | <task_instructions>]` in [`sympose/actions.py`](file:///Users/damiro/Development/sympose/sympose/actions.py).
  * Configurable knob: `performance.max_worker_tool_turns: 8` in [`config.yaml`](file:///Users/damiro/Development/sympose/config.yaml).

---

### ADR-014: Deterministic Native Tools & In-Turn Proactive Synthesis
* **Context**: When sub-agents lacked direct terminal execution tools, models attempted to simulate/hallucinate plausible mock outputs. Additionally, users were forced to ask multiple follow-up turns to get orchestrator summaries.
* **Decision**:
  1. Built [`sympose/native_tools.py`](file:///Users/damiro/Development/sympose/sympose/native_tools.py) (`run_command`, `read_file`) providing real, safe `subprocess.run` execution on macOS.
  2. Implemented strict anti-simulation directives forbidding simulated `> 🛠️ Sub-Agent Worker Report` badges.
  3. Implemented **In-Turn Proactive Synthesis** in [`sympose/engine.py`](file:///Users/damiro/Development/sympose/sympose/engine.py): upon worker completion, the primary agent immediately streams its executive synthesis and recommendations in the exact same response turn.

---

## 🧪 Verification & SLA Metrics

* **Test Suite**: 8/8 automated unit and integration tests passing in `0.034s` ([`scratch/test_skills_and_mcp.py`](file:///Users/damiro/Development/sympose/scratch/test_skills_and_mcp.py)).
* **LOC Metric**: Every package module in `sympose/` strictly complies with the **`< 200 LOC per file`** rule:
  * `sympose/native_tools.py`: 85 LOC
  * `sympose/workers.py`: 168 LOC
  * `sympose/skills.py`: 145 LOC
  * `sympose/mcp.py`: 188 LOC
  * `sympose/engine.py`: 195 LOC
  * `sympose/profiles.py`: 194 LOC
