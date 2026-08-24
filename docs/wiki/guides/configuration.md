---
title: "Configuration & Live Tuning"
created: 2026-08-24
type: wiki-guides
parent: index
tags:
  - sympose/guides
  - configuration
  - live-tuning
---

# ⚙️ Configuration & Live Tuning

Sympose separates system performance and exit policies from agent manifests using a centralized [`config.yaml`](file:///Users/damiro/Development/sympose/config.yaml) file.

---

## 1. Master `config.yaml` Structure

```yaml
performance:
  request_timeout: 10.0          # Hard timeout in seconds per completion
  max_context_turns: 15          # Sliding window history slice (15 user + 15 assistant)
  drop_unsupported_params: true  # Prevents provider schema mismatch crashes
  stream: true                   # Enable real-time 60 FPS token streaming

session:
  exit_behavior:
    auto_save: false             # If true, auto-saves without modal prompt on /exit
    default_target: "both"       # Options: "memory", "obsidian", "both"
    clear_terminal: true         # Clears screen on exit for clean terminal reset
    obsidian_subfolder: "Sessions" # Subfolder in persona domain folder
    summarization_model: "gemini/gemini-3.5-flash-lite" # Fast distillation model

vault:
  search_tier: "direct"          # Options: "direct" (Pure Python), "sqlite_fts", "semantic"
  max_search_results: 5
```

---

## 2. In-Session Live CLI Tuning

You can inspect and update any configuration parameter dynamically without restarting the application:

```bash
# View active configuration
/config

# Change sliding context window size
/config set performance.max_context_turns 20

# Change default request timeout
/config set performance.request_timeout 8.0

# Enable auto-save on exit
/config set session.exit_behavior.auto_save true
```
