---
entry: 2026-09-17
created: 2026-09-17 16:20
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/vault
  - sympose/ui
  - reliability
  - code-review
---

# Sympose Engineering Log: Code-Audit Tier 1 — 14 Quick Fixes, Fact-Checked Before Touching Anything

> **Date:** Thursday, September 17, 2026
> **Topic:** A 34-finding code-audit report (backend + `ui/`) was fact-checked
> against the actual codebase before any fix landed, then its lowest-risk
> tier — 14 self-contained, no-dependency findings — was closed in one pass.
> **Status:** All 14 fixed and regression-tested; Tiers 2–4 (moderate,
> structural, "needs a rethink") remain open, in the sequence the report lays
> out.

## 1. Verification before trust

The report arrived as an external artifact (not derived from this session),
so before any of its 34 findings turned into a code change, four parallel
review passes independently re-read every cited file:line against the
current tree — not just the report's summary — checking that the described
bug is real, the location is accurate, and any comparison the report made to
"sibling" code ("every sibling write action checks X") actually holds.

Result: the report held up well. Of 34 findings, the large majority were
exactly right. A handful had small inaccuracies — a mis-cited line number
(C7), a wrong count (G2 claimed "10 vs 5" built-in trigger words; the real
split is 18 vs 5), one overstated failure mode (C5 said an unguarded `int()`
"crashes the whole run"; it's actually caught by an outer `try/except`, just
too coarsely), and one PoC command that wouldn't itself reach the bypass it
was demonstrating (S2). None of these invalidated the underlying finding.

## 2. The 14 fixes (Tier 1 — quick, no dependencies)

- **C8** (`mcp_client.py`) — `stop()` now `.wait()`s after `kill()`, closing
  a zombie-process leak on the force-kill path.
- **C9** (`actions.py`) — `REACT` is a declared tag with no execution
  branch, so every use logged a spurious "malformed tag" badge even though
  `slack.py` already handles reactions independently via its own regex on
  raw output. Added an explicit no-op branch with a comment explaining why.
- **C10** (`actions.py`) — `WRITE_CANVAS` badged success unconditionally,
  unlike WRITE_NOTE/APPEND_NOTE/DAILY_NOTE two cases above it. Added the
  same `_op_failed` guard.
- **C3** (`config.py`) — `text-completion-openai` (OpenAI's own cloud
  endpoint) was listed in `_LOCAL_MODEL_PREFIXES`, forcing the wrong
  grounding mode and timeout. Removed.
- **C4** (`sessions.py`) — session auto-titling hardcoded `timeout: 4.0`
  with no schema entry. Added `session.exit_behavior.title_timeout` to
  `config_schema.py` (ADR-077) and regenerated
  `docs/wiki/reference/configuration.md`.
- **C5** (`sub_agents.py`, `native_tools.py`) — unguarded `int()` on
  LLM-supplied `max_results`/`count` args. Wrapped in try/except returning a
  retryable tool-level error, matching the adjacent empty-query checks.
- **D5** (`vault.py`) — note reads used `errors="ignore"`, silently dropping
  non-UTF-8 bytes from content presented as exact ground truth. The report
  cited two sites; all nine occurrences in the file read note content that
  ends up as grounding material (samples, manifest/index bodies,
  chronological picks), so all nine were switched to `errors="replace"` for
  consistency rather than leaving seven of them silently lossy.
- **E6** (`app-shell.tsx`) — the mock chat transcript was rebuilt as a fresh
  element tree every render. The report suggested a bare module-level
  constant, but the transcript embeds one live prop (the WRITE_NOTE badge's
  `editorOpen`/`toggleEditor`, which really opens the editor panel on
  click), so a frozen constant would have broken that interaction. Used
  `useMemo` instead, with `toggleEditor` stabilized via `useCallback` so the
  memoization is actually effective.
- **E3** (`theme-provider.tsx`) — the one preference hook still using
  `localStorage` instead of the app's cookie convention. Routed through
  `lib/cookies.ts`; dropped the cross-tab `storage`-event listener in the
  process since no sibling preference hook syncs across tabs either.
- **E9** (`compactor.py`, `vault_manifest.py`) — two independent
  implementations of "get-or-create a lock per key." Extracted
  `get_or_create_lock()` into `compactor.py` (already the documented home
  for shared background-hygiene primitives); `vault_manifest.py` imports it.
- **E5** (`content-panel.tsx`, `markdown-panel.tsx`) — the "container width ÷
  8" minimum-width rule was duplicated as a bare magic number, kept in sync
  only by a comment. Extracted `eighthWidth()` into `use-resizable.ts`
  (already imported by both).
- **F3/F4/F5** (`use-nebula-preferences.ts`, `use-editor-preferences.ts`,
  `use-toolbar-items.ts`) — enum-kind cookie values were cast with no
  runtime check against their allowed union, and F4's `|| DEFAULTS.x`
  fallback only caught a missing cookie, not a well-formed-but-stale one.
  Added one shared guard, `isOneOf()` in `lib/utils.ts`, applied at all
  three sites: `use-nebula-preferences.ts`'s `SPEC` gained a declared
  `enumValues` per enum knob; `use-editor-preferences.ts` gained a local
  `decodeEnum()` helper; `use-toolbar-items.ts` validates each array element
  against stylo's `ToolbarCommandId` set (duplicated locally since it's a
  type only, nothing exported at runtime — a `ToolbarCustomItem` object
  can't survive a cookie's JSON round-trip anyway, since its required `run`
  callback is dropped by `JSON.stringify`, so string-only validation is
  correct, not incomplete).

## 3. Verification

775 backend tests pass (`.venv/bin/pytest`), including two that failed
transiently right after adding the `title_timeout` schema setting until
`docs/wiki/reference/configuration.md` was regenerated via
`python -m sympose.config_reference` — the doc-drift check doing exactly its
job. `ui/` typecheck (`tsc -b`) is clean and `npm run build` succeeded,
regenerating `sympose/webui/`.

## 4. What's next

Tiers 2–4 of the same report remain, in the sequence it lays out: G1+G2
together (ignore-folders/search-triggers fallback consolidation), F1+F2
together (panel eviction in `use-panels.ts`), then the structural tier in
dependency order (D6 before E7/E8, D2+D3 as one identity migration, S1's
auth-bypass fix), and finally a decision on Tier 4 — patch S2/C6/C7's
textual heuristics individually, or do the root-cause redesign the report
recommends (track real read-tool invocations as an explicit fact instead of
inferring them from command text or reply content).
