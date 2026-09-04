---
title: "Modular Skills System & Playbook Specification"
created: 2026-08-24
type: wiki-agents
parent: index
tags:
  - sympose/skills
  - playbooks
  - heuristics
---

# 🧠 Modular Skills System (`SKILL.md`)

Sympose supports standardized, procedural **Skill Playbooks**. Skills allow agents to load domain heuristics, standard operating procedures (SOPs), and specialized rules without modifying the agent's core identity (`_soul.md`).

---

## 1. What is a Skill?

* **`_soul.md` (Who the agent is)**: Tone, core personality, values, and domain authority.
* **`SKILL.md` (How the agent executes)**: Reusable, structured methodologies and checklists (e.g. *Git Hygiene*, *Code Review Guidelines*, *Stoic Decision Trees*).

---

## 2. Directory Structure

Skills live in the `skills/` directory at the project root. A skill can be defined in two formats:

```text
skills/
├── git_workflow/
│   └── SKILL.md            <-- Folder-based skill (Recommended)
├── code_review/
│   └── SKILL.md
└── system_architecture.md  <-- Standalone file-based skill
```

---

## 3. The `SKILL.md` Specification

A `SKILL.md` file consists of **YAML frontmatter** followed by the **Markdown playbook**:

```markdown
---
name: "git_workflow"
title: "Git Hygiene & Atomic Branch Workflows"
description: "Disciplined version control conventions and atomic commit rules."
tags:
  - engineering
  - git
mcp_servers:
  - "github"
recommended_models:
  - "openrouter/anthropic/claude-3.7-sonnet"
  - "gemini/gemini-3.5-flash-lite"
---

# 🌲 Git Workflow Playbook

When proposing git commits:
1. Format: `<type>(<scope>): <imperative summary>`
2. Never force-push to main or protected branches.
3. Keep each commit focused on a single atomic intent.
```

### Frontmatter Fields:
| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `string` | Unique identifier (e.g. `git_workflow`). |
| `title` | `string` | Human-readable title displayed in UI and `/skills`. |
| `description` | `string` | Short 1-sentence summary of the skill's purpose. |
| `tags` | `list` | Categorization tags. |
| `mcp_servers` | `list` | *(Optional)* MCP tool servers automatically paired with this skill. |
| `recommended_models` | `list` | *(Optional)* Priority model list for ephemeral sub-agent workers executing this skill. |

---

## 4. Assigning Skills to Agents

To equip an agent with skills, add the `skills:` list to their manifest in `profiles/<agent>.yaml`:

```yaml
# profiles/grace.yaml
name: "Grace Hopper"
handle: "grace"
title: "Surgical Software & Systems Engineer"
model: "gemini/gemini-3.5-flash-lite"

skills:
  - "git_workflow"
  - "code_review"
  - "system_architecture"
```

When `@grace` starts, the runtime compiles these skills directly into her system prompt under `### Specialized Skill Playbooks & Heuristics`.

---

## 5. Non-Code Skills & Mandatory Deliverable Schemas

To prevent the **"Lazy Hand-Wave"** failure mode in research, strategic planning, or writing tasks, non-code skills must define a **Mandatory Output Schema**:

```markdown
## Mandatory Output Contract (Deliverable Structure)
Every strategic evaluation produced by this skill MUST include:
1. The Core Tradeoff (The fundamental tension in 1 sentence)
2. Option Comparison Matrix (Minimum 2 distinct paths comparing latency, cost, risk)
3. Decisive Recommendation (An opinionated path with rationale)
4. Kill Criteria / Reversal Triggers (Measurable conditions to pivot or abort)
```

When a worker executes this skill, the runtime forces the model to fill each mandatory section, completely eliminating vague hand-waving.

---

## 6. Built-in Starter Skills

| Skill Name | Path | Domain | Description |
| :--- | :--- | :--- | :--- |
| **`git_workflow`** | [`skills/git_workflow/SKILL.md`](../../../skills/git_workflow/SKILL.md) | Dev / Git | Conventional commits, atomic branch safety, and PR synthesis. |
| **`code_review`** | [`skills/code_review/SKILL.md`](../../../skills/code_review/SKILL.md) | Engineering | Zero-bloat static analysis across Blockers, Warnings, and Suggestions. |
| **`system_architecture`** | [`skills/system_architecture/SKILL.md`](../../../skills/system_architecture/SKILL.md) | Systems | Decoupled architecture, sub-second TTFT, and fault isolation. |
| **`strategic_analysis`** | [`skills/strategic_analysis/SKILL.md`](../../../skills/strategic_analysis/SKILL.md) | Strategy | Tradeoff matrices, one-way/two-way door tests, and kill criteria. |

---

## 7. Live Inspection & Commands

* `/skills` (or `/tools`): View all indexed skills and active MCP servers in your workspace.
* `/worker <skill_name> <task>`: Dispatch an isolated sub-agent worker loaded with a specific skill.
