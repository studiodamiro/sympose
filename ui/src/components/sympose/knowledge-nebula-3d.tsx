import * as React from "react"
import ForceGraph3D, {
  type ForceGraphMethods,
  type NodeObject,
} from "react-force-graph-3d"
import { forceRadial } from "d3-force-3d"
import SpriteText from "three-spritetext"

import { cn } from "@/lib/utils"
import {
  type NebulaGraph,
  type NebulaNode,
} from "@/lib/nebula-graph"
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
 * Camera-distance window over which in-scene node labels fade in — the 3D
 * analogue of the 2D renderer's zoom (`globalScale`) gate. Beyond `FAR` labels
 * are hidden; within `NEAR` they are fully opaque.
 */
const LABEL_FADE_NEAR = 110
const LABEL_FADE_FAR = 260

/**
 * Knowledge Nebula — 3D variant (wiki spec §2, ADR-051/052). A force-directed
 * WebGL cloud of the vault: notes are nodes coloured by folder and sized by
 * link degree, `[[wikilinks]]` are the edges. Paints a transparent background
 * so whatever sits behind it shows through. Reached through `<KnowledgeNebula>`
 * with `mode="3d"` (the default).
 */
const KnowledgeNebula3D = React.forwardRef<
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
      autoRotate = false,
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
    const animFrameRef = React.useRef<number | null>(null)
    const { w, h } = useElementSize(containerRef)
    const live = interactive ?? !dimmed

    // force-graph mutates the object it is handed (link source/target become node
    // refs, x/y/z get written). Clone so the caller's data — a JSON import module
    // singleton in the showcase — is never touched.
    const data = React.useMemo(() => {
      const cloned = structuredClone(graph) as NebulaGraph
      cloned.nodes.forEach((n: any) => {
        n.__scale = 1.0
      })
      return cloned
    }, [graph])

    const timerRef = React.useRef<any>(null)

    // --- In-scene node labels ----------------------------------------------
    // One SpriteText per node, kept in a map so a rAF loop can fade them by
    // camera distance (mirrors the 2D renderer's zoom-gated labels). Dynamic
    // inputs are read through refs so the `nodeThreeObject` accessor and the
    // loop stay identity-stable and never force a costly object rebuild.
    const labelSpritesRef = React.useRef<Map<string, SpriteText>>(new Map())
    const showLabelsRef = React.useRef(showLabels)
    const highlightedIdsRef = React.useRef(highlightedNodeIds)
    const hiddenIdsRef = React.useRef(hiddenNodeIds)
    const nodeRelSizeRef = React.useRef(nodeRelSize)
    const isLightRef = React.useRef(isLight)
    showLabelsRef.current = showLabels
    highlightedIdsRef.current = highlightedNodeIds
    hiddenIdsRef.current = hiddenNodeIds
    nodeRelSizeRef.current = nodeRelSize
    isLightRef.current = isLight

    const nodeById = React.useMemo(() => {
      const m = new Map<string, any>()
      ;(data.nodes as any[]).forEach((n) => m.set(n.id, n))
      return m
    }, [data])

    const buildNodeLabel = React.useCallback((node: any) => {
      const sprite = new SpriteText(String(node.label ?? node.id))
      sprite.textHeight = 3.5
      sprite.fontFace = "Inter Variable, system-ui, sans-serif"
      sprite.color = isLightRef.current ? "#0f172a" : "#e2e8f0"
      sprite.center.set(0.5, 1)
      sprite.material.transparent = true
      sprite.material.depthWrite = false
      sprite.material.opacity = 0
      sprite.visible = false
      sprite.renderOrder = 10
      labelSpritesRef.current.set(node.id, sprite)
      return sprite
    }, [])

    // Recolour existing sprites on theme change (setter regenerates the
    // texture, so only do it here — never per frame).
    React.useEffect(() => {
      const color = isLight ? "#0f172a" : "#e2e8f0"
      labelSpritesRef.current.forEach((sprite) => {
        sprite.color = color
      })
    }, [isLight])

    // Fade labels by camera distance every frame (three.js is already looping).
    React.useEffect(() => {
      let raf = 0
      const tick = () => {
        raf = requestAnimationFrame(tick)
        const fg = fgRef.current
        if (!fg) return
        const cam = fg.camera() as any
        if (!cam) return
        const { x: camX, y: camY, z: camZ } = cam.position
        const on = showLabelsRef.current
        const hi = highlightedIdsRef.current
        const hidden = hiddenIdsRef.current
        const rel = nodeRelSizeRef.current
        labelSpritesRef.current.forEach((sprite, id) => {
          const node = nodeById.get(id)
          if (
            !on ||
            !node ||
            node.__birthed === false ||
            hidden?.has(id) ||
            (hi && !hi.has(id))
          ) {
            if (sprite.visible) sprite.visible = false
            return
          }
          const dx = (node.x ?? 0) - camX
          const dy = (node.y ?? 0) - camY
          const dz = (node.z ?? 0) - camZ
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz)
          const opacity = clamp(
            (LABEL_FADE_FAR - dist) / (LABEL_FADE_FAR - LABEL_FADE_NEAR),
            0,
            1
          )
          if (opacity <= 0.02) {
            if (sprite.visible) sprite.visible = false
            return
          }
          sprite.visible = true
          sprite.material.opacity = opacity
          const r = Math.sqrt(Math.max(0, nodeRenderVal(node, hi))) * rel
          sprite.position.y = -(r + 2)
        })
      }
      raf = requestAnimationFrame(tick)
      return () => cancelAnimationFrame(raf)
    }, [nodeById])

    // Release sprite textures on unmount.
    React.useEffect(() => {
      const sprites = labelSpritesRef.current
      return () => {
        sprites.forEach((s: any) => {
          s.material?.map?.dispose?.()
          s.material?.dispose?.()
        })
        sprites.clear()
      }
    }, [])

    const getClusterFraming = (liveNode: any, zoomDist = clickZoomDistance) => {
      const nodeId = liveNode.id
      const clusterNodes: any[] = [liveNode]
      const clusterNodeIds = new Set<string>([nodeId])

      data.links.forEach((l: any) => {
        const srcId = typeof l.source === "object" ? l.source.id : l.source
        const tgtId = typeof l.target === "object" ? l.target.id : l.target
        if (srcId === nodeId && !clusterNodeIds.has(tgtId)) {
          const neighbor = (data.nodes as any[]).find((n) => n.id === tgtId)
          if (neighbor) {
            clusterNodes.push(neighbor)
            clusterNodeIds.add(tgtId)
          }
        }
        if (tgtId === nodeId && !clusterNodeIds.has(srcId)) {
          const neighbor = (data.nodes as any[]).find((n) => n.id === srcId)
          if (neighbor) {
            clusterNodes.push(neighbor)
            clusterNodeIds.add(srcId)
          }
        }
      })

      // Calculate Centroid (average X, Y, Z of the connected cluster)
      let sumX = 0, sumY = 0, sumZ = 0
      clusterNodes.forEach((n) => {
        sumX += n.x ?? 0
        sumY += n.y ?? 0
        sumZ += n.z ?? 0
      })
      const count = clusterNodes.length
      const cx = sumX / count
      const cy = sumY / count
      const cz = sumZ / count

      // Calculate cluster bounding radius
      let maxRadius = 15
      clusterNodes.forEach((n) => {
        const dx = (n.x ?? 0) - cx
        const dy = (n.y ?? 0) - cy
        const dz = (n.z ?? 0) - cz
        const r = Math.hypot(dx, dy, dz)
        if (r > maxRadius) maxRadius = r
      })

      // Scale camera distance to frame the entire cluster
      const knobFactor = zoomDist / 60
      const targetDistance = Math.max(35, (maxRadius * 2.2 + 25) * knobFactor)

      return {
        lookAt: { x: cx, y: cy, z: cz },
        cameraPos: { x: cx, y: cy, z: cz + targetDistance },
      }
    }

    React.useImperativeHandle(ref, () => ({
      zoomToFit: (duration = 600, padding = 48) => {
        const fg = fgRef.current
        if (!fg) return
        fg.zoomToFit(duration, padding)
        setTimeout(() => {
          const controls = fg.controls() as any
          if (controls) {
            controls.target.set(0, 0, 0)
            controls.enableZoom = true
            controls.enableRotate = true
            controls.enablePan = true
            controls.update()
          }
        }, duration + 60)
      },
      focusNode: (nodeOrId: NebulaNode | string, distance?: number, duration = 800) => {
        const fg = fgRef.current
        if (!fg) return
        const id = typeof nodeOrId === "string" ? nodeOrId : nodeOrId.id
        const liveNode = (data.nodes as any[]).find((n) => n.id === id)
        if (!liveNode) return

        const framing = getClusterFraming(liveNode, distance ?? clickZoomDistance)
        fg.cameraPosition(
          framing.cameraPos,
          framing.lookAt,
          duration
        )
        setTimeout(() => {
          const controls = fg.controls() as any
          if (controls) {
            controls.target.set(framing.lookAt.x, framing.lookAt.y, framing.lookAt.z)
            controls.enableZoom = true
            controls.enableRotate = true
            controls.enablePan = true
            controls.update()
          }
        }, duration + 60)
      },
      fitNodes: (nodeIds: string[] | Set<string>, duration = 800, padding = 40) => {
        const fg = fgRef.current
        if (!fg) return
        const idSet = new Set(nodeIds)
        const matching = (data.nodes as any[]).filter((n) => idSet.has(n.id))
        if (matching.length === 0) return

        // Compute Centroid of matching nodes
        let sumX = 0, sumY = 0, sumZ = 0
        matching.forEach((n) => {
          sumX += n.x ?? 0
          sumY += n.y ?? 0
          sumZ += n.z ?? 0
        })
        const count = matching.length
        const cx = sumX / count
        const cy = sumY / count
        const cz = sumZ / count

        // Compute max radius from centroid
        let maxRadius = 20
        matching.forEach((n) => {
          const dx = (n.x ?? 0) - cx
          const dy = (n.y ?? 0) - cy
          const dz = (n.z ?? 0) - cz
          const r = Math.hypot(dx, dy, dz)
          if (r > maxRadius) maxRadius = r
        })

        // Compute camera distance so matching nodes occupy ~75% of stage
        const targetDistance = Math.max(50, maxRadius * 2.2 + padding)

        fg.cameraPosition(
          { x: cx, y: cy, z: cz + targetDistance },
          { x: cx, y: cy, z: cz },
          duration
        )

        setTimeout(() => {
          const controls = fg.controls() as any
          if (controls) {
            controls.target.set(cx, cy, cz)
            controls.enableZoom = true
            controls.enableRotate = true
            controls.enablePan = true
            controls.update()
          }
        }, duration + 60)
      },
      animateBirth: (noteDelayMs = 25) => {
        const fg = fgRef.current
        if (!fg) return

        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        if (animFrameRef.current) {
          cancelAnimationFrame(animFrameRef.current)
          animFrameRef.current = null
        }

        const totalNodes = data.nodes.length
        if (totalNodes === 0) return

        // 1. Hide all nodes initially and randomize entry points
        data.nodes.forEach((n: any) => {
          n.x = (Math.random() - 0.5) * 450
          n.y = (Math.random() - 0.5) * 450
          n.z = (Math.random() - 0.5) * 450
          n.vx = (Math.random() - 0.5) * 6
          n.vy = (Math.random() - 0.5) * 6
          n.vz = (Math.random() - 0.5) * 6
          n.__scale = 0.0001
          n.__birthed = false
        })

        fg.d3ReheatSimulation()

        let currentIdx = 0

        // 2. Spawn notes ONE BY ONE with interval noteDelayMs
        timerRef.current = setInterval(() => {
          if (currentIdx < totalNodes) {
            const node = data.nodes[currentIdx] as any
            node.__birthed = true
            currentIdx++
            fg.refresh?.()
            fg.d3ReheatSimulation()
          } else {
            if (timerRef.current) {
              clearInterval(timerRef.current)
              timerRef.current = null
            }
            data.nodes.forEach((n: any) => {
              n.__birthed = true
            })
            fg.refresh?.()
            fg.d3ReheatSimulation()
          }
        }, Math.max(5, noteDelayMs))
      },
    }))

    // Tear down any in-flight birth animation when the component unmounts —
    // otherwise the setInterval keeps firing against a disposed renderer.
    React.useEffect(() => {
      return () => {
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        if (animFrameRef.current) {
          cancelAnimationFrame(animFrameRef.current)
          animFrameRef.current = null
        }
      }
    }, [])

    // Dynamic d3 force adjustments
    React.useEffect(() => {
      const fg = fgRef.current
      if (!fg) return
      if (centerForce !== undefined) {
        fg.d3Force("radial", forceRadial(0, 0, 0, 0).strength(centerForce * 0.8))
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

    // Pull the camera back so the first frame frames the whole cloud
    React.useEffect(() => {
      fgRef.current?.cameraPosition({ z: 360 })
    }, [])

    // Ambient orbit controls
    React.useEffect(() => {
      const controls = fgRef.current?.controls() as
        | { autoRotate: boolean; autoRotateSpeed: number; update: () => void }
        | undefined
      if (!controls) return

      const shouldRotate = autoRotate || dimmed
      controls.autoRotate = shouldRotate
      controls.autoRotateSpeed = 1.2

      let rotateFrameId: number | null = null

      if (shouldRotate) {
        const loop = () => {
          controls.update()
          rotateFrameId = requestAnimationFrame(loop)
        }
        rotateFrameId = requestAnimationFrame(loop)
      }

      return () => {
        if (rotateFrameId) cancelAnimationFrame(rotateFrameId)
        if (controls) controls.autoRotate = false
      }
    }, [autoRotate, dimmed])

    // Configure controls for touch and mouse wheel zooming
    React.useEffect(() => {
      const setupControls = () => {
        const controls = fgRef.current?.controls() as any
        if (!controls) return false
        controls.enableZoom = true
        controls.enablePan = true
        controls.enableRotate = true
        controls.minDistance = 5
        controls.maxDistance = 5000
        controls.zoomSpeed = 1.2
        return true
      }

      if (!setupControls()) {
        const timer = setInterval(() => {
          if (setupControls()) clearInterval(timer)
        }, 100)
        return () => clearInterval(timer)
      }
    }, [])

    const tooltipFn = React.useMemo(() => createNodeTooltip(isLight), [isLight])
    const defaultLinkWidth = isLight ? 0.8 : 0.6
    const activeLinkWidth = linkWidth ?? defaultLinkWidth

    const nodeClickedRef = React.useRef(false)
    const pointerDownPosRef = React.useRef<{ x: number; y: number } | null>(null)

    const handleNodeClick = (node: NodeObject) => {
      nodeClickedRef.current = true
      const fg = fgRef.current
      if (!fg) return
      const n = node as any
      const framing = getClusterFraming(n, clickZoomDistance)

      fg.cameraPosition(
        framing.cameraPos,
        framing.lookAt,
        800
      )
      setTimeout(() => {
        const controls = fg.controls() as any
        if (controls) {
          controls.target.set(framing.lookAt.x, framing.lookAt.y, framing.lookAt.z)
          controls.enableZoom = true
          controls.update()
        }
      }, 860)
      onNodeClick?.(n as NebulaNode)
    }

    const handlePointerDown = (e: React.PointerEvent) => {
      pointerDownPosRef.current = { x: e.clientX, y: e.clientY }
    }

    const handlePointerUp = (e: React.PointerEvent) => {
      if (!pointerDownPosRef.current) return
      const dx = Math.abs(e.clientX - pointerDownPosRef.current.x)
      const dy = Math.abs(e.clientY - pointerDownPosRef.current.y)
      pointerDownPosRef.current = null

      // If pointer moved less than 6px, treat as a clean empty-space tap/click
      if (dx < 6 && dy < 6) {
        setTimeout(() => {
          if (!nodeClickedRef.current) {
            onBackgroundClick?.()
          }
          nodeClickedRef.current = false
        }, 40)
      }
    }

    return (
      <div
        ref={containerRef}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        className={cn(
          "relative touch-none select-none overscroll-none transition-opacity duration-300",
          !live && "pointer-events-none",
          className
        )}
        style={{ opacity: dimmed ? 0.35 : 1 }}
      >
        {w > 0 && h > 0 && (
          <ForceGraph3D
            ref={fgRef}
            width={w}
            height={h}
            graphData={data}
            backgroundColor="rgba(0,0,0,0)"
            showNavInfo={false}
            nodeVisibility={(n: NodeObject) => {
              const node = n as NebulaNode
              if (hiddenNodeIds?.has(node.id)) return false
              return (node as any).__birthed !== false
            }}
            linkVisibility={(l: any) => {
              const srcId = typeof l.source === "object" ? l.source.id : l.source
              const tgtId = typeof l.target === "object" ? l.target.id : l.target
              if (hiddenNodeIds?.has(srcId) || hiddenNodeIds?.has(tgtId)) return false
              const srcBirthed = typeof l.source === "object" ? l.source.__birthed !== false : true
              const tgtBirthed = typeof l.target === "object" ? l.target.__birthed !== false : true
              return srcBirthed && tgtBirthed
            }}
            nodeRelSize={nodeRelSize}
            nodeResolution={16}
            nodeOpacity={0.95}
            nodeVal={(n: NodeObject) => nodeRenderVal(n, highlightedNodeIds)}
            nodeColor={(n: NodeObject) => {
              const node = n as NebulaNode
              if (highlightedNodeIds && !highlightedNodeIds.has(node.id)) {
                return isLight ? "rgba(148,163,184,0.18)" : "rgba(100,116,139,0.15)"
              }
              return nebulaNodeColor(node, isLight, nodeSeparation, nodeVividness)
            }}
            nodeLabel={tooltipFn}
            nodeThreeObjectExtend={true}
            nodeThreeObject={buildNodeLabel}
            linkColor={(l: any) => {
              const srcId = typeof l.source === "object" ? l.source.id : l.source
              const tgtId = typeof l.target === "object" ? l.target.id : l.target
              if (highlightedNodeIds && (!highlightedNodeIds.has(srcId) || !highlightedNodeIds.has(tgtId))) {
                return isLight ? "rgba(203,213,225,0.06)" : "rgba(255,255,255,0.02)"
              }
              return isLight ? "rgba(51,65,85,0.70)" : "rgba(203,213,225,0.65)"
            }}
            linkWidth={(l: any) => {
              const srcId = typeof l.source === "object" ? l.source.id : l.source
              const tgtId = typeof l.target === "object" ? l.target.id : l.target
              if (highlightedNodeIds && (!highlightedNodeIds.has(srcId) || !highlightedNodeIds.has(tgtId))) {
                return 0.1
              }
              return activeLinkWidth
            }}
            linkDirectionalArrowLength={showArrows ? 5 : 0}
            linkDirectionalArrowRelPos={0.95}
            linkDirectionalParticles={linkParticles}
            linkDirectionalParticleWidth={1.6}
            linkDirectionalParticleSpeed={0.006}
            enableNodeDrag={live && !dimmed}
            enableNavigationControls={live}
            cooldownTicks={200}
            onNodeClick={handleNodeClick}
            onBackgroundClick={onBackgroundClick}
          />
        )}
      </div>
    )
  }
)

KnowledgeNebula3D.displayName = "KnowledgeNebula3D"

export { KnowledgeNebula3D }
