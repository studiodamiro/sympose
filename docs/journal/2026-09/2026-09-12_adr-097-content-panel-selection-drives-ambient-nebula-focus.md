---
title: "ADR-097 — Content-Panel Note Selection Drives the Ambient Nebula Focus (amends ADR-088)"
created: 2026-09-12
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
  - nebula
---

# ADR-097 — Content-Panel Note Selection Drives the Ambient Nebula Focus (amends ADR-088)

- **Status:** Accepted — implemented 2026-09-12.
- **Date:** 2026-09-12
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)

## Context

Clicking a node directly on the Knowledge Nebula in Explore mode already flies
the camera to it and narrows the highlight to its 1-hop neighbours —
`handleNodeClick` in `knowledge-nebula-2d.tsx` frames the cluster, and
`AmbientNebula`'s `selectedNodeId` feeds `useNebulaFilter` to fade every node
outside that cluster (ADR-088). That reaction only ever fired from a click on
the nebula canvas itself. Opening a note anywhere else in the app — the vault
tree, a `[[wikilink]]` followed inside the editor, a fresh note just created —
left the ambient nebula sitting on whatever it last showed, even though the
app already tracks exactly one "note currently open" value
(`AppShell`'s `selectedNote`) that every one of those actions already writes
to.

damiro asked for the two to connect: whichever note is open in the content
panel should drive the same fly-to-and-highlight reaction, "much like when
you click a note in explore mode" — and explicitly wanted it live even while
the nebula sits dimmed in Focus mode behind the panels, not gated behind
switching into Explore first.

## Decision

Thread the existing selection through rather than building a second
mechanism:

- `AppShell` derives `activeNoteId` from `selectedNote` — the bare filename
  stem (`selectedNote.split("/").pop().replace(/\.[^./]+$/, "")`), matching
  the id space `GET /api/vault/graph` already publishes (`VaultManager.
  get_vault_graph`'s `id` is `vault_manifest_build._stem()`, a basename
  without extension) — and passes it to `<AmbientNebula activeNoteId>`.
- `AmbientNebula` gained one `useEffect` keyed on `activeNoteId` that calls
  `setSelectedNodeId(activeNoteId)` (the same state Explore-mode clicks
  already set, already wired into `useNebulaFilter`) and
  `nebulaRef.current?.focusNode(activeNoteId)` (the existing imperative
  fly-to-cluster method on `KnowledgeNebulaHandle`, already used for the
  Explore-click case). No new highlight logic, no new camera-framing math —
  the effect just calls the two primitives ADR-088/096 already built, from a
  second trigger.
- The effect is unconditional — not gated on `prefs.interaction === "explore"`
  — so the dimmed Focus-mode nebula behind the panels re-centers and
  re-highlights live as you browse notes, and Explore mode (when you switch
  into it) opens already focused on whatever you were last reading.

Because `selectedNote` already updates from the vault tree (`onSelect`),
wikilink navigation (`openWikilink`), and note creation, this one wiring
point covers all three without touching any of them.

## Consequences

- The ambient nebula now reads as a live reflection of what you're doing in
  the vault, not just a decorative backdrop that only reacts to being
  clicked on directly.
- `AmbientNebula`'s `selectedNodeId` now has two writers — Explore-mode
  clicks on the canvas, and `activeNoteId` from the content panel — with no
  reconciliation between them beyond "last write wins." Clicking a node
  directly in the nebula does not, in turn, update `selectedNote` /
  `AppShell`'s content panel; that asymmetry pre-dates this change and stays
  out of scope here.
- If a clicked/opened note's id isn't present in the current graph (e.g. the
  live `/api/vault/graph` fetch hasn't landed yet, or a race with the
  bundled-sample fallback), `focusNode` and `useNebulaFilter` both already
  no-op safely on an unknown id — the effect neither throws nor jumps the
  camera anywhere.

## Alternatives rejected

- **Expose the nebula's ref up to `AppShell` and call `focusNode` from
  there directly**, instead of passing `activeNoteId` down and reacting to
  it inside `AmbientNebula`. Rejected: it would leak `KnowledgeNebulaHandle`
  and the id-derivation knowledge out of the one component that owns the
  nebula's selection state, for no behavioral difference — `AmbientNebula`
  already owns `selectedNodeId`, so it should own reacting to a new note
  becoming active too.
- **A second, separate "ambient focus" state distinct from
  `selectedNodeId`**, so a direct nebula click and a content-panel selection
  couldn't clobber each other. Rejected as unwarranted complexity for
  tonight's ask — damiro asked for one reaction to "a note is clicked,"
  not for the two trigger sources to be independently addressable, and nothing
  in the current UI lets both happen in the same instant in a way a user
  would notice fighting.
- **Gate the reaction behind Explore mode**, only applying it once the user
  switches the nebula to interactive. Rejected per damiro's explicit answer —
  the point is the *background* animating while you read, not a change to
  what Explore mode shows when you get there.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
