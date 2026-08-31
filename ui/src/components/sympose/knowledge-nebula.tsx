import * as React from "react"

import { KnowledgeNebula2D } from "./knowledge-nebula-2d"
import { KnowledgeNebula3D } from "./knowledge-nebula-3d"
import {
  type KnowledgeNebulaHandle,
  type KnowledgeNebulaProps,
} from "./knowledge-nebula-shared"

export type { KnowledgeNebulaHandle, KnowledgeNebulaProps } from "./knowledge-nebula-shared"

/**
 * Module A — the Ambient Knowledge Nebula (wiki spec §2, ADR-051/052). A
 * force-directed view of the vault: notes are nodes coloured by folder and
 * sized by link degree, `[[wikilinks]]` are the edges.
 *
 * This wrapper picks the renderer from `mode`:
 *  - `"3d"` (default) — a WebGL cloud (three.js). Orbit / auto-rotate.
 *  - `"2d"` — the flat Obsidian-style canvas graph. Pan / zoom, zoom-gated labels.
 *
 * Both share the {@link KnowledgeNebulaProps} feed and the imperative
 * {@link KnowledgeNebulaHandle}, so toggling `mode` is transparent to callers —
 * `ref.current` stays valid across the swap. The feed is a plain `NebulaGraph`;
 * the showcase passes `mock-nebula.json` and swapping to `GET /api/vault/graph`
 * is a one-line change upstream.
 *
 * `index.ts` intentionally does NOT re-export this — it pulls in three.js and
 * `react-force-graph`. Import it directly, lazily.
 */
const KnowledgeNebula = React.forwardRef<
  KnowledgeNebulaHandle,
  KnowledgeNebulaProps
>(({ mode = "3d", ...props }, ref) =>
  mode === "2d" ? (
    <KnowledgeNebula2D ref={ref} {...props} />
  ) : (
    <KnowledgeNebula3D ref={ref} {...props} />
  )
)

KnowledgeNebula.displayName = "KnowledgeNebula"

export { KnowledgeNebula }
