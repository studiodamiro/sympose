import * as React from "react"

import { cn } from "@/lib/utils"
import { useEffectiveTheme } from "@/lib/use-effective-theme"
import {
  FOLDER_COLORS,
  FOLDER_COLORS_LIGHT,
  foldersInGraph,
} from "@/lib/nebula-graph"
import { useNebulaFilter } from "@/lib/nebula-filter"
import { useNebulaGraph } from "@/lib/use-nebula-graph"
import type { NebulaPreferences } from "@/lib/use-nebula-preferences"
import { NebulaControls } from "@/components/sympose/nebula-controls"
import { KnowledgeNebula2D } from "@/components/sympose/knowledge-nebula-2d"
import type { KnowledgeNebulaHandle } from "@/components/sympose/knowledge-nebula-shared"

type SetPref = <K extends keyof NebulaPreferences>(
  key: K,
  value: NebulaPreferences[K]
) => void

/**
 * Module A in the app shell — the persistent full-bleed Knowledge Nebula layer
 * that lives *behind* every panel (UI_DESIGN_REFERENCE.md §4–§5). It has two
 * states, driven by `prefs.interaction`:
 *
 *  - **Explore** — sharp and interactive (`pointer-events: auto`), the control
 *    dock and the folder legend on screen.
 *  - **Focus** (default) — dimmed and inert (`pointer-events: none`), no dock,
 *    so the foreground panels own the interaction. The shell paints its own
 *    matte scrim over this so panels stay legible.
 *
 * Phase A ships the 2D canvas renderer only — imported directly so three.js
 * stays out of the bundle until the 3D renderer lands (Phase B). The app shell
 * lazy-mounts this component after first paint so `react-force-graph` never
 * sits on the TTFT hot path.
 */
function AmbientNebula({
  prefs,
  setPref,
  activeNoteId,
}: {
  prefs: NebulaPreferences
  setPref: SetPref
  /** The note currently open in the content panel (bare filename stem, same
   *  id space as `NebulaNode.id`). Drives the same fly-to-node-and-highlight
   *  behavior as an in-nebula click, so browsing notes elsewhere keeps the
   *  ambient background in sync — in both Focus and Explore. */
  activeNoteId?: string
}) {
  const theme = useEffectiveTheme()
  const isLight = theme === "light"
  const explore = prefs.interaction === "explore"

  const { graph, source } = useNebulaGraph()
  const nebulaRef = React.useRef<KnowledgeNebulaHandle>(null)
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null)

  React.useEffect(() => {
    if (!activeNoteId) return
    setSelectedNodeId(activeNoteId)
    nebulaRef.current?.focusNode(activeNoteId)
  }, [activeNoteId])

  // The selection (and the highlight it drives) is kept across Explore ⇄ Focus
  // — it only *changes* while interactive, but a Focus trip and back leaves it
  // exactly as it was.
  const { highlightedNodeIds, hiddenNodeIds } = useNebulaFilter(graph, {
    query: "",
    showTags: prefs.tags,
    showAttachments: prefs.attachments,
    existingOnly: prefs.existingOnly,
    showOrphans: prefs.orphans,
    selectedNodeId,
  })

  const folders = foldersInGraph(graph)
  const folderColors = isLight ? FOLDER_COLORS_LIGHT : FOLDER_COLORS

  return (
    <div
      data-slot="ambient-nebula"
      data-interaction={prefs.interaction}
      className={cn(
        // Always the bottom of the stack — never rises above the shell, in
        // either mode. Explore interactivity comes from the stage giving up
        // pointer events (see the stage `pointer-events-none` in app-shell),
        // not from this layer climbing in front of it.
        "fixed inset-0 z-0",
        !explore && "pointer-events-none"
      )}
    >
      <KnowledgeNebula2D
        ref={nebulaRef}
        graph={graph}
        className="absolute inset-0"
        isLight={isLight}
        dimmed={!explore}
        interactive={explore}
        showLabels={prefs.labels}
        showArrows={prefs.arrows}
        highlightedNodeIds={highlightedNodeIds}
        hiddenNodeIds={hiddenNodeIds}
        nodeRelSize={prefs.nodeRelSize}
        nodeSeparation={prefs.nodeSeparation}
        nodeVividness={prefs.nodeVividness}
        linkWidth={prefs.linkWidth}
        clickZoomDistance={prefs.clickZoomDistance}
        centerForce={prefs.centerForce}
        repelForce={prefs.repelForce}
        linkForce={prefs.linkForce}
        linkDistance={prefs.linkDistance}
        onNodeClick={(n) => setSelectedNodeId(n.id)}
        onBackgroundClick={() => {
          setSelectedNodeId(null)
          nebulaRef.current?.zoomToFit(600, 48)
        }}
      />

      {/* Focus dimming — two independent layers so blur and tint don't fight.
          The blur layer stays fully opaque-free (just a `backdrop-filter`) so
          its blur always renders; the tint layer is a solid `--background`
          card at `focusTint` element opacity — a clean 0 (clear) → 1 (fully
          covered). Both clear in Explore. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 transition-[backdrop-filter] duration-300"
        style={{
          backdropFilter: explore ? "none" : `blur(${prefs.focusBlur}px)`,
          WebkitBackdropFilter: explore ? "none" : `blur(${prefs.focusBlur}px)`,
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-background transition-opacity duration-300"
        style={{ opacity: explore ? 0 : prefs.focusTint }}
      />

      {/* Explore-only chrome: data-source badge, folder legend, control dock. */}
      <div
        className={cn(
          "transition-opacity duration-300",
          explore ? "opacity-100" : "pointer-events-none opacity-0"
        )}
      >
        {prefs.legend && folders.length > 0 && (
          <div className="pointer-events-none absolute top-4 left-4 flex max-w-[40vw] flex-wrap gap-x-3 gap-y-1">
            {folders.map((f) => (
              <span
                key={f}
                className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground"
              >
                <span
                  className="size-2 rounded-full"
                  style={{ background: folderColors[f] }}
                />
                {f}
              </span>
            ))}
          </div>
        )}

        {/* Bottom-right cluster — the data-source badge stacked above the
            dock (moved off bottom-left, where it collided with the menu
            rail's account row) rather than absolutely positioned on its own,
            so the two can never overlap regardless of the dock's height. */}
        <div className="pointer-events-none absolute right-4 bottom-4 flex flex-col items-end gap-2">
          <div className="flex items-center gap-1.5 rounded-full border border-border bg-card/90 px-2.5 py-1 font-mono text-[11px] text-muted-foreground backdrop-blur-sm">
            <span
              className={cn(
                "size-1.5 rounded-full",
                source === "live" ? "bg-ok" : "bg-fg-muted"
              )}
            />
            {source === "live" ? "live vault" : "bundled sample"} · {graph.nodes.length} nodes
          </div>

          {prefs.dock && (
            <NebulaControls
              prefs={prefs}
              setPref={setPref}
              className="pointer-events-auto max-h-[80vh] overflow-y-auto"
            />
          )}
        </div>
      </div>
    </div>
  )
}

export { AmbientNebula }
