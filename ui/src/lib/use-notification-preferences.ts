import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"

export type NotifyEnabled = "on" | "off"
/** How a *recoverable* destructive action (move-to-Bin) asks first. */
export type ConfirmStyle = "dialog" | "inline" | "none"
export type ToastPosition =
  | "top-left"
  | "top-center"
  | "top-right"
  | "bottom-left"
  | "bottom-center"
  | "bottom-right"

export interface NotificationPreferences {
  /** Feedback toasts ("Saved", "Moved to bin", errors). `"off"` silences them. */
  enabled: NotifyEnabled
  /**
   * The prompt shown before a recoverable delete. `"none"` runs it straight
   * away — the file still goes to the Bin, so it stays recoverable. Permanent
   * actions ("Delete forever", "Empty bin") always confirm regardless.
   */
  confirm: ConfirmStyle
  /** Where feedback toasts and the inline confirm appear. */
  position: ToastPosition
}

export const TOAST_POSITIONS: ToastPosition[] = [
  "top-left",
  "top-center",
  "top-right",
  "bottom-left",
  "bottom-center",
  "bottom-right",
]

const COOKIES = {
  enabled: "sympose:notify.enabled",
  confirm: "sympose:notify.confirm",
  position: "sympose:notify.position",
} as const

const DEFAULTS: NotificationPreferences = {
  enabled: "on",
  confirm: "dialog",
  position: "bottom-right",
}

function read(): NotificationPreferences {
  const confirm = getCookie(COOKIES.confirm)
  const position = getCookie(COOKIES.position)
  return {
    enabled: getCookie(COOKIES.enabled) === "off" ? "off" : "on",
    confirm: confirm === "inline" || confirm === "none" ? confirm : "dialog",
    position: TOAST_POSITIONS.includes(position as ToastPosition)
      ? (position as ToastPosition)
      : DEFAULTS.position,
  }
}

// A module-level store, not `useState` seeded per hook: the imperative `notify`
// and `confirm` helpers (`lib/notify`, `lib/confirm`) read the current prefs
// without a React context, and every `useNotificationPreferences()` caller
// stays in sync through `useSyncExternalStore`.
let store: NotificationPreferences = read()
const listeners = new Set<() => void>()

export function getNotificationPreferences(): NotificationPreferences {
  return store
}

export function setNotificationPreference<
  K extends keyof NotificationPreferences,
>(key: K, value: NotificationPreferences[K]): void {
  setCookie(COOKIES[key], value)
  store = { ...store, [key]: value }
  for (const l of listeners) l()
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

export function useNotificationPreferences(): readonly [
  NotificationPreferences,
  <K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K]
  ) => void,
] {
  const snapshot = React.useSyncExternalStore(
    subscribe,
    getNotificationPreferences,
    getNotificationPreferences
  )
  return [snapshot, setNotificationPreference] as const
}
