---
title: "Python Package API Reference"
created: 2026-08-24
type: wiki-reference
parent: index
tags:
  - sympose/reference
  - python-api
  - developer-guide
---

# 🐍 Python Package API Reference

The `sympose` package is organized into lean, modular components adhering to the **Single Responsibility Principle (<200 LOC per file)**.

---

## 1. Package Entry Point: `sympose`

```python
from sympose import (
    ConfigManager,
    config_manager,
    ProfileManager,
    VaultManager,
    PersonaEngine,
    TerminalInterface,
)
```

---

## 2. Core Classes

### `sympose.engine.PersonaEngine`
Executes multi-model AI completions with sliding context and autonomic tools.

```python
engine = PersonaEngine(profile_manager, max_turns=15)

# Stream response generator
for token in engine.chat_stream("samantha", "How do we structure our deployment?"):
    sys.stdout.write(token)
```

### `sympose.profiles.ProfileManager`
Discovers, bootstraps, and manages YAML agent profiles, souls, and memories.

```python
pm = ProfileManager("profiles")
profile = pm.get_profile("grace")
system_prompt = pm.build_system_prompt(profile)
pm.append_memory("grace", "Enforce strict < 200 LOC per file.")
```

### `sympose.memory.SessionArchivist`
Handles LLM-driven session summarization, heuristic gated extraction, and note persistence.

```python
archivist = SessionArchivist(pm)

# Non-blocking async shadow extraction
archivist.trigger_background_extraction("samantha", user_msg, assistant_reply)

# Session distillation
result = archivist.summarize_session("samantha", history, target="both")
```

### `sympose.vault.VaultManager`
Provides sandboxed file I/O, path validation, multi-tier vault search, and in-memory backlink indexing.

```python
is_safe = is_safe_path("/vault/Engineering/notes.md", "/vault/Engineering")
content = VaultManager.read_note(profile, "Architecture.md")
results = VaultManager.search(profile, "API design")

# Inverted Index & Backlink Lookups (ADR-044)
links = VaultManager.extract_wikilinks(content)
index = VaultManager.build_backlink_index(profile)
backlinks = VaultManager.get_backlinks(profile, "OAuth")
digest = VaultManager.get_backlinks_digest(profile, "OAuth")
```

### `sympose.config.ConfigManager`
Manages master configuration loading, validation, and dynamic updates.

```python
timeout = config_manager.get("performance.request_timeout", 10.0)
config_manager.set("performance.max_context_turns", 20)
```
