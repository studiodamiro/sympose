---
entry: 2026-09-04
created: 2026-09-04 19:37
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - adr
  - review
---

# Sympose Engineering Log: Backend Architecture & Objective-Effectiveness Review

> **Date:** Thursday, September 4, 2026
> **Topic:** Full backend audit — is the runtime logic effective against the stated objective?
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Findings recorded. Four decisions raised as **Proposed** (ADR-070 – ADR-073);
> two existing ADRs flagged for amendment; two code defects logged for direct fix.

---

## 1. Executive Summary

A line-by-line read of the `sympose/` package (`engine`, `actions`, `workers`,
`vault`, `memory`, `compactor`, `sessions`, `profiles`, `mcp` / `mcp_client`,
`native_tools`, `skills`, `commands`, `bootstrap`, `server`, `slack`, `config`,
`models`) was performed against Sympose's own objective: **zero-bloat,
local-first, sub-0.8 s TTFT, multi-model, multi-agent, sovereign vault**.

**Verdict.** The architecture is conceptually sound and genuinely zero-infra —
flat files, standard-library primitives, no daemons to maintain. The concepts
match the objective. Where the runtime *drifts* from the objective is in the
**execution of the hot path**: pre-inference retrieval work fights the latency
SLA, the primary agent relies on a brittle free-text action DSL where structured
function-calling already exists in the same codebase, and engine state is shared
across Slack daemon threads without guards. None of this is fatal; most of it is
a handful of focused changes.

Twenty findings are catalogued in §4, with evidence and remediation options.
§5 proposes the four that are genuine architecture decisions.

---

## 2. Scope & Method

- **In scope:** all backend Python modules under `sympose/`; `config.yaml`;
  `prompts/`; the `app.py` entry point; FastAPI gateway in `server.py`.
- **Out of scope:** `ui/` React dashboard, `sympose/ui.py` / `cli.py` terminal
  rendering (reviewed only where they touch engine control flow), Obsidian
  vault content.
- **Method:** static read + control-flow tracing. No profiling run was taken;
  latency claims below are derived from the code path (synchronous I/O before the
  first `litellm.completion` call), not measured.
- **Note on rule files:** `CLAUDE.md`, `PROJECT_JOURNAL.md`, and
  `docs/wiki/index.md` all reference `.agents/rules/documentation_standards.md`,
  but `.agents/` is git-ignored and absent from this workspace. This review
  followed the summarised standard in `CLAUDE.md` and the ADR/journal conventions
  observed in `docs/journal/2026-08/`.

---

## 3. What the architecture gets right — leave it alone

- The **flat-file profile / soul / memory triad** and the **`.jsonl` session
  format** — inspectable, no migration risk, no schema server.
- **`is_safe_path()` via `os.path.commonpath`** ([config.py:168](../../../sympose/config.py#L168))
  — correct directory-containment check; the sandbox *concept* in
  `VaultManager.get_allowed_dirs` is right.
- The **worker engine's use of real OpenAI-style function calling**
  ([workers.py:217](../../../sympose/workers.py#L217)) with
  `MAX_TOOL_OUTPUT_CHARS` truncation.
- **`_BACKLINK_CACHE`** mtime-keyed invalidation ([vault.py:471](../../../sympose/vault.py#L471))
  — the right pattern; it simply is not applied widely enough (see F2).
- **`atexit` MCP shutdown**, **per-file mutexes in `compactor`**, and the
  **Slack per-channel semaphore** ([slack.py:35](../../../sympose/slack.py#L35)).
- The **circuit breaker** on consecutive bot turns (`max_consecutive_bot_turns`).

---

## 4. Findings register

Severity: **Critical** (data loss / security breach likely) · **High** (breaks a
stated objective or corrupts state under normal use) · **Medium** (degrades an
objective or is a latent bug) · **Low** (hygiene / standard drift).

| ID | Area | Sev | Objective in tension | Evidence |
| -- | ---- | --- | -------------------- | -------- |
| F1 | Pre-inference vault walk on the hot path | High | Sub-0.8 s TTFT | [engine.py:158](../../../sympose/engine.py#L158), [vault.py:796](../../../sympose/vault.py#L796) |
| F2 | No mtime cache on `search_structured` / `get_folder_digest` | High | Sub-0.8 s TTFT | [vault.py:212](../../../sympose/vault.py#L212), [vault.py:96](../../../sympose/vault.py#L96) |
| F3 | `sqlite_fts` / `semantic` search modes advertised, never built | Medium | Scalable local retrieval | `.env.example`, `config.yaml` `vault.search_mode: direct`; ADR-003 |
| F4 | `build_system_prompt` re-reads ~6 files every turn, uncached | Medium | Sub-0.8 s TTFT | [profiles.py:183](../../../sympose/profiles.py#L183) |
| F5 | Primary agent uses free-text bracket-tag DSL, not function calling | High | Zero-bloat, robustness | [actions.py:31](../../../sympose/actions.py#L31), [engine.py:189](../../../sympose/engine.py#L189) |
| F6 | "Model forgot the tag" inference writes vault files on a regex guess | High | Ground-truth sovereignty (ADR-024) | [actions.py:291-308](../../../sympose/actions.py#L291-L308) |
| F7 | `execute_actions` worker recursion has no depth guard | Medium | Safety | [actions.py:166](../../../sympose/actions.py#L166) |
| F8 | Engine dicts mutated from Slack daemon threads without locks | High | Correctness under multi-agent | [engine.py:24-27](../../../sympose/engine.py#L24-L27), [slack.py:220](../../../sympose/slack.py#L220) |
| F9 | `VaultManager._last_searches` class dict + shared `"default"` key race | High | Correctness under multi-agent | [vault.py:180](../../../sympose/vault.py#L180), [vault.py:313](../../../sympose/vault.py#L313) |
| F10 | Unbounded daemon-thread spawn; compaction stampede | Medium | Zero-maintenance, perf | [memory.py:85](../../../sympose/memory.py#L85), [sessions.py:119](../../../sympose/sessions.py#L119), [compactor.py:126](../../../sympose/compactor.py#L126) |
| F11 | MCP client `_io_lock` spans whole request; out-of-order responses dropped for good | High | Correctness (amends ADR-065) | [mcp_client.py:109-140](../../../sympose/mcp_client.py#L109-L140) |
| F12 | MCP subprocess `stderr=PIPE` never drained → pipe-buffer deadlock | Medium | Resilience (amends ADR-065) | [mcp_client.py:69](../../../sympose/mcp_client.py#L69) |
| F13 | Worker `run_command`: 3-item denylist + folder-name regex is not a sandbox | High | Sovereign safety (ADR-013/026) | [native_tools.py:76-96](../../../sympose/native_tools.py#L76-L96) |
| F14 | `server.py` binds `0.0.0.0`, zero auth on any route | High | Security | [server.py:156](../../../sympose/server.py#L156); already ADR-064 (Proposed, unimplemented) |
| F15 | `is_safe_path` does not `realpath` → symlink escapes the sandbox | Low | Security (ADR-002) | [config.py:168-175](../../../sympose/config.py#L168-L175) |
| F16 | `ModelCatalog.STATIC_CATALOG` referenced but never defined → `AttributeError` offline | Medium | Defect | [models.py:60](../../../sympose/models.py#L60) |
| F17 | `DEFAULT_RECOMMENDATIONS` schema mismatch (`context` vs `context_length`) | Low | Defect | [models.py:25-30](../../../sympose/models.py#L25-L30) vs [commands.py:356](../../../sympose/commands.py#L356) |
| F18 | Every Slack thread persists a `.jsonl` session file (colons in name); prune walk scales linearly | Low | Perf / hygiene (ADR-054/067) | [engine.py:156](../../../sympose/engine.py#L156), [sessions.py:167](../../../sympose/sessions.py#L167) |
| F19 | `<200 LOC per file` standard broken | Low | Modular cleanliness (ADR-004) | `vault.py` 890, `ui.py` 749, `commands.py` 738 |
| F20 | `.agents/rules/` referenced everywhere but absent; `.gitignore` missing `.cursor/` | Low | Repo-hygiene standard | `CLAUDE.md`, `.gitignore` |

---

## 5. Finding detail & options

### F1 — Pre-inference vault retrieval blocks the first token

`PersonaEngine.chat_stream` calls `VaultManager.resolve_turn_context`
**synchronously on the main thread before `litellm.completion`**
([engine.py:158](../../../sympose/engine.py#L158)). For any vault-skilled agent
(Samantha ships `vault_recall`), that function can run several `os.walk`s and,
via `search` → `search_structured`, **read the full body of every `.md` file in
the allowed dirs**. The trigger gate (`config.yaml` `vault.search_triggers`)
includes `what`, `who`, `which`, `have`, `know`, `get`, `give`, `show`, `tell`,
`check` — nearly every question fires it. On a real Obsidian vault this is
hundreds of ms to seconds of blocking I/O before the model is even called. The
`<0.8 s TTFT` claim holds only for a tiny vault or a non-triggering message.

**Options** (raised as **ADR-070**): tighten triggers to explicit intent; move
retrieval off the pre-inference path (expose it as a tool the model calls when it
decides it needs context); or run it concurrently with prompt assembly under a
hard time budget and skip injection on miss.

### F2 — No cache on the search / digest walks

`build_backlink_index` has an mtime cache ([vault.py:471](../../../sympose/vault.py#L471));
`search_structured` and `get_folder_digest` do not. Identical repeat queries
re-walk the whole vault every turn. Applying the same
`tuple(sorted(allowed_dirs)) → (mtime, result)` pattern makes repeats O(1).
Folded into **ADR-070**.

### F3 — The pluggable search tiers were never built

`.env.example` and ADR-003 advertise `direct | sqlite_fts | semantic`. Only
`direct` exists. A stdlib `sqlite3` FTS5 index (zero new dependency, BM25 ranking
free, incremental on write) is the natural "scales to a large vault without a
vector DB" answer and is consistent with the sovereignty axiom. Folded into
**ADR-070** as the medium-term target.

### F4 — System-prompt assembly re-reads disk every turn

`ProfileManager.build_system_prompt` ([profiles.py:183](../../../sympose/profiles.py#L183))
calls `_read_file_safe` for soul, user card, shared memory, persona memory,
workspace rules, and skills on **every turn of every thread**, plus rebuilds the
peer list. Individually cheap, collectively pure waste on the hot path. Cache
each file on mtime (extends **ADR-052**).

### F5 — Two tool paradigms; the fragile one is user-facing

The primary agent emits actions as free-text tags — `[WRITE_NOTE: path | body]`,
`[SPAWN_WORKER: …]`, `[CONFIG_SET: …]` — parsed post-stream by a hand-rolled
bracket matcher ([actions.py:31](../../../sympose/actions.py#L31)). The worker
engine, in the same codebase, uses proper `tools=[…]` + `tool_choice="auto"`.
Consequences visible in the code: no schema/validation (`CONFIG_SET` coerces
types by `try int / try float` and writes `config.yaml`); a regex to *skip
documentation placeholders* because the tag syntax collides with prose about the
tag syntax ([actions.py:59](../../../sympose/actions.py#L59)); and the F6
inference fallback. Raised as **ADR-071**.

### F6 — Writing files on a guess

[actions.py:291-308](../../../sympose/actions.py#L291-L308) scrapes the model's
prose for `Reflection:` / `Key Themes:` and *infers* a `DAILY_NOTE` write when
the user's message matched `log|save|write … journal`. This writes to the vault
based on a regex guess about intent and will misfire. Directly contradicts the
ground-truth sovereignty axiom (ADR-024: "merely printing markdown does not write
files"). Recommendation: delete the fallback — if the tag was not emitted, do not
write. Part of **ADR-071**.

### F7 — Unbounded action recursion

`SPAWN_WORKER` → `execute_worker_task` → `execute_actions(pm, "worker",
synthesis)` re-parses worker output for tags ([actions.py:166](../../../sympose/actions.py#L166)).
A worker whose synthesis contains `[SPAWN_WORKER: …]` spawns again; there is no
depth counter. Add a `depth` argument to `execute_actions`, cap at 1. Part of
**ADR-071**.

### F8 / F9 — Shared mutable state under the Slack daemon

`MultiAgentSlackRunner` runs one `SlackDaemon` per persona, each dispatching
`_process_message` in a fresh daemon thread ([slack.py:220](../../../sympose/slack.py#L220)),
all sharing **one `PersonaEngine`**. `self.histories`, `self.active_vault_ctx`,
`self.model_overrides`, `self.active_sessions` are plain dicts with unguarded
read-modify-write. `VaultManager._last_searches` is a **class-level dict with a
shared `"default"` key** ([vault.py:313](../../../sympose/vault.py#L313)) that
every search clobbers — two threads searching concurrently corrupt each other's
`/read <n>` context. `_BACKLINK_CACHE` module global has no lock. Raised as
**ADR-072**.

### F10 — Background-thread sprawl

Per qualifying turn: `HeuristicGatedExtractor.extract_async` spawns a thread
running an LLM call ([memory.py:85](../../../sympose/memory.py#L85)); turn 3 spawns
`generate_smart_title_async` ([sessions.py:119](../../../sympose/sessions.py#L119));
`append_memory` → `check_and_compact_async` ([compactor.py:126](../../../sympose/compactor.py#L126))
where the trigger is `count >= threshold` and compaction is async, so every turn
between crossing the threshold and the first compaction completing spawns **its
own** compaction thread on the same file — the lock serialises the writes but
every thread still pays for the full LLM distillation. One bounded
`ThreadPoolExecutor` for all hygiene work; a single-flight guard per compaction
target. Part of **ADR-072**.

### F11 / F12 — MCP client under concurrency

`_send_request` ([mcp_client.py:109](../../../sympose/mcp_client.py#L109)) holds
`_io_lock` for the entire write→poll→read cycle (up to `timeout`, default 15 s),
so concurrent calls to one server fully serialise. Worse, it keeps only the line
whose `id` matches `req_id` and `continue`s past everything else — a response
that arrives out of order is **discarded permanently**, and the request it
belonged to blocks until its own timeout. `stderr=subprocess.PIPE`
([mcp_client.py:69](../../../sympose/mcp_client.py#L69)) is never read; a chatty
server fills the ~64 KB pipe buffer and deadlocks. Fix: one reader thread per
process parsing every line into a `{id: Future}` map; `stderr=DEVNULL` or drain
on a thread. **Amends ADR-065.**

### F13 / F15 — The worker shell "sandbox" is not one

`NativeTools.execute("run_command", …)` runs model-generated strings with
`shell=True` ([native_tools.py:76](../../../sympose/native_tools.py#L76)). Guards:
a 3-entry denylist (`rm -rf /`, `mkfs`, forkbomb) and a regex rejecting commands
that *mention the name of a sibling vault folder*. Nothing stops
`cat ~/.ssh/id_rsa`, `curl … | sh`, `git push`, `env`. It is local-first and
single-user, so this is "your machine" — but it should be a decision, not an
accident. `is_safe_path` also never `realpath`s, so a symlink inside an allowed
folder escapes it ([config.py:168](../../../sympose/config.py#L168)). Raised as
**ADR-073**.

### F14 — Unauthenticated LAN vault API

`app.py` calls `run_server(engine, host="0.0.0.0", …)`; `server.py` exposes
`/api/config` and `/api/vault/note?path=…&persona=…` with **no auth** and a
caller-chosen `persona` (a `vault_folders: ["*"]` persona ⇒ whole vault). This is
**already recorded as ADR-064 (Proposed)** and is still unimplemented. This
review re-confirms it as High priority and recommends the interim one-liner:
default `host="127.0.0.1"`, make `0.0.0.0` opt-in via env.

### F16 / F17 — `models.py` defects

`get_cached_models` returns `existing_cached_models or list(cls.STATIC_CATALOG)`
([models.py:60](../../../sympose/models.py#L60)) but `STATIC_CATALOG` is never
defined — offline with no cache file ⇒ `AttributeError` in `/model` flows. And
`DEFAULT_RECOMMENDATIONS` entries carry `context` while readers expect
`context_length`. Both are direct code fixes; no ADR needed. Logged here for
tracking.

### F18 — Slack session-file sprawl

`chat_stream` receives `session_id=th_key` (e.g. `C123:1699…:grace`) from Slack
and `SessionManager.append_turn` writes `sessions/C123:1699…:grace.jsonl` — one
file per thread, colons in the name, and `list_sessions` prunes by
`os.listdir` + `json.loads` of the first line of every file
([sessions.py:167](../../../sympose/sessions.py#L167)), which degrades linearly.
Consider not persisting ephemeral Slack threads, or date-sharding the store.
Tracked against ADR-054 / ADR-067; no new ADR.

### F19 / F20 — Standard drift

`vault.py` (890), `ui.py` (749), `commands.py` (738) exceed the `<200 LOC`
modularity rule (ADR-004); `commands.py` in particular is one ~700-line
`if/elif` chain in a single function — a `{prefix: handler}` dispatch table would
make it short and testable. Separately, `.agents/rules/` is referenced by
`CLAUDE.md` and both index tables but is not present in the workspace, and the
`.gitignore` AI-tooling block is missing `.cursor/` relative to the repo-hygiene
standard in `CONTRIBUTING.md`. Housekeeping; tracked, no ADR.

---

## 6. Decisions raised

| ADR | Title | Status | Covers |
| --- | ----- | ------ | ------ |
| [ADR-070](./2026-09-04_adr-070-hot-path-retrieval-budget-trigger-discipline.md) | Hot-Path Vault Retrieval Budget, Trigger Discipline & Indexed Search Tier | Proposed | F1, F2, F3, F4 |
| [ADR-071](./2026-09-04_adr-071-primary-agent-action-dispatch-mechanism.md) | Primary-Agent Action Dispatch — Bracket-Tag DSL vs Native Function Calling | Proposed | F5, F6, F7 |
| [ADR-072](./2026-09-04_adr-072-engine-concurrency-bounded-background-hygiene.md) | Engine Concurrency Model & Bounded Background Hygiene Pool | Proposed | F8, F9, F10 |
| [ADR-073](./2026-09-04_adr-073-worker-native-shell-allowlisting.md) | Worker Native-Shell Command Allowlisting & Symlink-Safe Path Checks | Proposed | F13, F15 |

**Amendments queued against existing ADRs**

- **ADR-065** (MCP Client Threading & Logging Standard) — add: single reader
  thread + `{id: Future}` dispatch map (F11); drain or discard subprocess
  `stderr` (F12).
- **ADR-064** (Dashboard/API Auth Plan) — re-confirmed High; adopt the
  `host="127.0.0.1"` default immediately, ahead of the full auth pass (F14).
- **ADR-052** (In-Memory Metadata Caching) — extend to cover `build_system_prompt`
  file reads (F4).

**Direct code fixes (no ADR):** F16, F17.
**Tracked housekeeping (no ADR):** F18, F19, F20.

---

## 7. Suggested sequencing

1. **Latency** — F1 + F2 + F4: tighten `search_triggers`, add the mtime cache to
   `search_structured` / `get_folder_digest`, cache the system-prompt file reads.
   Biggest objective gap, smallest change.
2. **Concurrency** — F8 + F9 + F10: bounded hygiene pool, lock (or fully
   session-key) the engine dicts, kill the `_last_searches["default"]` sharing.
3. **MCP client** — F11 + F12: reader thread + future map, `stderr` handling.
4. **Action dispatch** — decide F5/F6/F7 via ADR-071; do not leave it half-migrated.
5. **Defects & interim security** — F16, F17, and the `127.0.0.1` default (F14).
6. **Indexed search tier** (F3) and **module splits** (F19) as follow-on.

---

## 8. Next Immediate Objective

Ratify or reject **ADR-070 – ADR-073**, then land sequencing step 1 (latency) as
the first patch set. No code was changed in this review.
