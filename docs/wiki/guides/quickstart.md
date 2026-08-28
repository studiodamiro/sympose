---
title: "Quickstart Guide"
created: 2026-08-24
type: wiki-guides
parent: index
tags:
  - sympose/guides
  - quickstart
  - setup
---

# 🚀 Quickstart Guide

Get up and running with Sympose in less than 2 minutes.

---

## 1. Prerequisites

- **macOS** (or Linux) with Python 3.10+
- An API Key: **OpenRouter** (`OPENROUTER_API_KEY`), **Google Gemini** (`GEMINI_API_KEY`), or **Anthropic Claude** (`ANTHROPIC_API_KEY`)
- *(Optional)* [Ollama](https://ollama.com/) running locally for `@aurelius` (`ollama run qwen2.5:7b`)

---

## 2. Installation & Upgrades

### Option A: 1-Line Standalone Global Install (Recommended)
```bash
pipx install git+https://github.com/studiodamiro/sympose.git
```

To upgrade to the latest release at any time:
```bash
pipx upgrade sympose
```

### Option B: Local Developer Clone
```bash
git clone https://github.com/studiodamiro/sympose.git
cd sympose

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .
```

For the complete guide on multi-platform installation and workspace persistence, see the [Installation & Onboarding Guide](./installation-and-onboarding.md).

---

## 3. Interactive Setup Wizard

Sympose includes an automated onboarding wizard. Run:

```bash
sympose --setup
```

The wizard will guide you through:
1. Selecting your primary LLM provider (OpenRouter, Google Gemini, Anthropic, Ollama).
2. Registering your API key securely into `.env`.
3. Choosing your default baseline model (`gemini/gemini-3.6-flash` or `openrouter/google/gemini-2.5-flash`).
4. Linking your local Obsidian vault directory.

---

## 4. Launching Sympose

```bash
# 1. Interactive Terminal CLI Hub (Default)
sympose
# or: ./chat.sh

# 2. Web Dashboard & Standalone Vault Explorer (localhost:8000)
sympose --dashboard
# or: ./chat.sh --dashboard

# 3. 24/7 Slack Socket Mode Daemon
sympose --slack
# or: ./chat.sh --slack
```

---

## 5. First Conversation

Once the terminal launches, type naturally:

```
You (to @samantha | gemini-3.5-flash-lite): I need to study Svelte in December 2026.

Samantha:
Got it, damiro! Svelte's compile-time reactivity makes it an excellent choice...
[0.78s TTFT | 0.85s total | gemini-3.5-flash-lite]
```

To exit cleanly and save your takeaways:
```
You: /exit
```
