// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { useRecentNotes } from "./use-recent-notes"

function clearCookies() {
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0]?.trim()
    if (name) document.cookie = `${name}=; path=/; max-age=0`
  })
}

describe("useRecentNotes", () => {
  beforeEach(() => {
    clearCookies()
  })

  it("starts empty before a vault is known", () => {
    const { result } = renderHook(() => useRecentNotes(null))
    expect(result.current.recentPaths).toEqual([])
  })

  it("records a visit, moving it to the front and deduping repeats", () => {
    const { result } = renderHook(() => useRecentNotes("/vault-a"))

    act(() => result.current.recordVisit("a.md"))
    act(() => result.current.recordVisit("b.md"))
    expect(result.current.recentPaths).toEqual(["b.md", "a.md"])

    act(() => result.current.recordVisit("a.md"))
    expect(result.current.recentPaths).toEqual(["a.md", "b.md"])
  })

  it("caps stored history at 20 entries", () => {
    const { result } = renderHook(() => useRecentNotes("/vault-a"))

    for (let i = 0; i < 25; i++) {
      act(() => result.current.recordVisit(`note-${i}.md`))
    }
    act(() => result.current.setShownCount(20))
    expect(result.current.recentPaths).toHaveLength(20)
    // most recent first, oldest 5 fell off
    expect(result.current.recentPaths[0]).toBe("note-24.md")
    expect(result.current.recentPaths).not.toContain("note-0.md")
  })

  it("removes a single path via removeFromRecents", () => {
    const { result } = renderHook(() => useRecentNotes("/vault-a"))

    act(() => result.current.recordVisit("a.md"))
    act(() => result.current.recordVisit("b.md"))
    act(() => result.current.removeFromRecents("a.md"))

    expect(result.current.recentPaths).toEqual(["b.md"])
  })

  it("empties history via clearRecents", () => {
    const { result } = renderHook(() => useRecentNotes("/vault-a"))

    act(() => result.current.recordVisit("a.md"))
    act(() => result.current.clearRecents())

    expect(result.current.recentPaths).toEqual([])
  })

  it("hides recentPaths while disabled, without dropping history", () => {
    const { result } = renderHook(() => useRecentNotes("/vault-a"))

    act(() => result.current.recordVisit("a.md"))
    act(() => result.current.setEnabled(false))
    expect(result.current.recentPaths).toEqual([])

    act(() => result.current.setEnabled(true))
    expect(result.current.recentPaths).toEqual(["a.md"])
  })

  it("respects shownCount as a display cap under the stored history", () => {
    const { result } = renderHook(() => useRecentNotes("/vault-a"))

    act(() => result.current.recordVisit("a.md"))
    act(() => result.current.recordVisit("b.md"))
    act(() => result.current.recordVisit("c.md"))
    act(() => result.current.setShownCount(2))

    expect(result.current.recentPaths).toEqual(["c.md", "b.md"])
  })

  it("keeps shownCount and enabled global across a vault switch", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => useRecentNotes(vaultPath), {
      initialProps: { vaultPath: "/vault-a" },
    })

    act(() => result.current.setShownCount(2))
    act(() => result.current.setEnabled(false))

    rerender({ vaultPath: "/vault-b" })

    expect(result.current.shownCount).toBe(2)
    expect(result.current.enabled).toBe(false)
  })

  it("does not leak history across a vault switch", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => useRecentNotes(vaultPath), {
      initialProps: { vaultPath: "/vault-a" as string | null },
    })

    act(() => result.current.recordVisit("a-note.md"))
    expect(result.current.recentPaths).toEqual(["a-note.md"])

    rerender({ vaultPath: "/vault-b" })
    expect(result.current.recentPaths).toEqual([])

    act(() => result.current.recordVisit("b-note.md"))
    expect(result.current.recentPaths).toEqual(["b-note.md"])
  })

  it("restores a vault's own history when switching back to it", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => useRecentNotes(vaultPath), {
      initialProps: { vaultPath: "/vault-a" as string | null },
    })

    act(() => result.current.recordVisit("a-note.md"))
    rerender({ vaultPath: "/vault-b" })
    act(() => result.current.recordVisit("b-note.md"))

    rerender({ vaultPath: "/vault-a" })
    expect(result.current.recentPaths).toEqual(["a-note.md"])

    rerender({ vaultPath: "/vault-b" })
    expect(result.current.recentPaths).toEqual(["b-note.md"])
  })

  it("does not reset history on a re-render with the same vault (reseed-on-every-render regression)", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => useRecentNotes(vaultPath), {
      initialProps: { vaultPath: "/vault-a" as string | null },
    })

    act(() => result.current.recordVisit("a-note.md"))
    rerender({ vaultPath: "/vault-a" })
    rerender({ vaultPath: "/vault-a" })

    expect(result.current.recentPaths).toEqual(["a-note.md"])
  })

  it("resolves the unscoped, pre-vault history once the vault becomes known", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => useRecentNotes(vaultPath), {
      initialProps: { vaultPath: null as string | null },
    })

    act(() => result.current.recordVisit("early.md"))
    expect(result.current.recentPaths).toEqual(["early.md"])

    rerender({ vaultPath: "/vault-a" })
    // the pre-vault write lived on the bare, unscoped key — a real vault's
    // scoped key starts fresh, it does not inherit it.
    expect(result.current.recentPaths).toEqual([])
  })
})
