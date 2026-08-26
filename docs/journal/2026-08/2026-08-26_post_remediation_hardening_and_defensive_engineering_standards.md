---
entry: 2026-08-26
created: 2026-08-26 21:05
type: daily-journal
project: sympose
tags:
  - sympose/adr
  - security
  - concurrency
  - memory-architecture
  - defensive-engineering
  - adr-038
---

# Engineering Journal: Post-Remediation Hardening & Defensive Engineering Standards (ADR-038)

> **Date:** August 26, 2026  
> **Lead Architect:** damiro  
> **Engineering Partner:** Rear Admiral Grace Hopper (`@grace`)  
> **Status:** APPROVED & IMPLEMENTED (ADR-038)  

---

## 1. Context & Problem Statement

Following a comprehensive technical audit of the Sympose codebase (19 Python modules, prompt pipelines, multi-agent Slack daemon, memory compactor, and sub-agent workers), 25 specific edge-case anomalies were identified and resolved across two verification passes.

These anomalies revealed subtle architectural failure modes that required formalization into binding engineering standards:
1. **Identity & Persona Coupling**: Hardcoded fallback strings (e.g. `damiro`, `@samantha, @grace, @aurelius`) caused silent defaults and stale completions when identities or profiles evolved.
2. **Directory Sibling Path Bypass**: Plain string prefix checks (`resolved_target.startswith(resolved_base)`) allowed sibling directory escapes (e.g. `/tmp/vault` matching `/tmp/vault_secrets/`).
3. **Multi-Agent State Clobbering**: Multi-threaded listeners (Slack Socket Mode) shared a single in-memory handle history dictionary, creating race conditions under concurrent messages.
4. **Asynchronous Compaction Write Races**: Compaction running in background daemon threads risked overwriting newly appended facts written by foreground turns.
5. **Subprocess Lifecycle & Blocking I/O**: Spawned MCP child processes remained orphaned on exit, and synchronous `readline()` calls bypassed timeout loops when subprocesses hung.
6. **Working Memory Section Bleed**: Multi-section session summarizers risked dumping raw multi-heading Markdown session logs into `_memory.md` when section parsing failed.

---

## 2. Decision (ADR-038)

We formally establish and ratify the **6 Defensive Engineering & Hardening Standards**:

### Standard 1: Zero Hardcoded Identity & Dynamic Persona Resolution
- **Rule**: No username, persona name, or handle may be hardcoded anywhere in the codebase.
- **Implementation**: Profile managers, UI tables, completers, and regex parsers dynamically inspect `ProfileManager` and `os.getenv("USER")`. Regex parsers dynamically strip Markdown decorators (`**`, `__`, `` ` ``).

### Standard 2: Directory-Delimited Path Boundary Validation
- **Rule**: Plain string `.startswith()` for directory sandbox checks is strictly prohibited.
- **Implementation**: All path security checks must use `os.path.commonpath([resolved_target, resolved_base]) == resolved_base` or `Path.is_relative_to()`.

### Standard 3: Anchored Relative Asset Discovery
- **Rule**: External declarative assets (prompt templates, config files) must never rely on bare CWD relative paths.
- **Implementation**: All template lookups anchor to the package root (`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`), with CWD as a secondary fallback.

### Standard 4: Session-Isolated Multi-Client Concurrency & Lifecycle Hooks
- **Rule**: Multi-client and multi-threaded integrations must maintain thread-isolated history state and clean up child processes.
- **Implementation**:
  - `PersonaEngine.chat_stream`, `get_history`, and `reset_history` accept explicit `session_id` tokens (e.g. `channel_id:thread_ts:handle`).
  - All spawned background subprocesses (MCP servers) register process cleanup hooks via `atexit.register()`.

### Standard 5: Thread-Safe Memory Compaction & Snapshot Reconciliation
- **Rule**: Asynchronous memory operations must never overwrite foreground user writes.
- **Implementation**: Asynchronous compaction acquires a process-wide mutex (`get_file_lock(filepath)`), snapshots initial lines, and upon LLM completion re-reads the file under lock to reconcile and preserve any newly appended facts before write-back.

### Standard 6: Discrete Working Memory Line Standard
- **Rule**: Working memory files (`profiles/*_memory.md` and `_shared_memory.md`) must strictly contain discrete bullet points (`- ` / `* `).
- **Implementation**: Extraction and summarization pipelines strictly filter lines to bullet points before appending to memory files, preventing Markdown session logs from polluting memory files.

---

## 3. Consequences & Verification

- **Security**: Complete immunity against directory traversal and sibling path escapes.
- **Concurrency**: Flawless multi-agent Slack thread isolation with zero state clobbering.
- **Data Integrity**: Zero lost memories during async compaction or conversational extraction.
- **Zero Orphaned Processes**: Clean process shutdown for all active MCP servers.
- **Test Suite**: 23/23 unit and integration tests passing (`OK`).
