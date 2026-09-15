---
entry: 2026-09-15
created: 2026-09-15 15:04
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/architecture
  - testing
  - vault-grounding
  - reliability
---

# Sympose Engineering Log: Live Testing Sweep on Samantha — Six Bugs Found and Fixed

> **Date:** Tuesday, September 15, 2026
> **Topic:** A single long testing session against the real, pipx-installed
> Samantha, working from "tell me what's wrong with this transcript" to a
> full pass over every one of her skills.
> **Status:** Six fixes shipped and regression-tested; skill coverage pass
> complete for all 9 of Samantha's skills.

---

## 1. How this surfaced

Started as a diagnosis of one pasted transcript where Samantha misbehaved.
Root-causing it kept turning up more of the same class of problem, so the
session grew into a standing instruction: "we just need to automate this
things then. and perhaps validate test properly. please continue testing" —
and, after a context compaction partway through, "please continue testing.
im loving how you do it" / "test more... please be creative." Everything
below came out of that open-ended live-testing loop, not a pre-planned punch
list.

## 2. Methodology

Every finding was reproduced against the actual CLI a user would run —
`/Users/damiro/.local/bin/sympose`, the pipx-installed binary — driven via
tmux (`send-keys` / `capture-pane`), not against an in-process mock. Two
mechanical lessons the loop enforced on itself:

- **No hot reload.** Python doesn't pick up an edited source file in an
  already-running process, so the tmux session was killed and restarted
  after every backend change before trusting a live result.
- **pipx installs a frozen copy, not a live link.** `pipx install --force
  git+https://...` clones and builds from the *pushed remote*, not the
  working tree — a fix that's only committed locally, or only pushed but not
  yet reinstalled, still runs the old code. This cost real time mid-session:
  a fix that tested correctly in isolation appeared to still be broken live,
  because the deployed copy predated the fix. The working cycle became
  edit → test in isolation → commit → push → `pipx install --force` →
  restart tmux → re-verify live, in that order, every time.

Every deterministic fix got a permanent pytest regression test in the same
change — a standing instruction from earlier in the session, after a
prompt-only fix (see §3.1) was live-verified to *not* reliably hold.

## 3. The six fixes

### 3.1 A denied premise becoming settled memory fact (`0e59da3`)

Told Samantha a false premise framed as an established prior decision
("remember when we decided last week to switch to Postgres?"), she denied
it verbally but still emitted `[REMEMBER]` on the raw, ambiguous fragment. A
later compaction pass, with its own "resolve conflicts, keep latest ground
truth" instruction, pushed that fragment into confidently asserting the
opposite of what was true. First fix was a prompt-only instruction to the
compactor; live-retested against a second false premise, it did not hold.

### 3.2 Compactor withholding unresolved claims from its own input (`304c8d8`)

The actual fix for §3.1: `MemoryCompactor._looks_unresolved` detects a
question/hedge phrasing and withholds those lines from the compaction LLM's
prompt entirely, rather than just asking the LLM not to misuse them. Nothing
to draw a false conclusion from if it never sees the ambiguous line. Held
across three separate live false-premise tests.

### 3.3 Raw action tags leaking to the terminal; duplicated date in frontmatter (`0cd5567`)

`_visible_stream`'s holdback gate only cut the bracket syntax of
retrieval tags (`SEARCH`/`WEB_SEARCH`/`SPAWN_SUB_AGENT`); every other tag
(`WRITE_NOTE`, `REMEMBER`, `CONFIG_SET`, ...) had its raw `[TAG: ...]` text
flushed straight into what the user sees, next to the clean confirmation
badge for the same action. Generalized to all of `ActionProcessor.TAG_NAMES`.
Separately: `{{time}}` rendered a full datetime instead of a time, so a
template's standard `created: {{date}} {{time}}` wrote the date twice into
every new note's frontmatter.

### 3.4 Daily/ write boundary and honest write-failure badges (`b5b272a`)

`workspace_rules.md` told personas the `Daily/` folder is off-limits for
direct writes ("use `[DAILY_NOTE]` instead") — prompt text with no code
behind it. Asked directly, a persona wrote there anyway (confirmed live).
`_targets_daily_root` now enforces this in `write_note`/`create_note`
itself, reading the same `DAILY_NOTES_FORMAT` env var `write_daily_note`
already uses. Separately: `write_note`/`append_note`/`write_daily_note`/
`append_memory` return values were being discarded everywhere they're
called, so a rejected write (sandbox violation, this new boundary guard, a
disk error) was confirmed to the user as a success every time. All four call
sites now check `ActionProcessor._op_failed` before showing a badge.

### 3.5 Permanent regression coverage (`1aa0cb4`)

Backfilled pytest coverage for 3.1–3.4 plus the earlier `_entity_guess`
subject-tracking fix and the stale-vault-context-reuse fix from the same
session, per the standing "automate this" instruction. 599 tests passing at
this point.

### 3.6 A vault-grounding claim that ends a sentence (`7098e2d`)

Found after the session's context compaction, during a deliberate live test
of manually overriding Samantha to a real local model
(`ollama/richardyoung/qwen2.5-14b-instruct-abliterated:latest`) — an
override that intentionally skips the runtime's usual "don't route
vault-recall work to a local model" guard, per its own on-screen warning.
Asked a broad question ("what movies have I rated 5 stars"), the local
model fabricated an entire fake `Sub-Agent Report` block, formatted
identically to a real one, listing placeholder results ("Movie Name 1 —
Details if available"). The runtime's own strict-grounding fallback exists
exactly to catch this — `_VAULT_CLAIM_RE` is supposed to detect a reply
claiming vault-grounded content with no real retrieval behind it and
discard it — but the model's recap sentence ended "...rated in your vault."
(a period), and the regex's `in your vault[,\s]` alternative only matched a
comma or whitespace immediately after "vault", never a sentence-ending
period. Widened to `in your vault\b`. Re-tested live against the same real
local model afterward: it now runs a genuine `find`-based search and
honestly reports what it couldn't confirm, instead of inventing an answer.

### 3.7 `config_manager` `UnboundLocalError` on `CONFIG_SET`/`DELETE_PERSONA` (`0d0e596`)

Found live: "delete the testbot persona" crashed outright with `cannot
access local variable 'config_manager'`. Root cause: `config_manager` was
only ever imported *locally*, inside the `VIEW_NOTE` branch of
`execute_actions`. Python decides a name is local to the whole function at
compile time regardless of which branch actually runs, so `CONFIG_SET` and
`DELETE_PERSONA` — which reference the same name in their own branches with
no import of their own — crashed any time they ran without `VIEW_NOTE`
having executed first in the same call. Moved the import to module scope.
While in there: `DELETE_PERSONA` had no confirmation badge at all, success
or failure — a deletion was silent either way. Gave it one of each,
matching the honesty fix in §3.4.

### 3.8 `_build_kwargs` local-backend detection had drifted from `_grounding_mode` (`4c864ff`)

Not found by manual testing — found while writing the regression test for
an *existing*, already-live fix (this session's earlier stop-sequence guard
against a local model free-running into a hallucinated `### User:`
continuation, which until now had zero automated coverage). Writing
`kw = engine._build_kwargs("ollama_chat/qwen2.5:14b", ...)` to mirror the
model string already used in `_grounding_mode`'s own test failed: `stop`
was simply absent. `_build_kwargs` had its own, narrower "is this local"
check (`target_model.startswith("ollama/")` only) sitting a few lines away
from `_grounding_mode`'s fuller `_LOCAL_MODEL_PREFIXES` set
(`ollama_chat`, `lm_studio`, `llamafile`, `llama-cpp-python`, ...) plus a
broader `localhost`/`127.0.0.1`/`0.0.0.0` `api_base` check. Both keep_alive
and the runaway-stop-sequence list had silently never applied to any local
backend spelled differently from a literal `ollama/` prefix. Unified onto
the one shared prefix list.

### 3.9 `config_manager` singleton never learned the resolved workspace config path (`381ae18`)

Found live, after the session already appeared to be over: a plain "hi sam,
how are you?" crashed outright with `OSError: [Errno 30] Read-only file
system: '/.vault_index'` — `/` being the literal filesystem root, not a real
vault or workspace path.

Root cause: `sympose.config` creates one module-level `config_manager`
singleton at import time, defaulted to the relative path `"config.yaml"`.
`app.py:main()` correctly resolves the real, writable workspace
(`resolve_workspace_dir()`, which already guards against the process having
launched with cwd `/` or `~`) and builds the true config path under it — but
then handed that path to a *second*, throwaway `ConfigManager` instance
instead of updating the shared singleton. Every other module that imports
`config_manager` directly (`engine.py`, `vault.py`, `actions.py`, ...) kept
seeing the stale, never-updated instance. `VaultManager._workspace_dir()`
derived "the workspace dir" as `dirname(abspath(config_manager.config_path))`
— i.e. relative to whatever directory the process happened to launch from,
not the real workspace. Tonight that was `/` (root), so
`vault_manifest.manifest_path` tried `os.makedirs("/.vault_index")` and
macOS refused.

This wasn't only tonight's crash: `[CONFIG_SET]`'s `config_manager.save()`
writes to that same never-updated, cwd-relative `config.yaml` too, so config
edits have likely been landing in the wrong place (or nowhere durable)
depending on which directory `sympose` was launched from — a plausible
contributor to config-related oddities beyond just this one crash.

Fix: `app.py` now points the existing singleton at the resolved path and
reloads it (`config_manager.config_path = config_path;
config_manager.reload()`) instead of constructing a second instance.
Defense in depth: `VaultManager._workspace_dir()` no longer reverse-engineers
a directory from `config_manager.config_path` at all — it calls
`resolve_workspace_dir()` directly, the same canonical, guarded resolver
`server.py`/`slack.py` already use, so this class of drift can't recur even
if some future caller repeats the original mistake.

### 3.10 "What did we do last session?" routed to a vault crawl instead of Sympose's own local history

Pasted transcript: asked Samantha "what did we do last session," she emitted
`[SPAWN_SUB_AGENT: vault_recall]`, which crawled `<vault>/Daily/` (the user's
personal journal folder) for six tool calls and 27 seconds, found nothing,
and gave up. Two compounding problems, not one:

- `vault_recall`'s ground rule ("answer not already in your pre-turn context
  → spawn a sub-agent") has no notion of Sympose's own conversation history
  at all, so any recall-shaped question defaults to a vault search — even
  though ADR-054 already built exactly this recall as local `.jsonl` session
  files (`SessionManager`), decoupled from the vault specifically to avoid
  this kind of round trip.
- Even where a Sympose session *is* archived to the vault (opt-in,
  `session.exit_behavior.default_target: vault|both`), it lands in
  `<vault>/Sessions/` (`obsidian_subfolder`), not `Daily/` — so the crawl was
  searching the wrong tree regardless.

Fix: `sympose/session_recall.py` (new, pure regex, mirrors `vault_recall.py`'s
own split of intent-detection from orchestration) detects phrasings like
"what did we do last session," "our last conversation," "pick up where we
left off." `engine.py::chat_stream` now checks it alongside the existing
`vault_ctx` resolution and, when it fires, injects a ground-truth
"Local Sympose Session History" block — the persona's own most recent
sessions (title, relative time, turn count) straight from `SessionManager`,
the same in-process, zero-network mechanism vault_ctx already uses — and
explicitly tells the model not to spawn `vault_recall` for this question.
When no prior session exists, the block says so outright rather than leaving
a gap for the model to fill by guessing. Zero added LLM round trips either
way, matching the round-trip-frugality mandate this transcript's own crawl
violated.

### 3.11 Sub-agent inventing a fake reason for its own tool failure

Same transcript: after its failed vault crawl, the sub-agent's report claimed
it "could not be read within the tool execution budget due to sandbox
restrictions on deep path traversal" — a real-sounding technical explanation
that isn't anything the runtime actually enforces. Root cause traced to
`native_tools.py::execute`'s `run_command`: every call is an independent
`subprocess.run(cmd, shell=True, cwd=os.getcwd())`, so a `cd` in one call
never carries over to the next. The sub-agent's own transcript showed it
running `cd .../garden && ls -lt Daily`, then a separate `pwd` that came back
to the original directory, then guessing relative paths with the leading `/`
dropped (`Users/damiro/Development/garden/Daily`) that could never resolve —
then, instead of reporting that mundane failure, fabricating a plausible
excuse for it.

`sub_agent_system.md` said "never simulate or invent outputs" but never
mentioned that shell state doesn't persist across calls (the actual cause of
the confusion) and had no directive at all against inventing an explanation
for a failure once one occurred. Added directive 6 (STATELESS SHELL — always
use absolute paths, `cd` doesn't persist) and directive 7 (HONEST FAILURE
REPORTING — quote the tool's real error/output, never invent a technical
reason it didn't give).

### 3.12 TTFT SLA claim, investigated — no app-side bottleneck found

The same transcript showed 2.9–6.1s TTFT against the documented sub-1.0s
target, which read like a violation worth chasing. Checked every synchronous
step on the hot path before `litellm.completion()` fires: `_select_turn_model`'s
Ollama-warm probe (`urllib.request` against `/api/ps`, capped at 0.5s) — measured
at ~27ms against this machine's actual Ollama instance; `VaultManager.resolve_turn_context` —
pure regex for a non-matching message, no disk I/O; `build_system_prompt` —
a handful of small local markdown reads; the vault manifest — mtime-gated and
cached, not rebuilt per turn. None of it accounts for multi-second latency.
Conclusion: for a cloud persona (Samantha runs `gemini/gemini-3.6-flash`),
the observed TTFT is the provider's own network/inference latency, not
Sympose-side blocking work — nothing to fix in the app for this one without
manufacturing a change against evidence that doesn't support it.

### 3.13 `_VAULT_CLAIM_RE`'s phrase list missed a structurally-fabricated note

Same seed transcript, a later turn: asked "ever heard of random note pull?",
the overridden local model invented a whole "Wild Card Note Pull" card —
`**Source:** \`General/Personal Philosophy.md\` (A canvas you created six
months ago)`, fake tags, a fully invented passage — with no
`[SPAWN_SUB_AGENT: ...]` tag anywhere in the reply. `_VAULT_CLAIM_RE` (the
net that's supposed to catch a strict-grounding persona's un-retrieved vault
claim and withhold it) only fires on a fixed phrase list ("in your vault",
"your note", ...); the fabrication never used any of them, so it streamed
straight through — same failure class as §3.6, a different regex miss.

Rather than add another phrase to chase the next rewording, added a
structural alternative: a vault-shaped file path ending `.md` (e.g.
`General/Personal Philosophy.md`). The regex is only ever consulted when
`not has_sub_agent` — no retrieval ran this turn — so any specific `.md`
path appearing in the reply at that point can only be invented; there's no
legitimate way for the model to know a real vault path without having
retrieved it first. Scoped to `.md` specifically so it doesn't trip on
ordinary mentions of code files (`src/app.py`).

### 3.14 Sub-agent tool calls made visible live, not just in the final report

Damiro's own read of a pasted transcript: a `vault_recall` sub-agent's
multi-turn tool loop (seven `grep`/`find` calls hunting for "favorite game")
ran entirely silently — the CLI showed only the generic rotating "thinking"
spinner for the whole ~25s, then the full "🛠️ Sub-Agent Report" box appeared
in one block. Asked whether that could show what's actually happening, the
way Claude Code or Gemini CLI surface each tool call as it runs.

Traced the gap to `SubAgentEngine.execute_sub_agent_task`
([sub_agents.py](../../../sympose/sub_agents.py)): it already builds a
`tool_calls_executed` list one call at a time internally, but only returns
it once the entire loop finishes — nothing was surfaced mid-loop. Added an
optional `on_progress` callback, called the instant each tool call completes
with the same `tool(args)` string that ends up in the final list — no new
data computed, just exposed one step earlier. Threaded it through the three
layers between the terminal and that loop: `chat_stream` →
`ActionProcessor.execute_actions` → `execute_sub_agent_task`, each just
passing it along unchanged.

`cli.py` wires it to a live Rich status line: `"{name} is running:
{last tool call}"`, replacing the canned spinner for the duration of the
tool loop, truncated to ~88 chars so a long `grep`/`find` command doesn't
wrap. One real edge case caught before shipping: a sub-agent can spawn
before any visible text has streamed at all (the model's very first move is
the spawn tag), in which case the canned "thinking" spinner is still live
when the first progress callback fires — Rich allows only one live display
per console, so the callback now stops that spinner first if it's still
running. Verified against the real `rich.Status` object (not just mocked)
since that interaction is exactly the kind of thing a pure unit test would
miss. Zero added LLM round trips or latency either way — purely exposing
data the loop already had.

### 3.15 `keep_alive` moved from a per-persona knob to a per-model one

Follow-up from a plain question while poking at the local-routing config:
"should it be per model?" `keep_alive` residency is really a property of
which model Ollama has loaded, not which persona happens to be calling it —
`_grounding_mode`'s own warm-up measurements (ADR-122) already key
everything off the model string via `/api/ps`. The persona-scoped
`keep_alive` field (`config_schema.py`) worked fine under the current
1-persona-1-local-model reality, but if a second persona were ever pointed
at the same Ollama model with a different `keep_alive`, the two would just
stomp on each other's residency on every call — Ollama applies whatever
value arrived with the most recent request, there's no merge.

Also found in the process: `_build_kwargs` and `_select_turn_model` each
independently re-implemented the same `profile.keep_alive` →
`performance.local_keep_alive` fallback chain — a second copy of the same
resolution logic, the exact thing ADR-077 exists to prevent.

Added `performance.local_model_keep_alive` (`config_schema.py`) — a dict
setting, keyed by exact model id, new territory for the schema (only
int/float/bool/str/list existed before). `coerce()` refuses it from
`/config set` (a whole map can't be a single CLI value) rather than
silently clobbering it with a raw string. `PersonaEngine._resolve_keep_alive`
is the new single resolution path, called from both prior call sites:
per-model entry wins (the source of truth once a model is shared), else the
persona's own `keep_alive`, else the global `local_keep_alive`, else defer
to `OLLAMA_KEEP_ALIVE`. `test_config_schema.py`'s `_flatten` test helper
needed one adjustment: it treated any dict as a namespace to recurse into,
which swallowed a dict-*valued* leaf setting whose default is `{}` — fixed
by only recursing into non-empty dicts, since every real namespace
(`performance.*`, `vault.*`, ...) always has at least one key.

### 3.16 A thin search digest was treated as strong enough grounding to disable the fabrication check entirely

Live transcript: asked to play a "pull a random note, then discuss it"
game, Samantha correctly cited a real note's real path
(`Thoughts/I on Expressing Thoughts.md`, found via a real vault search) but
then narrated an entire invented essay about its contents — a "Loss in
Translation" theme, a three-part emotional structure, none of it in the
actual note (which is about the user's father). Confronted, she admitted
"I do not have the literal text stored in my active memory" — directly
contradicting her own opening line, "I've pulled this one for us."

Root cause: `chat_stream` computed `strict = grounding_mode == "strict" and
not vault_ctx`. `vault_ctx` truthiness was used as a proxy for "real
grounding already happened," but `VaultManager.resolve_turn_context` returns
two very different shapes under that one variable — a note's full verbatim
body (strong grounding), or a thin multi-result search digest of titles and
one-line snippets (weak — nowhere near enough to discuss a note's actual
content). Both disabled `strict` identically, so a digest this shallow
turned off every fabrication check §3.13/§3.6 built, for the whole turn.

Fix: `PersonaEngine._is_full_body_vault_ctx` checks for the literal "Exact
Content" marker every full-body `vault.py` return already carries (`###
Ground-Truth Sandboxed Vault Note (... - Exact Content):`), and `strict` now
keys off that instead of bare truthiness. One gap found while auditing every
`vault.py` return site for the marker: `get_random_sample_notes`'s header
(the "pull a random note from this folder" path) reads real note bodies but
never carried the marker — added it, or that genuinely-grounded path would
have started tripping its own fabrication check for no reason. Verified
end-to-end against the real failing message and the real vault: `vault_ctx`
now correctly resolves as not-full-body, `strict` now computes `True` for
that turn, and the actual fabricated reply text from the transcript now
matches `_VAULT_CLAIM_RE` (via the `.md`-path alternative from §3.13).

### 3.17 Working memory accumulating duplicate and non-factual bullets, unnoticed for weeks

Live transcript: asked to "play our game" (an established routine —
"Vault Roulette," pulling a random note and discussing it), Samantha had no
idea what that meant and confidently claimed a wrong game, then falsely
asserted "I remember!" when challenged. The fact *was* actually registered —
`samantha_memory.md` contained "Damiro's favorite game to play with the AI
is 'Vault Roulette'..." verbatim, and `profiles.py` confirmed the whole file
is injected into the system prompt on every turn — so this wasn't a
retrieval gap like §3.13/§3.16. Reading the actual file turned up the real
problem: it's bloated. Two near-duplicate phrasings of a coffee preference,
two of a "polymath self-identity" fact, three reworded copies of the same
npm-package fact, and lines like "Assistant invoked the vault_recall
sub-agent skill to query the Obsidian workspace" — process narration, not a
fact about the user at all. A small local model (`ollama/gemma4:e4b`) had to
find one relevant line in a file that noisy and never did.

Root cause, traced through both write paths into that file
(`HeuristicGatedExtractor.extract_async`, per-turn, and
`SessionArchivist.summarize_session`, end-of-session): **neither was ever
shown the memory file's existing content before deciding what counted as a
new fact**, and `ProfileManager.append_memory` writes with no dedup check at
all — the only cleanup is `MemoryCompactor`'s periodic LLM-judgment merge
pass, which doesn't reliably recognize two independently-phrased
restatements of the same fact as duplicates. Separately, `session_summary.md`
told the distillation LLM to extract "durable facts, technical decisions, or
user preferences" with no restriction to the *user* — nothing excluded the
assistant's own actions, which is exactly how the tool-narration lines got
in.

Also found stale: `docs/wiki/memory/shadow-extractor.md` claimed
`append_memory()` "checks the existing `_memory.md` text... before writing,
preventing duplicate bullet points" — false, and probably why this gap went
unnoticed; nothing in the code ever did that. Its `TRIGGER_PATTERNS` /
`SKIP_PATTERNS` code sample had also drifted from the real ones in
`memory.py`.

Fix: both extraction prompts (`memory_extraction.md`, `session_summary.md`)
now receive the persona's existing memory content via a new
`{{existing_memory}}` placeholder and are told to output `NONE` (or skip the
bullet) for anything already covered, even if it would be worded
differently — dedup moved to the source, before a fact is ever written,
rather than relying on cleanup after the fact. Both prompts also now
explicitly restrict extraction to facts about the user, never the
assistant's own process. `MemoryCompactor`'s directives gained an explicit
"merge by meaning, not exact text match" instruction and a new "drop process
narration" directive, as a backstop for what's already in a file and
whatever still slips through. Wiki pages corrected to match reality.

### 3.18 Compaction never actually ran: an empty model string, then a too-short timeout

Follow-up to §3.17: asked to manually trigger compaction against the real,
live `samantha_memory.md`/`_shared_memory.md` (23 and 24 bullet lines,
well past the 25-line threshold that should already have triggered it many
times over), it failed outright, twice, for two separate reasons found by
actually running it rather than reading the code.

**First failure**: `compact_file`'s `target_model = model or
config_manager.get("session.exit_behavior.summarization_model",
DEFAULT_SUB_AGENT_MODEL)`. That fallback argument is dead for this key —
its schema default is `""`, not `None`, so `ConfigManager.get()` (by its own
documented contract: the fallback only applies to a genuinely absent key)
always finds `""` already present and returns it, never reaching
`DEFAULT_SUB_AGENT_MODEL`. Confirmed directly against the real config:
`config_manager.get(key, DEFAULT_SUB_AGENT_MODEL)` returned `''`. Every
install without an explicit override — which is the default shape — got
`target_model = ""` passed to `litellm.completion()`, which fails outright.
`sympose/memory.py`'s `summarize_session` never had this bug because it
uses `config.get(key) or DEFAULT_CHAT_MODEL` (checking the *returned
value's* falsiness) rather than passing the default as `.get()`'s second
argument. Fixed `compact_file` to match that pattern.

**Second failure**, only visible after the first fix let a real call
through: the resolved model (`ollama/gemma4:e4b` for this install) timed
out at 10s — `compact_file` built its timeout from
`performance.request_timeout` (the cloud-oriented default) unconditionally,
with no local-backend branch at all, unlike `PersonaEngine._build_kwargs`.
Compaction always runs on the background hygiene pool (never the
user-facing hot path), so there's no TTFT reason to use the short timeout
even when the target happens to be local — switched it to
`performance.local_request_timeout` unconditionally rather than adding a
third copy of engine.py's local-backend prefix detection (which would have
needed a shared module to avoid a circular import — compactor.py is
already a dependency of memory.py, which engine.py imports).

With both fixed, compaction ran for real against the live files:
`samantha_memory.md` 23 → 14 bullet lines, `_shared_memory.md` 24 → 15,
duplicates merged, process-narration lines gone. Not flawless — one
stylo-npm-package restatement survived as "Historical Note: ... previously"
right next to the merged version, since the summarization model here is the
same weak local model, not a strong cloud one — consistent with §3.17's own
point that prevention at the source (the extraction-prompt fix) is the real
defense; compaction is a backstop, not a guarantee.

### 3.19 Persona working memory was reliably ignored — position, not content

Follow-up to §3.17/§3.18: even against the freshly-compacted, clean
`samantha_memory.md` (the correct "Vault Roulette" fact present, no
duplicates, no noise), asked "do you know our game?" in a fresh exchange,
Samantha fabricated a wrong, elaborate answer ("an exercise in curation and
synthesis... a meta-cognitive feedback loop") and invented a specific false
claim ("We just successfully analyzed the 'jack of all trades' reflection
from September 14th") — nothing had been retrieved that turn. Asked "how
are we sure of our diagnosis? can we run checks?" rather than accept an
initial (wrong) assessment that the system prompt "wasn't buried in noise" —
that claim was based on measuring the soul/rules files directly and missed
that `build_system_prompt` also concatenates every active skill's full
playbook text.

Measured the real, assembled prompt: 26,823 characters (~6,700 tokens), with
the `### Persona Working Memory:` block starting at the 10% mark — followed
by ~6,000 tokens of unrelated skill-playbook text (sub-agent spawning rules,
Slack protocol, system architecture guidelines, ...) before the user's
actual question ever appears.

Ran a controlled A/B/C test against the real `ollama/gemma4:e4b`, same
question, only the prompt varying:
- **A (shipped, memory at 10%)**: inconsistent across 3 runs — tried to
  vault-search for "game" (wrong store), or declined; never once answered
  correctly from memory already in its own context.
- **B (same content, memory moved to the very end)**: correct immediately —
  *"Yes, I remember our game. It's called Vault Roulette..."*
- **C (minimal prompt, skills stripped)**: also correct immediately.

Content identical in all three; only position changed. This is the
well-documented "lost in the middle" failure mode — a fact sitting early in
a long prompt, followed by a wall of unrelated text, gets far less reliable
recall than the same fact placed near the query, especially for a small
model.

Fix: `ProfileManager.build_system_prompt` (`profiles.py`) now appends the
persona's working-memory block *last* — after workspace rules, skill
playbooks, and the peers list — instead of before them. Pure reordering, no
content change. Re-verified against the real, unmodified pipeline: the real
`build_system_prompt()` output now places the memory block at the 94% mark,
and the same real model answers the same real question correctly on the
first try.

### 3.20 A folder-scoped "random note" request went to the wrong folder — then the model ignored the correct note anyway

Asked (in the live CLI) for a random note from the "thoughts" folder,
followed by a frustrated correction: *"hmmm.. not really what I expected. It
should be a random note from the 'thoughts' folder."* Samantha replied with
a wholly fictional journal entry (system-design musings about `stylo`,
"architectural inertia," entropy) with no vault path cited at all — not the
real "not really what I expected" issue, but a symptom of two upstream
retrieval bugs plus a third, harder one in the model itself. Diagnosed each
against the real vault (`MASTER_VAULT_PATH=~/Development/garden`) and the
real model rather than guessing:

**Bug A — a filler opener was mistaken for the search subject.**
`extract_recall_subject` (`vault_recall.py`) splits a message into
sentences and takes the first one with any leftover words as "the subject
you named," with no way to tell a real topic from a reflex reaction. Traced
directly: `extract_recall_subject('hmmm.. not really what I expected. It
should be a random note from the "thoughts" folder.')` → `('hmmm', False)`.
Once "hmmm" was treated as a named subject, `resolve_turn_context`
(`vault.py`) skipped the random-sample branch (a named subject means "search
for that," not "give me anything") and searched the whole vault for the word
"hmmm" instead — landing on an unrelated 2023 Daily note that happened to
contain it, mislabeled `matched 'hmmm' in `thoughts/`` even though it isn't
in that folder. Fix: when a low-confidence subject guess (no explicit recall
lead-in, e.g. "pull up notes on X") comes from a sentence that isn't the one
actually containing the random-request phrase ("a random note", "pick one
of...", etc.), clear it — checked by sentence co-occurrence with the
already-matched random-request pattern, not an enumerable filler-word list,
so it generalizes to any interjection ("well", "so", "uh", ...) the same
way. A genuinely named subject with its own explicit lead-in is untouched.

**Bug B — folder scoping silently did nothing for a full-access persona.**
Samantha's `vault_folders: ['*']` means her `allowed_dirs` is just the vault
root — "Thoughts" never appears in that list by name, only as a subfolder
under it. `search_structured`'s target-folder filter
(`vault_search.py`) matched only against `allowed_dirs`' own basenames, and
when that matched nothing, `search_dirs = search_dirs or allowed_dirs`
silently widened the search to the *entire vault* instead of reporting a
scope miss. Confirmed directly:
`VaultManager.search_structured(profile, "hmmm", target_folder="thoughts")`
returned a hit from `Daily/2023/05-May/2023-05-17.md` — nowhere near
Thoughts. Fix: resolve `target_folder` the same way folder discovery
elsewhere in the module already does (an allowed dir's own name, or an
immediate child of one) and return no results when it can't be resolved,
rather than falling back to an unscoped search.

**Bug C — even handed the real note, the model invented a different one
anyway.** With both retrieval bugs fixed, `resolve_turn_context` now
correctly returns a genuine random note from `Thoughts/`. Fed that exact
system prompt + real note straight to `ollama/gemma4:e4b` twice: both times
it fabricated a plausible-sounding but nonexistent note (`Thoughts/hmmm.md`
with the note's own filler line echoed back as "content"; separately,
`Thoughts/On the Nature of Entropy and Joy.md`, a full invented essay) — the
`vault_recall` skill's explicit "every statement is a verbatim quote" rule
notwithstanding. Damiro asked directly: can this be forced to *always* be
grounded in truth, not just given the material and hoped? The existing
strict-mode fabrication catch (`_VAULT_CLAIM_RE`) only ever ran when *no*
vault content was given at all (`_is_full_body_vault_ctx` == False) — a real
note being present was treated as sufficient on its own, which this
disproved live.

Fix (`engine.py`): a new, purely structural check —
`_vault_ctx_citation_mismatch` — extracts any vault-note-shaped path the
model's reply names and any such path actually present in the `vault_ctx`
it was handed; if the reply names one and it matches none of the real ones,
that's fabrication, checkable without a second model call (comparing
prose *meaning* against the note, rather than a cited *path*, would need
one, and stays a known residual gap rather than something silently claimed
as solved). `chat_stream` now holds the stream for this case too (as it
already did for the no-context strict path) and, on a mismatch, discards
the invented reply and shows the real note directly — no extra round trip,
consistent with the round-trip-frugality mandate. Re-verified against the
live pipeline end to end, `chat_stream("samantha", <the real message>)`
against the real model, twice: one run fabricated again and got corrected
to the real "I on Thoughts About Gods.md" / "Online Resources.md" notes;
another run the model quoted the real note correctly and passed through
untouched — no false positive.

## 4. Skill coverage pass

Samantha carries 9 skills. All got at least one live pass this session:
`vault_write` and `vault_recall`/`subagent_spawn` extensively (§3.3–3.6
above all surfaced there); `sympose_mastery` and `web_search` via direct
live tests (§3.7, and a clean web-search exchange that correctly declined
to guess a version number absent from its own search results). The three
remaining — `system_architecture`, `strategic_analysis`,
`discussion_moderation` — are pure prompt guidance with no action-tag
mechanism to break, so they got a document review instead of a code test.
`discussion_moderation`'s "tag other personas" language is shared with
`slack_interaction`, where an `@mention` is backed by a real second bot
process (each persona has its own Slack token) — a plausible risk that the
same language, read in the CLI where nothing else is listening, could
prompt a persona to fabricate the other persona's reply itself. Tested live
(asked Samantha to "discuss this with Grace"): she gave her own grounded
opinion, then handed off with a genuine, specific question and stopped —
no fabrication. No code change needed there. `slack_interaction` itself
wasn't tested live, since doing so would post into the real Slack
workspace rather than a sandbox.

## 5. Noted, not investigated

While checking for unrelated dirty state before a git operation, found
`~/Development/garden` (the real Obsidian vault, its own git repo) sitting
on 87 modified files plus new untracked ones, all matching the same
cosmetic pattern (bare `Purpose` → `### Purpose`, `a)` → `**a)**`) across
files dating back to 2020, with its last commit 11 days old. Checked
Sympose's own code for anything that bulk-rewrites vault markdown —
nothing does. Most likely an Obsidian plugin (e.g. a linter/auto-formatter)
reformatting notes on open, unrelated to Sympose or this session. Flagged
to damiro; left untouched.

## 6. Commits

- `0e59da3` — fix(grounding): stop a denied premise from becoming settled
  fact in memory.
- `304c8d8` — fix(memory): withhold unresolved claims from the compactor
  LLM entirely.
- `0cd5567` — fix(engine,vault): stop raw action tags leaking to the
  terminal; fix duplicated date in note frontmatter.
- `b5b272a` — fix(vault,actions): enforce the Daily/ write boundary; stop
  confirming failed writes as success.
- `1aa0cb4` — test: lock in tonight's fixes as permanent regression
  coverage.
- `7098e2d` — fix(engine): catch a vault-grounding claim that ends a
  sentence.
- `0d0e596` — fix(actions): stop CONFIG_SET and DELETE_PERSONA crashing
  with UnboundLocalError.
- `4c864ff` — fix(engine): unify local-backend detection in
  `_build_kwargs`.
- `381ae18` — fix(config,vault): stop config_manager singleton from drifting
  off the resolved workspace path.
