# Contributing to Sympose

Sympose is a zero-bloat, sub-second multi-model AI agent hub and sovereign
Obsidian vault explorer. It pairs fast cloud models (Google Gemini, Anthropic
Claude) with local private models (Ollama) under one CLI, a sandboxed vault, an
autonomous memory layer, a Slack Socket Mode daemon, and a FastAPI-served web
dashboard. Every change is weighed against the latency, dependency, and
maintenance cost it imposes on that system.

---

## Engineering principles

- **Simplicity first.** Prefer the most direct solution with the fewest moving
  parts. Resist premature abstraction. If something fails or stalls, find the
  root cause rather than working around it.
- **One responsibility per module.** Keep source files in `sympose/` focused and
  small — a **hard ceiling of 200 lines of code**. Split a module when it grows
  past that. `app.py` stays a thin entry point (target < 50 lines): flag
  parsing and dispatch, no logic.
- **Zero-bloat dependencies.** Do not add a dependency, library, or build tool
  unless it is genuinely necessary. Prefer the Python standard library. Any
  addition must be justified in an ADR with an **Alternatives rejected** section
  weighing it against at least one lighter option. Precedent: external search
  APIs (Brave, Google) were rejected in favour of the zero-key `ddgs`
  (DuckDuckGo) standard, and no database / vector store is used — flat Markdown
  over stdlib.

## Architecture invariants

- **The Triad Pattern.** Every agent is three files: identity metadata in YAML
  (`profiles/<handle>.yaml`), cognitive directives in Soul
  (`profiles/<handle>_soul.md`), and dynamic facts in Memory
  (`profiles/<handle>_memory.md`). Nothing that belongs in one layer leaks into
  another.
- **Flat-file agnostic engine.** Markdown documents on disk are the sovereign
  single source of truth. Models are transient cognitive processors reading the
  file data bus. No hardcoded vault paths in `sympose/` — all paths resolve from
  `.env` (`MASTER_VAULT_PATH`) and `config.yaml`. Sympose adapts to any folder
  taxonomy (Flat, PARA, Johnny Decimal, Zettelkasten).
- **Sub-1.0s TTFT SLA.** Time-to-first-token stays under one second (target
  < 0.8s). No blocking network calls on the hot path; background LLM work runs on
  detached daemon threads and honours `performance.request_timeout`.
- **Directory-boundary path safety.** All sandbox checks use
  `os.path.commonpath([target, base]) == base` or `Path.is_relative_to()` —
  never a bare `str.startswith()`, which allows sibling-directory escapes.
  Sub-agent workers inherit the parent agent's `allowed_dirs`; no privilege
  escalation.
- **Session isolation & clean lifecycles.** Multi-client integrations
  (Slack Socket Mode, web) key history by explicit `session_id`. Spawned
  subprocesses (MCP servers) register `atexit` cleanup. Async memory writes take
  a process-wide file mutex and reconcile against foreground writes.

## Making changes

- Touch only the lines and files necessary for the change at hand.
- Discuss scope before large or architectural changes — open an issue or a draft
  ADR first.
- Verify before opening a PR: `.venv/bin/pytest` must pass, and any UI change
  must pass `cd ui && npm run typecheck` and `cd ui && npm run build`.

---

## Documentation standards

Whenever an architectural subsystem, memory pattern, latency optimization, or
core feature is introduced or modified, document it synchronously across two
layers. This section is the binding standard.

### Wiki (`docs/wiki/`)

Concept-based, publication-ready documentation (Quartz / Docusaurus / Obsidian
Publish). Subfolders: `architecture/`, `memory/`, `agents/`, `guides/`,
`reference/`, with `docs/wiki/index.md` as the navigation map. Include the
systems rationale — why a decision was made, benchmarks, gotchas — and Mermaid
diagrams for data flow. The wiki is present-tense: it always describes how the
system works now.

### Engineering journal & ADRs (`docs/journal/YYYY-MM/`)

Chronological log of milestones and formal Architectural Decision Records.

- Monthly date folders: `docs/journal/YYYY-MM/`.
- Filename format `YYYY-MM-DD_topic_slug.md`; ADRs use
  `YYYY-MM-DD_adr-NNN-topic-slug.md` (zero-padded `NNN`).
- A journal entry is the chronological narrative of a session. Each formal
  decision it reaches is extracted into its own `*_adr-NNN-*.md` file; the entry
  keeps a short summary and a link.
- The master ADR index lives in `docs/PROJECT_JOURNAL.md`, newest first.

**ADR content standard.** Every ADR carries, in order: **Status**, **Date**,
**Deciders**, **Context**, **Decision**, **Consequences** (both positive and
negative / costs), and **Alternatives rejected**. The rejected-alternatives
section is mandatory — name each option that was genuinely on the table and why
it lost. An ADR without it is a proposal, not a decision record. Where the
original record captured none, the section reads exactly
`> Not captured in the original decision record.` — never invent options.

**Scope discipline.** When an ADR covers a feature set, split it into _"Accepted
for the first release"_ and _"Deferred (post-v1, additive)"_. Deferred items must
not gate the first release. If a decision is time-boxed for re-evaluation,
record the revisit trigger explicitly.

**Amendment & supersession.** An ADR is immutable once its decisions have been
implemented; a later change of course is a **new** ADR. A new ADR that changes an
earlier one says so in its **Status** line
(`Accepted — amends ADR-NNN …` / `… supersedes ADR-NNN`), and the earlier ADR
gets a pointer forward: a note in its **Status** line and an inline blockquote at
the specific decision that moved. Never silently edit the earlier ADR's body.

**Index & cross-reference sync.** Adding or amending an ADR is not complete
until, in the same change: the `docs/PROJECT_JOURNAL.md` ADR table is updated;
the `docs/wiki/index.md` ADR table is updated (the two tables stay identical in
their ADR / Title / Status / Date columns); and every wiki page whose content
derives from the decision links to the ADR and reflects its current state.

### Obsidian YAML frontmatter

Every file under `docs/` begins with valid Obsidian YAML frontmatter. Root meta
files (`README.md`, `CONTRIBUTING.md`, `LICENSE`) are exempt.

```yaml
---
title: "Article Title"
created: YYYY-MM-DD
type: wiki-architecture # wiki-architecture | wiki-memory | wiki-agents | wiki-guides | wiki-reference | wiki-index | journal | adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
---
```

Use a controlled tag vocabulary; do not invent per-file variants:

| Content                                            | Tags                                           |
| ------------------------------------------------- | ---------------------------------------------- |
| Wiki — architecture                               | `sympose/architecture`, `engineering/standard` |
| Wiki — memory / agents / guides / reference / home | `sympose/wiki`, `engineering/standard`         |
| ADR                                              | `sympose/architecture`, `engineering/adr`      |
| Journal milestone                                | `sympose/journal`, `engineering/milestone`     |

### Portfolio-safe contents

The journal, ADRs, and wiki are committed and published. Keep their contents
generic: generic file, directory, and repository references; no credentials,
private URLs, private vault paths, or internal-only context. Write every entry
as if a reviewer will read it.

---

## Repository conventions

- **Commit messages**: imperative subject, prefixed by area
  (`docs:`, `feat:`, `fix:`, `chore:`). Explain the _why_ in the body.
- **Branches**: work on a topic branch off `main`; open a PR.

## Repository hygiene

These are strict, not aspirational.

- **Single author identity.** Every commit is authored and committed by the
  repository owner (`damiro <hello.damiro@gmail.com>`). No secondary identities,
  no aliases.
- **No trailers.** Commits carry no `Co-authored-by`, `Signed-off-by`, or
  tooling/attribution trailers of any kind.
- **Assistant and editor tooling is never committed.** `.agents/`, `.claude/`,
  `.cursor/`, `CLAUDE.md`, `.vscode/`, and the like are local-only. They are
  covered machine-wide by `core.excludesFile` (`~/.gitignore_global`, templated
  in the `dot-files` repo) and, belt-and-braces, by this repo's `.gitignore`.
  A new repository copies the same `.gitignore` block:

  ```gitignore
  # AI assistant & editor tooling — never committed
  .agents/
  .claude/
  .cursor/
  CLAUDE.md
  ```

- Referring to models (Gemini, Claude, Ollama) in code, docs, or configuration
  is fine — Sympose is a multi-model hub. The rule is about authorship and
  tooling artifacts, not the product's subject matter.

## Commands

| Task                     | Command                     |
| ------------------------ | --------------------------- |
| Run unit tests           | `.venv/bin/pytest`          |
| Run the Sympose CLI      | `python3 app.py`            |
| Web dashboard dev server | `cd ui && npm run dev`      |
| Web dashboard typecheck  | `cd ui && npm run typecheck` |
| Web dashboard build      | `cd ui && npm run build`    |
