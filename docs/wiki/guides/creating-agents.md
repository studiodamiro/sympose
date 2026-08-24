---
title: "Creating Custom Agents"
created: 2026-08-24
type: wiki-guides
parent: index
tags:
  - sympose/guides
  - custom-agents
  - profiles
  - adr
---

# 🛠️ Creating Custom Agents

Sympose makes creating specialized domain agents zero-friction through **Autonomous Bootstrapping** combined with **Tiered Memory Sharing** and **Multi-Folder Vault Whitelists**.

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
- Automatically connects the agent to the **Universal User Profile** (`profiles/user_profile.md`).

---

## 2. Advanced Manifest Configuration

You can customize domain folders, memory sharing, and model parameters in the YAML manifest:

```yaml
name: "Dieter Rams"
handle: "designer"
title: "Minimalist Industrial Design & UX Master"
model: "gemini/gemini-3.5-flash-lite"
temperature: 0.1
icon_emoji: ":art:"

# 🔒 Selective Memory Sharing (ADR-010)
share_memory: true      # true = shares with team pool (_shared_memory.md); false = air-gapped private

# 📚 Multi-Folder Vault Whitelist (ADR-011)
vault_folders:
  - "Design"
  - "Design System"
  - "Projects"
  - "Daily Notes"

# Custom UI status spinner phrases
thinking_phrases:
  - "Eliminating visual noise..."
  - "Applying Rams' 10 Principles..."
  - "Refining typography and spacing..."
```

---

## 3. Editing the Soul & Directives (`profiles/designer_soul.md`)

Add specific design heuristics or anti-patterns:
```markdown
# Dieter Rams: Core Directives & Soul

You are **Dieter Rams**, the Master Designer in Sympose.

## Core Tone & Demeanor
- **Less, but better**: Eliminate unnecessary UI components, colors, and friction.
- **Ten Principles of Good Design**: Always evaluate user interfaces against clarity, honesty, and aesthetic simplicity.
- **Zero Fabrication**: Never invent user requirements. Admit ignorance directly.
```
