import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Drop a trailing `.md` (case-insensitive) for display — the vault tree and
 *  main-menu labels show this instead of the raw filename when the "File
 *  extensions" preference is off. Non-`.md` names (folders, attachments)
 *  pass through unchanged. */
export function stripMdExtension(name: string): string {
  return name.replace(/\.md$/i, "")
}

/** True when `value` is one of `allowed` — the guard a cookie-backed enum
 *  preference runs a decoded string through before trusting it, so a stale or
 *  hand-edited cookie value can't smuggle an unrecognized value past a bare
 *  `as` cast. */
export function isOneOf<T extends string>(
  value: string,
  allowed: readonly T[]
): value is T {
  return (allowed as readonly string[]).includes(value)
}
