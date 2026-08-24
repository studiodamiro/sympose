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
- A Google Gemini API Key (`GEMINI_API_KEY`) or Anthropic Claude Key (`ANTHROPIC_API_KEY`)
- *(Optional)* [Ollama](https://ollama.com/) running locally for `@aurelius` (`ollama run qwen2.5:7b`)

---

## 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/sympose.git
cd sympose

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install lean dependencies
pip install -r requirements.txt
```

---

## 3. Environment Configuration

Create a `.env` file in the project root:

```bash
# Cloud LLM API Keys
GEMINI_API_KEY="your-gemini-api-key-here"
ANTHROPIC_API_KEY="your-anthropic-api-key-here"

# Path to your local Obsidian Vault (Optional)
MASTER_VAULT_PATH="/Users/yourname/Documents/ObsidianVault"
```

---

## 4. Launching the Interactive CLI

Start Sympose with the launcher:

```bash
./chat.sh
```

Or run Python directly:
```bash
python3 app.py --persona samantha
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
