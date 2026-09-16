import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"
import { isOneOf } from "@/lib/utils"

export type EditorSurface = "in-place" | "source"
export type EditorReveal = "caret" | "never"
export type EditorSelectionUI = "menu" | "bar"
export type EditorTableEditing = "source" | "cells"
export type EditorFocusOutline = "on" | "off"
export type EditorAutosave = "on" | "off"
export type EditorHideExtension = "on" | "off"

export interface EditorPreferences {
  surface: EditorSurface
  reveal: EditorReveal
  selectionUI: EditorSelectionUI
  /** How the in-place canvas edits a table (stylo's `TableEditing`).
   *  `"source"` (default) reveals the aligned pipe source under the caret;
   *  `"cells"` edits the rendered table in place. Only meaningful when
   *  `surface` is `"in-place"`. */
  tableEditing: EditorTableEditing
  focusOutline: EditorFocusOutline
  /**
   * Persist body/frontmatter edits to the vault automatically, a beat after
   * typing stops (ADR-081). `"off"` (default) leaves saving to the toolbar
   * button and `⌘/Ctrl-S`.
   */
  autosave: EditorAutosave
  /** Hide the trailing `.md` on note labels in the vault tree and main menu.
   *  `"on"` (default) matches Obsidian's own convention. */
  hideExtension: EditorHideExtension
}

const COOKIES = {
  surface: "sympose:editor.surface",
  reveal: "sympose:editor.reveal",
  selectionUI: "sympose:editor.selection_ui",
  tableEditing: "sympose:editor.table_editing",
  focusOutline: "sympose:editor.focus_outline",
  autosave: "sympose:editor.autosave",
  hideExtension: "sympose:editor.hide_extension",
} as const

const DEFAULTS: EditorPreferences = {
  surface: "in-place",
  reveal: "caret",
  selectionUI: "menu",
  tableEditing: "source",
  focusOutline: "off",
  autosave: "off",
  hideExtension: "on",
}

/** Reads a cookie-backed enum preference, falling back to `fallback` for a
 *  missing cookie *and* for a well-formed-but-invalid one (a renamed enum
 *  value left over from an older build) — unlike a bare `|| fallback`, which
 *  only catches the missing case. */
function decodeEnum<T extends string>(
  raw: string | null,
  allowed: readonly T[],
  fallback: T
): T {
  return raw != null && isOneOf(raw, allowed) ? raw : fallback
}

/**
 * The markdown panel's editing preferences — cookie-backed per the UI
 * preference convention (UI_DESIGN_REFERENCE.md §5), not localStorage, and
 * not a `config_schema.py` runtime knob (ADR-077): these are per-browser
 * editing behavior, not backend/persona configuration.
 */
export function useEditorPreferences(): readonly [
  EditorPreferences,
  <K extends keyof EditorPreferences>(key: K, value: EditorPreferences[K]) => void,
] {
  const [prefs, setPrefs] = React.useState<EditorPreferences>(() => ({
    surface: decodeEnum(
      getCookie(COOKIES.surface),
      ["in-place", "source"],
      DEFAULTS.surface
    ),
    reveal: decodeEnum(
      getCookie(COOKIES.reveal),
      ["caret", "never"],
      DEFAULTS.reveal
    ),
    selectionUI: decodeEnum(
      getCookie(COOKIES.selectionUI),
      ["menu", "bar"],
      DEFAULTS.selectionUI
    ),
    tableEditing: decodeEnum(
      getCookie(COOKIES.tableEditing),
      ["source", "cells"],
      DEFAULTS.tableEditing
    ),
    focusOutline: decodeEnum(
      getCookie(COOKIES.focusOutline),
      ["on", "off"],
      DEFAULTS.focusOutline
    ),
    autosave: decodeEnum(
      getCookie(COOKIES.autosave),
      ["on", "off"],
      DEFAULTS.autosave
    ),
    hideExtension: decodeEnum(
      getCookie(COOKIES.hideExtension),
      ["on", "off"],
      DEFAULTS.hideExtension
    ),
  }))

  const set = React.useCallback(
    <K extends keyof EditorPreferences>(key: K, value: EditorPreferences[K]) => {
      setCookie(COOKIES[key], value)
      setPrefs((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  return [prefs, set] as const
}
