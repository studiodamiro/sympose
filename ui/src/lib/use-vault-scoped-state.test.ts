// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { getCookie } from "./cookies"
import { useVaultScopedState } from "./use-vault-scoped-state"

const COOKIE = "sympose:test.scoped"

function read(raw: string | null): string[] {
  return raw ? raw.split(",").filter(Boolean) : []
}

function serialize(value: string[]): string {
  return value.join(",")
}

function clearCookies() {
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0]?.trim()
    if (name) document.cookie = `${name}=; path=/; max-age=0`
  })
}

describe("useVaultScopedState", () => {
  beforeEach(() => {
    clearCookies()
  })

  it("starts from `read(null)` before a vault is known", () => {
    const { result } = renderHook(() => useVaultScopedState(COOKIE, null, read, serialize))
    expect(result.current[0]).toEqual([])
  })

  it("persists a value change to the scoped cookie", () => {
    const { result } = renderHook(() =>
      useVaultScopedState(COOKIE, "/vault-a", read, serialize)
    )

    act(() => result.current[1](["a.md"]))

    expect(result.current[0]).toEqual(["a.md"])
    // find the scoped key by reading back through the same read function —
    // the exact key format is cookies.ts's concern, not this hook's.
    const cookieNames = document.cookie
      .split(";")
      .map((c) => c.split("=")[0]?.trim())
      .filter((n): n is string => Boolean(n) && n.startsWith(COOKIE))
    expect(cookieNames).toHaveLength(1)
    expect(getCookie(cookieNames[0])).toBe("a.md")
  })

  it("does not leak a value across a vault switch", () => {
    const { result, rerender } = renderHook(
      ({ vaultPath }) => useVaultScopedState(COOKIE, vaultPath, read, serialize),
      { initialProps: { vaultPath: "/vault-a" as string | null } }
    )

    act(() => result.current[1](["a.md"]))
    expect(result.current[0]).toEqual(["a.md"])

    rerender({ vaultPath: "/vault-b" })
    expect(result.current[0]).toEqual([])

    act(() => result.current[1](["b.md"]))
    expect(result.current[0]).toEqual(["b.md"])
  })

  it("restores a vault's own value when switching back to it", () => {
    const { result, rerender } = renderHook(
      ({ vaultPath }) => useVaultScopedState(COOKIE, vaultPath, read, serialize),
      { initialProps: { vaultPath: "/vault-a" as string | null } }
    )

    act(() => result.current[1](["a.md"]))
    rerender({ vaultPath: "/vault-b" })
    act(() => result.current[1](["b.md"]))

    rerender({ vaultPath: "/vault-a" })
    expect(result.current[0]).toEqual(["a.md"])

    rerender({ vaultPath: "/vault-b" })
    expect(result.current[0]).toEqual(["b.md"])
  })

  it("does not reset the value on a re-render with the same vault", () => {
    const { result, rerender } = renderHook(
      ({ vaultPath }) => useVaultScopedState(COOKIE, vaultPath, read, serialize),
      { initialProps: { vaultPath: "/vault-a" as string | null } }
    )

    act(() => result.current[1](["a.md"]))
    rerender({ vaultPath: "/vault-a" })
    rerender({ vaultPath: "/vault-a" })

    expect(result.current[0]).toEqual(["a.md"])
  })

  it("never clobbers a pre-existing cookie with the mount-time placeholder", () => {
    // Simulates a returning session: real data already sits under the key
    // this hook will resolve to at mount (here, the bare `vaultPath: null`
    // key) before the hook ever renders.
    document.cookie = `${COOKIE}=${encodeURIComponent("existing.md")}; path=/`

    const { result } = renderHook(() => useVaultScopedState(COOKIE, null, read, serialize))

    expect(result.current[0]).toEqual(["existing.md"])
    // The write effect's mount-time run (still holding `read(null)`'s
    // placeholder) must not have overwritten this with an empty value.
    expect(getCookie(COOKIE)).toBe("existing.md")
  })

  it("supports a functional updater, like React's own setState", () => {
    const { result } = renderHook(() =>
      useVaultScopedState(COOKIE, "/vault-a", read, serialize)
    )

    act(() => result.current[1](["a.md"]))
    act(() => result.current[1]((prev) => [...prev, "b.md"]))

    expect(result.current[0]).toEqual(["a.md", "b.md"])
  })
})
