// @vitest-environment jsdom
import { renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useNebulaGraph } from "./use-nebula-graph"

function graphResponse(ids: string[]) {
  return {
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        nodes: ids.map((id) => ({
          id,
          label: id,
          folder: "",
          tags: [],
          val: 1,
          exists: true,
        })),
        links: [],
      }),
  } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("useNebulaGraph persona scoping (ADR 010)", () => {
  it("requests the graph for the active persona", async () => {
    const fetchMock = vi.fn().mockResolvedValue(graphResponse(["a.md"]))
    vi.stubGlobal("fetch", fetchMock)

    renderHook(() => useNebulaGraph(0, "/vault", "dev"))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(fetchMock).toHaveBeenCalledWith("/api/vault/graph?persona=dev")
  })

  it("refetches when the persona changes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(graphResponse(["a.md"]))
    vi.stubGlobal("fetch", fetchMock)

    const { rerender } = renderHook(
      ({ persona }) => useNebulaGraph(0, "/vault", persona),
      { initialProps: { persona: "samantha" } }
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    rerender({ persona: "dev" })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock).toHaveBeenLastCalledWith("/api/vault/graph?persona=dev")
  })

  it("shows an empty live graph, not the sample, for a persona with no visible notes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(graphResponse([])))

    const { result } = renderHook(() => useNebulaGraph(0, "/vault", "dev"))

    await waitFor(() => expect(result.current.source).toBe("live"))
    expect(result.current.graph.nodes).toEqual([])
  })

  it("empties the previous persona's graph when the new persona has nothing visible", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(graphResponse(["wide.md"]))
      .mockResolvedValueOnce(graphResponse([]))
    vi.stubGlobal("fetch", fetchMock)

    const { result, rerender } = renderHook(
      ({ persona }) => useNebulaGraph(0, "/vault", persona),
      { initialProps: { persona: "samantha" } }
    )
    await waitFor(() => expect(result.current.graph.nodes.length).toBe(1))

    rerender({ persona: "dev" })

    await waitFor(() => expect(result.current.graph.nodes).toEqual([]))
    expect(result.current.source).toBe("live")
  })

  it("drops the previous persona's graph when the new persona's fetch fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(graphResponse(["wide.md"]))
      .mockRejectedValueOnce(new Error("offline"))
    vi.stubGlobal("fetch", fetchMock)

    const { result, rerender } = renderHook(
      ({ persona }) => useNebulaGraph(0, "/vault", persona),
      { initialProps: { persona: "samantha" } }
    )
    await waitFor(() => expect(result.current.source).toBe("live"))

    rerender({ persona: "dev" })

    // A wider graph must never linger under a narrower persona.
    await waitFor(() => expect(result.current.source).toBe("sample"))
  })
})
