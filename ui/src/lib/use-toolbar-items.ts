import * as React from "react"
import type { ToolbarItem } from "@damiro/stylo"

import { getCookie, setCookie } from "@/lib/cookies"

const COOKIE = "sympose:editor.toolbar_items"

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
    return Array.isArray(parsed) ? (parsed as ToolbarItem[]) : null
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
