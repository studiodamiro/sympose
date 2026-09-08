---
title: "ADR-078 — Materialized Vault Manifest (Structural Map) for the Agent & Dashboard Graph"
created: 2026-09-09
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - vault
---

# ADR-078 — Materialized Vault Manifest (Structural Map) for the Agent & Dashboard Graph

- **Status:** Accepted — manifest engine implemented 2026-09-09
  (`sympose/vault_manifest.py`, config knobs, `VaultManager` write-through +
  accessor, tests). The `GET /api/vault/graph` endpoint and the
  `vault_recall` / `resolve_turn_context` rewrite (ADR-078.7) are the follow-up
  integration pass and are not yet done.
- **Date:** 2026-09-09
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Builds on the retrieval caches in `sympose/vault.py`
  (`_VAULT_SNAPSHOT_CACHE`, `_BACKLINK_CACHE`) and the `sqlite_fts` index of
  [ADR-070 / ADR-070.5](./2026-09-04_adr-070-hot-path-retrieval-budget-trigger-discipline.md).
- Holds to the [ADR-052](../2026-08/2026-08-29_adr-052-in-memory-metadata-caching-scalability.md)
  scalability standard and the concurrency posture of
  [ADR-072](./2026-09-04_adr-072-engine-concurrency-bounded-background-hygiene.md).
- Supplies the `GET /api/vault/graph` contract that
  `ui/src/lib/nebula-graph.ts` currently stubs with `mock-nebula.json`
  ([ADR-051](../2026-08/2026-08-29_adr-051-flat-web-dashboard-knowledge-nebula-theme-engine.md)).
- Implementation log to follow in a companion journal entry on acceptance.

## Context

The agent has no persisted map of the vault. Retrieval walks the filesystem on
demand, backed by two in-memory, mtime-keyed caches: `_get_vault_snapshot()`
(every note — rel path, parsed frontmatter, body) and `build_backlink_index()`
(the inverted `[[wikilink]]` graph). Both are rebuilt wholesale whenever a
watched top-level directory's mtime drifts.

The dashboard's Knowledge Nebula needs the same data — notes as nodes,
wikilinks as edges, top-level folder as the colour group. Its client contract
(`NebulaGraph` in `ui/src/lib/nebula-graph.ts`) is real, but the server side
does not exist; `ui/src/lib/mock-nebula.json` is a hand-built placeholder and
the comment in that file says "swapping to the real source is a one-line
`fetch()`".

damiro wants a single materialized file that is a faithful, near-real-time map
of the vault, usable both by the agent (for navigation / structure awareness)
and by the dashboard (as the graph feed), before the UI integration work
starts. Two forces shape the decision:

1. **It cannot be called the source of truth.** The `.md` files on disk are
   authoritative. Any generated map is a *projection*; if the projection is
   treated as primary, every staleness window becomes a correctness bug rather
   than a stale-cache annoyance.
2. **It has to scale to thousands of notes.** The existing "any top-level
   mtime drift ⇒ re-read and re-parse the entire vault" strategy does not:
   at a few thousand notes, editing one daily note would trigger a
   multi-second full rebuild. That violates the ADR-052 standard.

## Decision

**A derived, incrementally-maintained structural manifest — one JSON file per
vault, off the hot path, feeding both the agent and the graph endpoint.**

- **ADR-078.1 — `sympose/vault_manifest.py` owns the projection.** A new
  focused module (<200 LOC), structured like `vault_index.py`: a pure
  `build(notes, links) -> dict` projection, an mtime-gated
  `ensure_fresh(workspace_dir, mv, snapshot_provider) -> dict`, and a cheap
  `load(workspace_dir, mv) -> dict | None` for cold readers. The `.md` files
  remain authoritative; every rebuild path reads disk, so on any disagreement
  disk wins **by construction**. The manifest is described in code and docs as a
  *map* / *projection*, never as the source of truth.

- **ADR-078.2 — Location and write discipline.** The file lives at
  `<workspace>/.vault_index/<vault-hash>.manifest.json`, beside the ADR-070.5
  sqlite index and, like it, **never inside the user's Obsidian vault** (Obsidian
  sync would propagate it and its own graph view could ingest it). Writes are
  atomic: temp file in the same directory, then `os.replace()`, so a concurrent
  reader never sees a partial document.

- **ADR-078.3 — Schema: structure only, no note bodies.**

  ```
  meta:    { vault_root, generated_at, watermark, note_count, schema_version }
  nodes:   [{ id, rel_path, folder, tags, title, bytes, mtime, exists }]
  links:   [{ source, target }]                 # resolved from [[wikilinks]]
  folders: { "<folder-rel-path>": <note count> }  # one entry per folder, every depth
  ```

  `id` is the vault-relative stem (matching `NebulaNode.id`); `folder` is the
  top-level segment (the nebula colour group); `exists: false` marks a wikilink
  target with no file on disk (a ghost node). `folders` is a flat map — every
  folder at every depth (`Daily`, `Daily/2026`, `Daily/2026/09-September`) to
  its note count — so a consumer can reconstruct the tree without the manifest
  carrying nesting. Bodies are deliberately absent — this is a navigation and
  graph index, not a content store. The `nodes` / `links` shape is a superset of
  the client's `NebulaNode` / `NebulaLink`, so `GET /api/vault/graph` is a
  projection of the manifest, not a reshape.

- **ADR-078.4 — Incremental freshness (the scalability core).** Two tiers:

  1. **Cheap gate.** The existing shallow top-level-dir mtime watermark
     (`_dirs_mtime`). Unchanged ⇒ serve the loaded manifest, no walk.
  2. **Delta rebuild.** On drift, a stat-only recursive `os.scandir` pass
     collects `{rel_path: (mtime, size)}` for the current tree (fast even at
     tens of thousands of files — no file is opened). Diff against the manifest:
     read + YAML-parse only new or changed notes, drop deleted ones, and
     recompute `links` from the union of per-note forward-links (small and
     cheap to hold). Steady-state cost is proportional to the number of
     *changed* files, not to vault size. A cold build with no manifest is a
     one-time full walk — unavoidable and acceptable.

- **ADR-078.5 — Write-through for Sympose's own edits.** `write_note` /
  `append_note` patch the single affected node and its outgoing links in the
  manifest immediately after writing, reusing the `_reindex_note_if_enabled`
  hook point. Edits Sympose makes are reflected with no walk; edits made
  externally (in Obsidian) are picked up by the ADR-078.4 delta rebuild on the
  next read.

- **ADR-078.6 — No watcher, no daemon, no new dependency.** True real-time
  reflection of *external* edits would require a filesystem watcher — a
  background service and most likely a new dependency, both ADR-gated and
  against Sympose's zero-daemon posture — for a benefit no current workflow
  needs. Explicitly out of scope. Revisit only if "edit in Obsidian while
  watching the nebula redraw live" becomes a real use case.

- **ADR-078.7 — Two consumers, one builder.**
  - **Dashboard:** `GET /api/vault/graph` (new, in `sympose/server.py`)
    returns `ensure_fresh(...)` projected to `{ nodes, links }`.
    `ui/src/lib/mock-nebula.json` is retired and the `fetch()` in
    `nebula-graph.ts` points at the endpoint.
  - **Agent:** a cheap structural digest (folder tree with counts, tag
    inventory, orphan / hub notes) built from `load(...)` for *navigation and
    structure awareness only*. Two touch points:
    - **Code** — `VaultManager.resolve_turn_context()` and its helpers
      (`get_discovered_folders`, `find_chronological_notes`,
      `build_backlink_index`) read the manifest instead of walking the tree.
      This is the latency lever and is independent of any skill.
    - **Skill prompt** — the `vault_recall` skill
      (`sympose/builtin_skills/vault_recall/SKILL.md`; the read-side skill,
      paired with `vault_write`) has a "Discovery — don't assume structure"
      section that currently sends the model to `find` / `ls` / pattern
      matching. It is rewritten to consult the manifest first for vault shape,
      folder schema, and the wikilink graph, falling back to filesystem probing
      only when the manifest is disabled or absent.
    In both places the manifest is **not** a grounding source: any note content
    a persona quotes is still read from the actual `.md` per
    [ADR-057](../2026-08/2026-08-29_adr-057-structured-vault-retrieval-context-excerpts.md)
    and the zero-hallucination grounding guarantee. The skill's "Ground rule"
    stays as written — the manifest tells the model *where* to look, never
    *what a note says*. A stale manifest can never put words in a persona's
    mouth.

- **ADR-078.8 — Knobs, declared in the schema (ADR-077).** All in
  `sympose/config_schema.py`; the delta-vs-full rebuild mechanism itself is not
  a knob.
  - `vault.manifest.enabled` (`bool`, default `false`). Default off keeps the
    zero-state install a pure on-demand walk. When off, `GET /api/vault/graph`
    still works by building the projection in memory per request and writing no
    file.
  - `vault.manifest.check_debounce_seconds` (`float`, default `2.0`). Refresh is
    access-triggered, not timed; this caps how often the stat-only `scandir`
    delta pass may run, so a hammered graph endpoint during active editing
    cannot trigger back-to-back stat-walks. `0.0` disables the debounce.
  - `vault.manifest.max_nodes` (`int`) — guard that caps pathological vaults.

- **ADR-078.9 — Concurrency.** One rebuild lock per vault-hash
  (`threading.Lock` keyed by the manifest path) so concurrent personas / Slack
  threads / the API endpoint do not each kick off a redundant delta rebuild,
  matching the locked-shared-state posture of ADR-072. Atomic `os.replace`
  already guarantees reader safety independent of the lock.

## Consequences

- One builder (`_get_vault_snapshot()` + forward-link extraction) feeds both
  agent retrieval and the graph endpoint. The UI stops carrying a mock feed and
  cannot drift into its own ad-hoc shape.
- **Scale profile at ~5 000 notes:** cold build is a full walk (seconds, one
  time). Steady state is the cheap mtime gate (microseconds) and, only when the
  vault actually changed, a `scandir` stat pass (sub-second) plus a parse of the
  handful of changed files. The manifest JSON is roughly 1–3 MB and serializes
  in well under 100 ms. The rebuild runs only on an explicit graph / navigation
  request, never on the message hot path.
- A new persisted artifact per vault in the workspace. It is outside the repo
  (workspace ≠ checkout) and outside the vault, so no `.gitignore` or Obsidian
  exclusion is needed beyond choosing the path.
- The ADR-070.5 `sqlite_fts` index keeps its own all-or-nothing rebuild on
  watermark drift. Unifying it onto the same `scandir` delta diff is a sensible
  follow-up but is **out of scope** here.
- `vault_manifest.py` and any digest formatter stay separate from `vault.py` so
  the retrieval module does not grow past the size guideline.

## Implementation Note (2026-09-09 — engine)

Shipped this pass:

- **`sympose/vault_manifest.py`** (~206 lines) — `manifest_path`, `build` (pure
  projection), `ensure_fresh` (debounce → cheap top-level mtime gate → locked
  rebuild → atomic `os.replace`), `patch_note` (single-node write-through that
  re-stamps the watermark), `load`. Module-level per-path `threading.Lock`,
  in-memory `_mem_cache` / `_last_check`.
- **`sympose/config_schema.py`** — `vault.manifest.enabled` (bool, `False`),
  `vault.manifest.check_debounce_seconds` (float, `2.0`),
  `vault.manifest.max_nodes` (int, `0`). `docs/wiki/reference/configuration.md`
  regenerated; `config.yaml` seeded with the block, off.
- **`sympose/vault.py`** — `VaultManager._update_manifest_if_enabled()` called
  after the FTS reindex hook in `write_note` / `append_note`;
  `VaultManager.get_manifest()` classmethod (whole-vault, no `profile` arg —
  the map is not persona-scoped). Returns `None` when the knob is off.
- **`tests/unit/test_vault_manifest.py`** — 23 tests (projection shape, ghost
  nodes, folder depth counts, freshness gate, debounce, drift rebuild,
  truncation, provider-failure fallback, write-through, `VaultManager`
  integration). Suite 233 → 256, all green.

The delta-read optimisation in ADR-078.4 (re-parse only changed files on an
external edit, rather than re-running the full snapshot provider) is **not**
in this pass: an external edit still triggers a full `_get_vault_snapshot`
rebuild, gated by the cheap mtime check so idle cost stays zero. Sympose's own
writes already avoid the walk via `patch_note`. The incremental external-edit
path is a clean follow-up that changes neither the schema nor the API.

## Alternatives rejected

- **Call the file the source of truth.** Inverts the dependency. The `.md`
  files are authoritative; a projection that claims primacy turns every
  refresh-lag window into a data-integrity bug and invites code that trusts the
  file over disk. Rejected on principle — it is a *map*, and disk always wins.
- **Extend the existing full-rebuild-on-watermark-drift cache to disk as-is.**
  Simplest change, but at thousands of notes a single edit re-reads and
  re-parses the whole vault — multi-second, and squarely against the ADR-052
  sub-5 ms scalability standard. Rejected for the ADR-078.4 delta diff.
- **Filesystem watcher (`watchdog`, or native FSEvents / inotify).** Gives
  genuine real-time reflection of external edits, but adds a runtime dependency
  and a background service — both ADR-gated, both against Sympose's zero-daemon
  design — for a gain no workflow currently needs. Deferred, not adopted.
- **Store the structure as extra tables in the ADR-070.5 sqlite index instead
  of a JSON file.** Lower bloat: it reuses `vault_index.ensure_fresh`'s
  watermark plumbing. But it loses the directly-inspectable, directly-`fetch()`-
  able artifact damiro asked for, and it still needs the delta-diff work to
  scale. Kept on the table as the fallback if the JSON file becomes a
  maintenance burden.
- **No persisted file — build the graph in memory per process and serve it only
  via the endpoint.** Lightest option, but there is no cold-start artifact,
  nothing for external tools or scripts to read, and the agent pays the
  first-walk cost every process. Rejected against the explicit "I want a file"
  requirement (the in-memory path survives only as the `enabled: false`
  behaviour in ADR-078.8).
- **Put the manifest inside the vault** (e.g. `.sympose/manifest.json`).
  Obsidian sync would propagate it across devices, its graph view might ingest
  it, and it would clutter file listings. Rejected — same reasoning that keeps
  the sqlite index in the workspace.
- **Include note bodies so the manifest doubles as a grounding cache.** Bloats
  the file to vault size, duplicates the FTS store, and — decisively — a stale
  body in the manifest could feed a persona fabricated content, violating the
  zero-hallucination grounding guarantee. Bodies stay out; grounding reads
  disk.
