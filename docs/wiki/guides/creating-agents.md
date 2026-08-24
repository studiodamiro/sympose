---
title: "Creating Custom Agents"
created: 2026-08-24
type: wiki-guides
parent: index
tags:
  - sympose/guides
  - custom-agents
  - profiles
---

# 🛠️ Creating Custom Agents

Sympose makes creating specialized domain agents zero-friction through **Autonomous Bootstrapping**.

---

## 1. Quick Genesis (4 Lines of YAML)

Create a new file in `profiles/` (e.g. `profiles/designer.yaml`):

```yaml
name: "Dieter Rams"
handle: "designer"
title: "Minimalist Industrial Design & UX Master"
model: "gemini/gemini-3.5-flash-lite"
```

Start Sympose or switch to the agent:
```bash
/switch @designer
```

Sympose automatically generates:
- `profiles/designer_soul.md` (Domain directives, tone, and heuristics).
- `profiles/designer_memory.md` (Initial working memory).
- Default UI status thinking phrases.

---

## 2. Advanced Manual Customization

To manually refine your agent's behavior:

### A. Edit the Soul (`profiles/designer_soul.md`)
Add specific design heuristics or anti-patterns:
```markdown
# Dieter Rams: Core Directives & Soul

You are **Dieter Rams**, the Master Designer in Sympose.

## Core Tone & Demeanor
- **Less, but better**: Eliminate unnecessary UI components, colors, and friction.
- **Ten Principles of Good Design**: Always evaluate user interfaces against clarity, honesty, and aesthetic simplicity.
```

### B. Configure Sandboxed Vault Folders
In `profiles/designer.yaml`:
```yaml
vault_folder: "Design"
icon_emoji: "🎨"
```
The agent now has dedicated access to `{MASTER_VAULT_PATH}/Design/` for notes, design specs, and session logs.
