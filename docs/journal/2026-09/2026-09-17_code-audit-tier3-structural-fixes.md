---
entry: 2026-09-17
created: 2026-09-17 21:30
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/vault
  - reliability
  - security
  - code-review
---

# Sympose Engineering Log: Code-Audit Tier 3 — Structural Fixes, and Where the Report Undersold the Work

> **Date:** Thursday, September 17, 2026
> **Topic:** Closing Tier 3 of the fact-checked 34-finding code audit (see
> the [Tier 1](./2026-09-17_code-audit-tier1-quick-fixes.md) and
> [Tier 2](./2026-09-17_code-audit-tier2-moderate-fixes.md) entries for the
> verification methodology and earlier fixes) — the 5 "structural" findings,
> plus E7/E8 (deferred from Tier 2 pending this tier's D6).
> **Status:** All 7 fixed and regression-tested. Two of them (D2, D3) turned
> out to need real design work, not the "small, mechanical" fix the report
> described — documented below so the gap between estimate and reality is on
> the record.

## 1. D6 first — the mtime-only staleness watermark

Every freshness check in the vault caching layer (`vault_paths.dirs_mtime`,
`vault_manifest`'s watermark, `vault_index`'s FTS rebuild trigger) compared
only *directory* mtimes. A directory's mtime moves when an entry is
added, removed, or renamed inside it — never when an existing file's
*content* changes. So editing a note in place, at any depth, was invisible
to every one of these caches, indefinitely, until some unrelated
structural change happened to touch a watched directory.

Fixed by rewriting `vault_paths.dirs_mtime` into the one shared watermark
helper: a full recursive walk (still stat-only — no file reads, the same
trade-off `vault_manifest_build._stat_tree` already makes and documents as
"cheap even at tens of thousands of files") that folds in every tracked
file's own mtime alongside every directory's. `vault_manifest.py`'s
`_top_level_watermark` and `vault_index.py`'s inline watermark logic now
both delegate to this one function instead of keeping their own separate,
shallower implementations. Also threaded `ignore_folders` through (missing
entirely from `vault_index`'s version before), so touching something in
`.trash`/`Attachments` doesn't force a rebuild.

5 new tests in `test_vault_paths.py`, including one that isolates the exact
bug: bump a file's own mtime via `os.utime` and assert the containing
directory's mtime is provably unchanged, then confirm the watermark still
moves.

## 2. D1 — atomic note writes

`write_note`/`overwrite_note`/`create_note` wrote via a direct
`open(path, "w")`, truncating the real file before any content lands — a
crash mid-write loses the note. Extracted `vault_manifest.write_atomic_text`
(tmp file + `os.replace`, the exact pattern the module's own JSON writer
already used) and pointed all three writers at it.

One thing worth flagging for whoever reads this later: my first pass had
`write_atomic_text` silently swallow and log a failure, matching
`_write_atomic`'s existing best-effort contract for manifest writes — which
would have made every one of these three writers report "Saved" even when
the write actually failed. Manifest writes are meant to degrade silently;
note *content* writes are not, so `write_atomic_text` raises on failure and
`_write_atomic` (the manifest's own caller) wraps it in its own
try/except to keep its original swallow-and-log behavior. Caught this by
tracing the exception path before shipping it, not after a test failure —
the 5 new `test_vault_write.py` tests (mocking `os.replace` to fail, then
asserting the pre-existing note is untouched byte-for-byte and the caller
gets an "Error: ..." string back) would have caught it either way.

## 3. E7 + E8 (deferred from Tier 2, now unblocked by D6)

`read_note`'s fuzzy/title fallback now routes through the same
`_get_vault_snapshot` cache `get_folder_digest`/`search_structured` already
share, instead of its own separate `os.walk` + re-read. `_list_real_folders`
got the same mtime-gated cache its siblings already had — it was the one
uncached directory walk left, redone in full on every dashboard tree
request. Both were safe to route through the shared cache only *because*
D6 fixed that cache's staleness blind spot first; doing this before D6
would have just scaled up the same bug to more read paths.

## 4. D3 — the backlink index's cross-folder rename bug

This is where the report's estimate and the actual fix diverged. The
finding: renaming `ProjectA/Foo.md` could retarget a `[[Foo]]` link that
actually meant a *different* `ProjectB/Foo.md`, because the index only
tracks bare stems.

The complication the report didn't surface: `vault_links.py`'s backlink
index already stores each occurrence's *full* wikilink text (`target`)
alongside its `target_stem` — the ambiguity isn't in what's stored, it's
that `rewrite_wikilink_targets` (the function that actually performs the
retarget) decided whether to rewrite an occurrence purely by matching the
bare filename, with no folder context at all — not even for a link that
was *already* folder-qualified in its own text (`[[ProjectB/Foo]]` would
have been rewritten too, on nothing but the fact that its last segment
said "Foo").

The fix has two parts:
- A folder-qualified link in the source text is now only rewritten when
  its own qualifying segments actually match the renamed note's path -
  independent of any ambiguity elsewhere.
- A bare link is only rewritten when either no other real note shares the
  renamed note's stem, or the occurrence's own file sits in the renamed
  note's top-level folder (Obsidian's own preference for resolving an
  unqualified link) - otherwise it's left alone rather than guessed at,
  via a new `find_notes_by_stem_fn` hook (`VaultManager._find_notes_by_stem`,
  built on the same D6-fixed snapshot cache).

Caught two bugs of my own while building this: `subn`'s match count isn't
the same as the actual-rewrite count (a "leave it alone" branch that
returns the original text unchanged still counts as one "substitution" to
`re.subn`, which would have reported "1 file relinked" on files that were
never actually touched) — switched to a manual counter incremented only on
a real rewrite. And a root-level file's "top folder" computation needs the
same "no segments -> empty string" fallback the renamed note's own path
gets, which the first draft was missing (a root-level referrer would have
compared its own filename, not an empty folder, against the renamed note's
folder). Both caught by hand-tracing the five new
`TestRenameNoteCrossFolderCollision` cases before trusting them, not
after.

## 5. D2 — manifest node identity: the bigger of the two

The finding: `vault_manifest_build._node`'s `id` was the bare filename
stem, so editing/deleting/patching one note could silently drop or
overwrite a *different*, same-named note's node in the manifest, the
dashboard graph, and the "most-linked notes" digest. The report called
this "mechanical... a small diff on its own." It wasn't, for one specific
reason: the manifest's `links` array uses the same ids to record which
note wikilinks to which, and a bare `[[Foo]]` in a note's content is
*inherently* ambiguous when two real notes are both named `Foo` — moving
node identity to full paths meant something now has to decide which of
several real candidates a bare link actually means, not just rename a key.

What shipped:
- `_node`'s `id` is the note's full relative path (D2 itself — this part
  really is a one-line change).
- A new `_resolve_links` + `_pick_link_target` pair, shared by `build()`,
  `_delta_rebuild()`, and `vault_manifest.py`'s `patch_note`/`remove_note`,
  resolves each link's raw wikilink stem against the *current* full node
  set: one real candidate resolves unambiguously; more than one prefers
  whichever shares the linking note's own top-level folder, else the
  alphabetically-first path (deterministic, and a real node — not the
  single-node collision a stem-keyed identity risked); no real candidate
  at all keeps today's ghost-node behavior exactly.
- Each link now carries its raw `target_stem` alongside the resolved
  `target`, specifically so a later incremental update (`_delta_rebuild`,
  `patch_note`) can always re-resolve from the original bare text against
  a *newer* node set, rather than trying to re-derive a stem from an
  already-resolved full path. Without this, adding a second `Foo.md`
  somewhere would never turn an existing, already-resolved link ambiguous
  in a later incremental update — only in the next full rebuild.
- `SCHEMA_VERSION` bumped 1 → 2 (the persisted link shape changed). A
  manifest already on disk under the old schema is never trusted again —
  neither `patch_note`/`remove_note` (both now check and no-op on a
  mismatch, deferring to the next full rebuild) nor, after a second bug I
  found while re-reading my own change, `ensure_fresh`'s own watermark
  short-circuit, which returns a cached/loaded manifest *before* ever
  checking its schema version. A stale v1 manifest whose watermark happens
  to still match current disk state would have been served forever,
  never migrating. Fixed with the same shape `_ignore_changed` already
  uses for the identical problem (a config change the watermark can't
  see) — a new `_schema_stale` check gating both of `ensure_fresh`'s
  watermark short-circuits, with a dedicated regression test that plants a
  fake v1 manifest with a matching watermark and confirms it gets rebuilt,
  not served.
- `format_manifest_digest`'s hub line and `get_vault_graph`'s node
  `label` both already separated *identity* (`id`) from *display* — the
  graph's docstring said "id keeps the full stem for link resolution,"
  already correctly distinguishing it from `label`. Only the digest's hub
  line needed a small fix (it was interpolating raw `id` into the
  `[[...]]` display text, which would now show an ugly full path with
  extension) — switched to each node's own `title` for display, keeping
  `id` for the counting itself.

17 existing tests in `test_vault_manifest.py` encoded the old bare-stem
identity as their expected values and needed updating — a legitimate
consequence of an intentional identity change, not fallout. Added 6 new
ones targeting the actual collision the report described: two same-named
notes both keep separate nodes after a build; patching or removing one
doesn't touch the other's node; a bare link with two real candidates
prefers the same-folder one, falls back deterministically otherwise.

## 6. S1 — the static-asset auth bypass

Confirmed as reported: `app.mount("/", SPAStaticFiles(...))` is a
Starlette `Mount`, which never goes through FastAPI's dependency-injection
tree — the app-level `dependencies=[Depends(require_dashboard_auth)]`
protected every real route but not the mount, so every dashboard asset
except the exact `/` path (JS bundles, and any deep-linked frontend route
falling through to the SPA's `index.html` fallback) was served with zero
credential check.

Fixed with ASGI middleware (`auth.DashboardAuthMiddleware`) instead of a
second FastAPI dependency layered on top — middleware runs ahead of
routing, so it's the one place that can see both the app's own routes and
the mount uniformly. Replaced the app-level `Depends()` outright rather
than keeping both: two overlapping auth mechanisms is a worse security
posture than one, since a future change removing "the" guard could
plausibly leave the *other* one forgotten. The credential-check logic
itself (`_check_credentials`) is now a shared function the FastAPI
dependency and the middleware both call, so there's exactly one
constant-time comparison implementation, not two.

The one real way to get this wrong: middleware order relative to CORS.
`DashboardAuthMiddleware` has to be added *before* `CORSMiddleware`, since
Starlette runs the most-recently-added middleware outermost — a preflight
`OPTIONS` request carries no credentials at all, so if auth ran first,
every cross-origin preflight would 401 and the dashboard's dev server
setup (a different origin than the API) would silently stop working
end-to-end. Verified this empirically against a real `TestClient` call
(not just reasoned through) before treating it as done, and locked it in
as a permanent regression test alongside the actual auth-bypass test
(hitting a path with no matching FastAPI route, so it can only be answered
by the mount, and confirming it 401s without credentials and correctly
falls through to the SPA fallback with them).

## 7. Verification

804 backend tests pass (`.venv/bin/pytest`), up from 778 at the start of
this tier — every new test targets a real, hand-verified failure mode of
the code it accompanies, not just the happy path. No `ui/` changes in this
tier (D1/D2/D3/D6/E7/E8/S1 are all backend), so no typecheck/build/live
browser pass was needed this time.

## 8. What's next

Tier 4 — the report's "needs a rethink" findings (S2, C6) plus C7's own
sequencing note bundling them with the already-shipped C7 fix as one
design problem — still needs the decision flagged in the Tier 1 entry:
patch the three heuristics individually, or do the root-cause redesign
(track real read-tool invocations as an explicit fact instead of
inferring them from command text or reply content). E1 stays deferred
until the chat feature itself is wired up.
