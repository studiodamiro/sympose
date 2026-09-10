---
title: "ADR-087 — Notification & Confirmation Preferences"
created: 2026-09-11
type: adr
parent: index
tags:
  - sympose/architecture
  - engineering/adr
  - dashboard
---

# ADR-087 — Notification & Confirmation Preferences

- **Status:** Accepted — implemented 2026-09-11.
- **Date:** 2026-09-11
- **Deciders:** damiro (Lead Architect); Grace / Claude (Sonnet 5) (Engineering Partner)
- Makes the dashboard's toast feedback and its delete confirmation
  user-configurable, and revisits the "modal, not toast" call baked into
  `ConfirmDialog` since ADR-085.

## Context

Two fixed behaviours in the dashboard had no knob:

- **Feedback toasts.** Every save, rename, create, restore and error fires a
  `sonner` toast from a `<Toaster>` pinned bottom-right. No way to move it, no
  way to silence it.
- **Delete confirmation.** ADR-084's follow-up routed every destructive action
  through `<ConfirmDialog>`, a centred modal. Its own header note records *why*
  it is a modal — an earlier `sonner`-toast confirm had a single action button
  "a misclick away from deleting". A modal is a hard stop, but it is also the
  only option, and for the common, recoverable case (move-to-Bin, ADR-085) it
  is heavier than the action needs.

## Decision

### `useNotificationPreferences` — three cookie-backed knobs

A hook shaped like `useEditorPreferences` (cookie-backed per the UI preference
convention, **not** a `config_schema.py` runtime knob — these are per-browser
dashboard behaviour, ADR-077 §scope), but built on a **module-level store read
through `useSyncExternalStore`**, so the imperative `notify()` / `confirm()`
helpers can read the current prefs with no React context and every hook caller
stays in sync.

| Knob | Values | Effect |
| ---- | ------ | ------ |
| `enabled` | `on` / `off` | `off` drops every feedback toast — "don't alert me anymore". |
| `confirm` | `dialog` / `inline` / `none` | How a **recoverable** delete asks first. |
| `position` | the six `sonner` corners / edges | Where feedback toasts *and* the inline confirm appear. |

### `notify` — gated feedback

`lib/notify.ts` mirrors the `toast` surface we use (`success` / `error` /
`info` / `warning` / `message`) and no-ops when `enabled === "off"`. The ~11
`toast.*` feedback call sites across five files switch to `notify.*`. The
confirmation path is never gated here — it needs a response.

### `confirm()` — one call, three forms

`lib/confirm.tsx` exposes `confirm({ message, description?, confirmLabel?,
tone?, permanent?, onConfirm })`:

- **`dialog`** — the existing `<ConfirmDialog>` modal, now fed by a `<ConfirmHost>`
  mounted once in `App` (an imperative request pushed to a small store; the host
  renders whatever is pending).
- **`inline`** — a persistent, colour-coded one-liner rendered through
  `toast.custom(…, { duration: Infinity, position })`:
  `⚠  Move "Note" to the bin?   Cancel  [ Move to bin ]`.
- **`none`** — runs `onConfirm` straight away. The file still moves to the Bin,
  so it stays recoverable — that is the whole basis for allowing "no prompt".

**`permanent: true`** (Delete forever, Empty bin) ignores the preference and
always uses the modal. Those are the only genuinely irreversible actions; they
keep the hard stop unconditionally.

The four `<ConfirmDialog>` call sites (editor toolbar delete, vault-row delete,
Bin purge-one, Bin empty-all) drop their `open` / `pending*` state and call
`confirm()` instead — a net simplification.

### Settings

A `NotificationsSection` in Settings, next to the editor one: two
`SegmentedControl`s (`enabled`, `confirm`) and a `Select` for `position`.

## Consequences

- The dashboard can be made silent, or its feedback relocated, from Settings.
- "None" confirmation trades the prompt for speed on the recoverable path; the
  Bin is the safety net, and permanent deletes are unaffected.
- The inline confirm is a softer stop than the modal — it can be ignored, and a
  second one stacks below the first. Acceptable given the two explicit buttons
  (not a one-tap "undo"-style action, unlike the pre-ADR-085 version) and the
  recoverable target.
- `confirm()` / `notify()` are imperative module functions backed by a store,
  not hooks — a small departure from the "prefs are hooks" pattern, justified by
  the ~15 call sites staying one-liners and by `toast` itself already being a
  global imperative API.
- `<Toaster>` stays mounted even when `enabled` is `off`, because the inline
  confirm renders through it.

## Alternatives rejected

- **A `useNotify()` / `useConfirm()` hook threaded to every call site.** More
  idiomatic React, but every one of ~15 sites would take a hook and prop-drill
  or context. The module store + plain functions keep the sites unchanged in
  shape and mirror how `sonner`'s own `toast` works.
- **Keep `ConfirmDialog` modal-only, add just the toast position knob.** Ignores
  the ask ("put a knob on the alert popup for delete… one liner… color coded")
  and leaves the common recoverable delete behind a full modal.
- **Let "None" skip the permanent deletes too.** The user was explicit: skip the
  prompt, but the file must stay recoverable via the Bin. Purge / empty have no
  Bin behind them, so they stay confirmed.
- **A 3×2 visual position grid in Settings.** Considered; a plain `Select` with
  the six named positions is less code and the choice is made once.
- **`localStorage` for the prefs.** The repo's standing choice is cookies for UI
  preferences (`lib/cookies`, UI_DESIGN_REFERENCE.md §5); followed here.

## B.4 index updates

`docs/PROJECT_JOURNAL.md` and `docs/wiki/index.md` ADR tables updated in the
same change.
