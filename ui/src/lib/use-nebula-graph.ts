import * as React from "react"

import { buildMasterGraph, type NebulaGraph } from "@/lib/nebula-graph"
import rawMock from "@/lib/mock-nebula.json"

/** Which feed is on screen — the live vault or the bundled offline sample. */
export type NebulaGraphSource = "sample" | "live"

export interface NebulaGraphState {
  /** Master graph (notes + pre-indexed tag hubs), ready for the renderers. */
  graph: NebulaGraph
  /** `"live"` once `GET /api/vault/graph` has answered with nodes. */
  source: NebulaGraphSource
}

const MOCK_MASTER = buildMasterGraph(rawMock as NebulaGraph)

/**
 * The Knowledge Nebula's data feed. First paint (and the offline fallback) is
 * the bundled `mock-nebula.json`; once `GET /api/vault/graph` answers with
 * nodes we swap to the live vault and flip `source` to `"live"`. The endpoint
 * is whole-vault and persona-independent (wiki spec §2 Module A) — the nebula
 * is an explorer surface, not a persona-scoped one — so this takes no persona.
 *
 * Shared by the in-shell ambient layer and the standalone `/nebula` showcase
 * so both read exactly one implementation of the fetch + fold.
 */
export function useNebulaGraph(): NebulaGraphState {
  const [state, setState] = React.useState<NebulaGraphState>({
    graph: MOCK_MASTER,
    source: "sample",
  })

  React.useEffect(() => {
    let cancelled = false
    fetch("/api/vault/graph")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: NebulaGraph) => {
        if (cancelled) return
        if (data?.nodes?.length) {
          setState({ graph: buildMasterGraph(data), source: "live" })
          console.info(
            `[nebula] live vault · ${data.nodes.length} notes, ${data.links?.length ?? 0} links from /api/vault/graph`
          )
        } else {
          console.info(
            "[nebula] /api/vault/graph returned no nodes — showing the bundled sample"
          )
        }
      })
      .catch((err) => {
        if (!cancelled)
          console.info(
            `[nebula] /api/vault/graph unreachable (${err}) — showing the bundled sample`
          )
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
