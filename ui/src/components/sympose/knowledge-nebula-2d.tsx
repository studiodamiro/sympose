import * as React from "react"
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d"
import { forceRadial } from "d3-force"

import { cn } from "@/lib/utils"
import { type NebulaGraph, type NebulaNode } from "@/lib/nebula-graph"
import {
  clamp,
  createNodeTooltip,
  nebulaNodeColor,
  nodeRenderVal,
  useElementSize,
  type KnowledgeNebulaHandle,
  type KnowledgeNebulaProps,
} from "./knowledge-nebula-shared"

/**
 * Knowledge Nebula — 2D variant. The flat, Obsidian-default knowledge-graph
 * skin: a `<canvas>` force layout where notes are folder-coloured discs,
 * `[[wikilinks]]` are hairline edges, and labels fade in as you zoom past
 * {@link LABEL_FADE_START}. Reached through `<KnowledgeNebula>` with `mode="2d"`.
 *
 * It honours the same {@link KnowledgeNebulaProps} / {@link KnowledgeNebulaHandle}
 * contract as the 3D renderer; camera flights map to `centerAt()` + `zoom()`
 * instead of `cameraPosition()`, and `autoRotate` has no meaning here.
 */
const MIN_ZOOM = 0.04
const MAX_ZOOM = 12
/** `globalScale` (zoom) at which node labels start / finish fading in. */
const LABEL_FADE_START = 1.6
const LABEL_FADE_END = 3.4

const KnowledgeNebula2D = React.forwardRef<
  KnowledgeNebulaHandle,
  KnowledgeNebulaProps
>(
  (
    {
      graph,
      className,
      dimmed = false,
      interactive,
      isLight = false,
      showLabels = true,
      highlightedNodeIds,
      hiddenNodeIds,
      clickZoomDistance = 60,
      nodeRelSize = 4,
      nodeSeparation = 0,
      nodeVividness = 0,
      linkWidth,
      linkParticles = 0,
      showArrows = false,
      repelForce,
      linkDistance,
      linkForce,
      centerForce,
      onNodeClick,
      onBackgroundClick,
    },
    ref
  ) => {
    const containerRef = React.useRef<HTMLDivElement>(null)
    const fgRef = React.useRef<ForceGraphMethods | undefined>(undefined)
    const timerRef = React.useRef<any>(null)
    const didInitialFitRef = React.useRef(false)
    const { w, h } = useElementSize(containerRef)
    const live = interactive ?? !dimmed

    // force-graph mutates what it is handed (link ends become node refs, x/y get
    // written). Clone so the caller's data — a JSON import singleton — is safe.
    const data = React.useMemo(() => {
      const cloned = structuredClone(graph) as NebulaGraph
      cloned.nodes.forEach((n: any) => {
        n.__scale = 1.0
      })
      return cloned
    }, [graph])

    // Centroid + zoom factor that frames a node together with its 1-hop cluster.
    const getClusterFraming = (nodeId: string, knobDist = clickZoomDistance) => {
      const memberIds = new Set<string>([nodeId])
      data.links.forEach((l: any) => {
        const srcId = typeof l.source === "object" ? l.source.id : l.source
        const tgtId = typeof l.target === "object" ? l.target.id : l.target
        if (srcId === nodeId) memberIds.add(tgtId)
        if (tgtId === nodeId) memberIds.add(srcId)
      })
      const members = (data.nodes as any[]).filter((n) => memberIds.has(n.id))
      if (members.length === 0) return null

      let sumX = 0, sumY = 0
      members.forEach((n) => {
        sumX += n.x ?? 0
        sumY += n.y ?? 0
      })
      const cx = sumX / members.length
      const cy = sumY / members.length

      let radius = 40
      members.forEach((n) => {
        const r = Math.hypot((n.x ?? 0) - cx, (n.y ?? 0) - cy)
        if (r > radius) radius = r
      })

      // force-graph zoom is px-per-graph-unit; fit the cluster into the shorter
      // viewport axis, then bias by the closeness knob (60 = neutral).
      const viewport = Math.min(w || 900, h || 640)
      const knob = 60 / Math.max(1, knobDist)
      const k = clamp(((viewport - 140) / (2 * radius)) * knob, MIN_ZOOM, MAX_ZOOM)
      return { cx, cy, k }
    }

    React.useImperativeHandle(ref, () => ({
      zoomToFit: (duration = 600, padding = 48) => {
        fgRef.current?.zoomToFit(duration, padding)
      },
      focusNode: (nodeOrId: NebulaNode | string, distance?: number, duration = 700) => {
        const fg = fgRef.current
        if (!fg) return
        const id = typeof nodeOrId === "string" ? nodeOrId : nodeOrId.id
        const framing = getClusterFraming(id, distance ?? clickZoomDistance)
        if (!framing) return
        fg.centerAt(framing.cx, framing.cy, duration)
        fg.zoom(framing.k, duration)
      },
      fitNodes: (nodeIds: string[] | Set<string>, duration = 700, padding = 40) => {
        const fg = fgRef.current
        if (!fg) return
        const idSet = new Set(nodeIds)
        const matching = (data.nodes as any[]).some((n) => idSet.has(n.id))
        if (!matching) return
        fg.zoomToFit(duration, padding, (n: any) => idSet.has(n.id))
      },
      animateBirth: (noteDelayMs = 25) => {
        const fg = fgRef.current
        if (!fg) return

        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }

        const totalNodes = data.nodes.length
        if (totalNodes === 0) return

        // Scatter every node and hide it, then reveal one by one.
        data.nodes.forEach((n: any) => {
          n.x = (Math.random() - 0.5) * 900
          n.y = (Math.random() - 0.5) * 900
          n.vx = (Math.random() - 0.5) * 8
          n.vy = (Math.random() - 0.5) * 8
          n.__birthed = false
        })
        fg.d3ReheatSimulation()

        let currentIdx = 0
        timerRef.current = setInterval(() => {
          if (currentIdx < totalNodes) {
            ;(data.nodes[currentIdx] as any).__birthed = true
            currentIdx++
            fg.d3ReheatSimulation()
          } else {
            clearInterval(timerRef.current)
            timerRef.current = null
            data.nodes.forEach((n: any) => {
              n.__birthed = true
            })
            fg.d3ReheatSimulation()
          }
        }, Math.max(5, noteDelayMs))
      },
    }))

    // Clear an in-flight birth animation on unmount.
    React.useEffect(() => {
      return () => {
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
      }
    }, [])

    // Dynamic d3 force adjustments — same knob math as the 3D renderer so the
    // Forces sliders behave identically across modes.
    React.useEffect(() => {
      const fg = fgRef.current
      if (!fg) return
      if (centerForce !== undefined) {
        fg.d3Force("radial", forceRadial(0, 0, 0).strength(centerForce * 0.8))
      }
      if (repelForce !== undefined) {
        fg.d3Force("charge")?.strength(-repelForce * 12)
      }
      if (linkDistance !== undefined) {
        fg.d3Force("link")?.distance(linkDistance)
      }
      if (linkForce !== undefined) {
        fg.d3Force("link")?.strength(linkForce)
      }
      fg.d3ReheatSimulation()
    }, [repelForce, linkDistance, linkForce, centerForce])

    // Frame the whole graph once the first layout settles, plus a safety net in
    // case the engine never reports a stop.
    const fitWhole = React.useCallback(() => {
      if (didInitialFitRef.current) return
      didInitialFitRef.current = true
      fgRef.current?.zoomToFit(400, 60)
    }, [])

    React.useEffect(() => {
      const t = setTimeout(fitWhole, 1500)
      return () => clearTimeout(t)
    }, [fitWhole])

    const tooltipFn = React.useMemo(() => createNodeTooltip(isLight), [isLight])
    const defaultLinkWidth = isLight ? 1.0 : 0.7
    const activeLinkWidth = linkWidth ?? defaultLinkWidth

    const isDimmed = React.useCallback(
      (id: string) => !!highlightedNodeIds && !highlightedNodeIds.has(id),
      [highlightedNodeIds]
    )

    const linkEndsHidden = (l: any) => {
      const srcId = typeof l.source === "object" ? l.source.id : l.source
      const tgtId = typeof l.target === "object" ? l.target.id : l.target
      return { srcId, tgtId }
    }

    // Obsidian-style label: drawn under the disc, fading in with zoom.
    const paintNodeLabel = (
      node: any,
      ctx: CanvasRenderingContext2D,
      globalScale: number
    ) => {
      if (!showLabels) return
      if (node.__birthed === false) return
      if (isDimmed(node.id)) return
      const alpha = clamp(
        (globalScale - LABEL_FADE_START) / (LABEL_FADE_END - LABEL_FADE_START),
        0,
        1
      )
      if (alpha < 0.02) return

      const label: string = node.label ?? node.id
      const fontSize = Math.max(10 / globalScale, 1.8)
      ctx.font = `${fontSize}px 'Inter Variable', system-ui, sans-serif`
      ctx.textAlign = "center"
      ctx.textBaseline = "top"
      const discRadius =
        Math.sqrt(Math.max(0, nodeRenderVal(node, highlightedNodeIds))) *
        nodeRelSize
      ctx.fillStyle = isLight
        ? `rgba(15,23,42,${0.88 * alpha})`
        : `rgba(226,232,240,${0.92 * alpha})`
      ctx.fillText(label, node.x, node.y + discRadius + 1.5 / globalScale)
    }

    const handleNodeClick = (node: any) => {
      const fg = fgRef.current
      if (!fg) return
      const framing = getClusterFraming(node.id, clickZoomDistance)
      if (framing) {
        fg.centerAt(framing.cx, framing.cy, 600)
        fg.zoom(framing.k, 600)
      }
      onNodeClick?.(node as NebulaNode)
    }

    return (
      <div
        ref={containerRef}
        className={cn(
          "relative touch-none select-none overscroll-none transition-opacity duration-300",
          !live && "pointer-events-none",
          className
        )}
        style={{ opacity: dimmed ? 0.35 : 1 }}
      >
        {w > 0 && h > 0 && (
          <ForceGraph2D
            ref={fgRef}
            width={w}
            height={h}
            graphData={data}
            backgroundColor="rgba(0,0,0,0)"
            minZoom={MIN_ZOOM}
            maxZoom={MAX_ZOOM}
            cooldownTicks={200}
            onEngineStop={fitWhole}
            nodeRelSize={nodeRelSize}
            nodeVal={(n: any) => nodeRenderVal(n, highlightedNodeIds)}
            nodeLabel={tooltipFn}
            nodeVisibility={(n: any) => {
              if (hiddenNodeIds?.has(n.id)) return false
              return n.__birthed !== false
            }}
            nodeColor={(n: any) => {
              if (isDimmed(n.id)) {
                return isLight ? "rgba(148,163,184,0.22)" : "rgba(100,116,139,0.18)"
              }
              return nebulaNodeColor(n, isLight, nodeSeparation, nodeVividness)
            }}
            nodeCanvasObjectMode={() => "after"}
            nodeCanvasObject={paintNodeLabel}
            linkVisibility={(l: any) => {
              const { srcId, tgtId } = linkEndsHidden(l)
              if (hiddenNodeIds?.has(srcId) || hiddenNodeIds?.has(tgtId)) return false
              const srcBirthed =
                typeof l.source === "object" ? l.source.__birthed !== false : true
              const tgtBirthed =
                typeof l.target === "object" ? l.target.__birthed !== false : true
              return srcBirthed && tgtBirthed
            }}
            linkColor={(l: any) => {
              const { srcId, tgtId } = linkEndsHidden(l)
              if (
                highlightedNodeIds &&
                (!highlightedNodeIds.has(srcId) || !highlightedNodeIds.has(tgtId))
              ) {
                return isLight ? "rgba(148,163,184,0.14)" : "rgba(148,163,184,0.06)"
              }
              return isLight ? "rgba(51,65,85,0.38)" : "rgba(203,213,225,0.22)"
            }}
            linkWidth={(l: any) => {
              const { srcId, tgtId } = linkEndsHidden(l)
              if (
                highlightedNodeIds &&
                (!highlightedNodeIds.has(srcId) || !highlightedNodeIds.has(tgtId))
              ) {
                return 0.25
              }
              return activeLinkWidth
            }}
            linkDirectionalArrowLength={showArrows ? 3.5 : 0}
            linkDirectionalArrowRelPos={0.98}
            linkDirectionalParticles={linkParticles}
            linkDirectionalParticleWidth={1.6}
            enableNodeDrag={live && !dimmed}
            enableZoomInteraction={live}
            enablePanInteraction={live}
            onNodeClick={handleNodeClick}
            onBackgroundClick={() => onBackgroundClick?.()}
          />
        )}
      </div>
    )
  }
)

KnowledgeNebula2D.displayName = "KnowledgeNebula2D"

export { KnowledgeNebula2D }
