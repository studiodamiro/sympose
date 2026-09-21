import { afterEach, describe, expect, it, vi } from "vitest"

import { addVault, fetchVaults, setActiveVault } from "./vaults-api"

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 500) {
  return {
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("fetchVaults", () => {
  it("returns the vaults and active path on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          vaults: [{ name: "garden", path: "/vault/garden" }],
          active: "/vault/garden",
        })
      )
    )
    expect(await fetchVaults()).toEqual({
      vaults: [{ name: "garden", path: "/vault/garden" }],
      active: "/vault/garden",
    })
  })

  it("returns an empty state when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchVaults()).toEqual({ vaults: [], active: null })
  })

  it("returns an empty state on a non-OK response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, false, 500)))
    expect(await fetchVaults()).toEqual({ vaults: [], active: null })
  })
})

describe("setActiveVault", () => {
  it("resolves ok with the updated state on success", async () => {
    const state = { vaults: [{ name: "a", path: "/a" }], active: "/a" }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(state)))
    expect(await setActiveVault("/a")).toEqual({ ok: true, state })
  })

  it("resolves not-ok with the backend's detail message on 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Not a configured vault" }, false, 404))
    )
    const result = await setActiveVault("/nope")
    expect(result).toEqual({ ok: false, error: "Not a configured vault" })
  })

  it("resolves not-ok when the backend is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")))
    const result = await setActiveVault("/a")
    expect(result.ok).toBe(false)
  })
})

describe("addVault", () => {
  it("resolves ok with the updated state on success", async () => {
    const state = { vaults: [{ name: "new", path: "/new" }], active: "/new" }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(state)))
    expect(await addVault("/new")).toEqual({ ok: true, state })
  })

  it("resolves not-ok with the backend's detail message on 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "That path doesn't exist" }, false, 400)
      )
    )
    expect(await addVault("/missing")).toEqual({
      ok: false,
      error: "That path doesn't exist",
    })
  })
})
