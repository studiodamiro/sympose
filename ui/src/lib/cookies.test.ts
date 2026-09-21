import { describe, expect, it } from "vitest"

import { vaultScopedKey } from "./cookies"

describe("vaultScopedKey", () => {
  it("falls back to the bare base when there's no active vault", () => {
    expect(vaultScopedKey("sympose:shell.note", null)).toBe("sympose:shell.note")
  })

  it("appends a deterministic suffix for a given vault path", () => {
    const key = vaultScopedKey("sympose:shell.note", "/Users/me/Vault")
    expect(key.startsWith("sympose:shell.note:")).toBe(true)
    // same input, same output — this is what lets a hook re-derive the same
    // key across renders without caching it anywhere itself.
    expect(vaultScopedKey("sympose:shell.note", "/Users/me/Vault")).toBe(key)
  })

  it("gives different vault paths different keys", () => {
    const a = vaultScopedKey("sympose:shell.note", "/Users/me/VaultA")
    const b = vaultScopedKey("sympose:shell.note", "/Users/me/VaultB")
    expect(a).not.toBe(b)
  })

  it("never contains characters a cookie name can't reliably hold", () => {
    const key = vaultScopedKey("base", "/Users/me/My Vault (2)/~notes")
    expect(key).toMatch(/^base:[a-z0-9]+$/)
  })
})
