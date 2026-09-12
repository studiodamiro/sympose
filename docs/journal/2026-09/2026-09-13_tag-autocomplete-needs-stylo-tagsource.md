---
entry: 2026-09-13
created: 2026-09-13 00:00
type: journal
project: sympose
tags:
  - journal/engineering
  - sympose/ui
  - editor
  - upstream-request
---

# Sympose Engineering Log: `#tag` Autocomplete — Blocked on a New Stylo Capability

> **Date:** Sunday, September 13, 2026
> **Topic:** damiro asked for `#tag` autocomplete matching `[[wikilink]]`
> autocomplete exactly (same trigger-while-typing UX, same themed popup).
> Traced why it can't be built from sympose alone and what stylo would need
> to add.
> **Participants:** damiro (Lead Architect), Grace (Engineering Partner)
> **Status:** Not implemented. Documented as an upstream request per
> standing rule (sympose treats `@damiro/stylo` as a fixed external
> dependency — no edits to its source from a sympose session). No sympose
> code changed.

---

## 1. The ask

Match `[[wikilink` autocomplete's UX for `#tag`: detect a `#` as the user
types it, pop the same themed completion dropdown, insert the chosen tag.

## 2. Why it can't be built from `ui/`

`[[wikilink]]` autocomplete exists because stylo exposes `wikiLinkSource`
(added 0.7.0, see
[2026-09-11 — Stylo 0.9 Upgrade & Wikilink Autocomplete](./2026-09-11_stylo-0.9-upgrade-and-wikilink-autocomplete.md)):
a prop stylo calls with the query typed after `[[`, while its own internal
CodeMirror extension owns the `[[` trigger detection, the unclosed-bracket
scope check, and the `@codemirror/autocomplete` registration
(`source: "wikiLinkSource"`). Sympose only supplies the candidate list
(`ui/src/lib/vault-wikilink-completions.ts`) and forwards the prop through
`markdown-panel.tsx`.

Checked stylo's public surface (`node_modules/@damiro/stylo/dist/types.d.ts`)
for an equivalent: there is none. The only completion-related exports are
`WikiLinkCompletion` / `WikiLinkSource`, and `embedSource` for `![[ref]]`.
No `tagSource`, no generic trigger-character hook, no `extensions` escape
hatch for a host to register its own CodeMirror completion source against
the shipped editor state. The `#` trigger and its completion source would
have to live inside stylo's own editor factory, the same place `[[`'s does
— not something reachable from a prop stylo doesn't expose.

## 3. What stylo would need

Mirroring `WikiLinkSource`'s exact shape and contract:

- A `TagCompletion` type (likely just `{ tag: string }`, or `{ tag, label? }`
  if a display-vs-written split turns out useful — `WikiLinkCompletion`'s
  `label` exists for `[[target|label]]`; tags have no equivalent alias
  syntax today, so probably just `{ tag: string }`).
- `tagSource?: (query: string) => readonly TagCompletion[] | Promise<...>`,
  called with the text typed after `#` while the caret sits in an unclosed
  `#…` word — same "read once, at mount" contract as `wikiLinkSource` /
  `embedSource`.
- Registered as another `@codemirror/autocomplete` source alongside the
  existing wikilink one, so it inherits the same tooltip
  (`.cm-tooltip-autocomplete`) automatically.
- Scope questions stylo's side would need to settle: is `#` only a trigger
  in prose (inert inside a fenced code block / inline code / URL, same as
  `[[`'s documented scope)? Does a `#` immediately followed by a digit or
  mid-word (e.g. a Markdown heading's `#`, or `word#word`) need to stay
  excluded the way GitHub/Obsidian-style tag syntax usually does?

## 4. Sympose-side work, once `tagSource` exists

Small and mechanical, mirroring the wikilink wiring exactly:

- A `matchTagTargets(tree_or_index, query)` helper alongside
  `vault-wikilink-completions.ts` — needs a tag index (every note's
  frontmatter `tags:` list plus any inline `#tag` occurrences) rather than
  the note-stem set wikilinks use, since tags aren't filenames. No such
  index currently exists in `ui/src` — worth checking whether the backend
  already computes one (e.g. for a tag browser) before building a
  client-side scan.
- `tagSource` prop threaded through `app-shell.tsx` → `markdown-panel.tsx`
  → `<Stylo>`, same ref-plus-stable-callback pattern `wikiLinkSource`
  already uses to survive a vault-tree refetch without an editor remount.
- No new CSS: a same-day pass themed the wikilink popup
  (`ui/src/index.css`, the `[data-slot="markdown-panel"] .cm-tooltip.cm-tooltip-autocomplete`
  rule) generically against `@codemirror/autocomplete`'s own selectors, not
  scoped to wikilinks specifically — so a tag popup gets the same frosted
  `--panel` surface, `--radius-lg`/`--radius-md` geometry, and selected-row
  treatment for free the moment a real completion source exists.

## 5. Follow-up

Tracked here as an open ask for whoever next works in the `stylo` repo
(`~/Development/stylo`) — not actioned from this session per the
sympose/stylo boundary. Once `tagSource` ships and stylo is bumped in
`ui/package.json`, §4 above is the whole sympose-side task.
