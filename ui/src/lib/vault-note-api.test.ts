import { afterEach, describe, expect, it, vi } from "vitest"

import { moveVaultNote } from "./vault-note-api"

function stubRename(reply: { path: string; detail: string }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve(reply),
  } as Response)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

/** The `new_path` the request carried. */
function sentNewPath(fetchMock: ReturnType<typeof vi.fn>) {
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  return (JSON.parse(init.body as string) as { new_path: string }).new_path
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("moveVaultNote", () => {
  it("asks for the vault root with a leading slash, since a bare name stays in the note's folder", async () => {
    const fetchMock = stubRename({ path: "m.md", detail: "Renamed" })
    const res = await moveVaultNote("F/m.md", "", "samantha")
    expect(sentNewPath(fetchMock)).toBe("/m")
    expect(res).toEqual({ ok: true, path: "m.md", detail: "Renamed" })
  })

  it("asks for a folder by its vault-relative path", async () => {
    const fetchMock = stubRename({ path: "G/H/m.md", detail: "Renamed" })
    await moveVaultNote("F/m.md", "G/H", "samantha")
    expect(sentNewPath(fetchMock)).toBe("G/H/m")
  })

  it("does not call the backend when the note is dropped on its own folder", async () => {
    const fetchMock = stubRename({ path: "", detail: "" })
    expect(await moveVaultNote("F/m.md", "F", "samantha")).toEqual({
      ok: true,
      path: "F/m.md",
      detail: "",
    })
    expect(await moveVaultNote("m.md", "", "samantha")).toEqual({
      ok: true,
      path: "m.md",
      detail: "",
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
