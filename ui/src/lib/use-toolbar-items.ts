import * as React from "react"
import type { ToolbarItem } from "@damiro/stylo"

import { getCookie, setCookie } from "@/lib/cookies"
import { isOneOf } from "@/lib/utils"

const COOKIE = "sympose:editor.toolbar_items"

// Mirrors stylo's `ToolbarCommandId` union (its own dist/types.d.ts) — that's
// a type only, with nothing exported at runtime to validate a decoded cookie
// element against, so the built-in id set is duplicated here. A
// `ToolbarCustomItem` object is never a realistic cookie value: its `run`
// callback can't survive a JSON.stringify/parse round trip, so validation
// only needs to cover plain command-id strings and the `"|"` separator.
const TOOLBAR_COMMAND_IDS = [
  "undo", "redo", "save", "search", "h1", "h2", "h3", "body", "bold",
  "italic", "strike", "underline", "code", "codeBlock", "link", "wikilink",
  "quote", "bulletList", "orderedList", "task", "hr", "frontmatter", "table",
  "math", "mathBlock",
] as const

function isValidToolbarItem(item: unknown): item is ToolbarItem {
  return item === "|" || (typeof item === "string" && isOneOf(item, TOOLBAR_COMMAND_IDS))
}

/** Sympose's own curated starting set — stylo's default minus `undo`/`redo`/
 *  `link`/`wikilink`/`hr`/`frontmatter`/`table`/`math`, plus `underline`
 *  (opt-in upstream) and `save` (disabled without `onSave`). Seeds the cookie
 *  on first run; `<StyloToolbarSettings>`'s own "Reset to default" button
 *  resets to stylo's upstream default instead, a known upstream quirk. */
const DEFAULT_TOOLBAR_ITEMS: ToolbarItem[] = [
  "h1",
  "h2",
  "|",
  "bold",
  "italic",
  "underline",
  "strike",
  "|",
  "bulletList",
  "orderedList",
  "|",
  "codeBlock",
  "quote",
  "|",
  "save",
]

function parse(raw: string | null): ToolbarItem[] | null {
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    const valid = parsed.filter(isValidToolbarItem)
    return valid.length > 0 ? valid : null
  } catch {
    return null
  }
}

/**
 * The markdown editor toolbar's button set (Settings > Markdown editor,
 * `<StyloToolbarSettings>`) — cookie-backed per the UI preference convention,
 * kept out of `useEditorPreferences` because its value is a JSON-encoded
 * array rather than a single enum string.
 */
export function useToolbarItems(): readonly [
  ToolbarItem[],
  (next: ToolbarItem[]) => void,
] {
  const [items, setItems] = React.useState<ToolbarItem[]>(
    () => parse(getCookie(COOKIE)) ?? DEFAULT_TOOLBAR_ITEMS
  )

  const set = React.useCallback((next: ToolbarItem[]) => {
    setCookie(COOKIE, JSON.stringify(next))
    setItems(next)
  }, [])

  return [items, set] as const
}
