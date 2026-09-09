import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"

export type EditorSurface = "in-place" | "source"
export type EditorReveal = "caret" | "never"
export type EditorSelectionUI = "menu" | "bar"
export type EditorFocusOutline = "on" | "off"

export interface EditorPreferences {
  surface: EditorSurface
  reveal: EditorReveal
  selectionUI: EditorSelectionUI
  focusOutline: EditorFocusOutline
}

const COOKIES = {
  surface: "sympose:editor.surface",
  reveal: "sympose:editor.reveal",
  selectionUI: "sympose:editor.selection_ui",
  focusOutline: "sympose:editor.focus_outline",
} as const

const DEFAULTS: EditorPreferences = {
  surface: "in-place",
  reveal: "caret",
  selectionUI: "menu",
  focusOutline: "off",
}

/**
 * The markdown panel's editing preferences — cookie-backed per the UI
 * preference convention (UI_DESIGN_REFERENCE.md §5), not localStorage, and
 * not a `config_schema.py` runtime knob (ADR-077): these are per-browser
 * editing behavior, not backend/agent configuration.
 */
export function useEditorPreferences(): readonly [
  EditorPreferences,
  <K extends keyof EditorPreferences>(key: K, value: EditorPreferences[K]) => void,
] {
  const [prefs, setPrefs] = React.useState<EditorPreferences>(() => ({
    surface: (getCookie(COOKIES.surface) as EditorSurface) || DEFAULTS.surface,
    reveal: (getCookie(COOKIES.reveal) as EditorReveal) || DEFAULTS.reveal,
    selectionUI:
      (getCookie(COOKIES.selectionUI) as EditorSelectionUI) ||
      DEFAULTS.selectionUI,
    focusOutline:
      (getCookie(COOKIES.focusOutline) as EditorFocusOutline) ||
      DEFAULTS.focusOutline,
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
