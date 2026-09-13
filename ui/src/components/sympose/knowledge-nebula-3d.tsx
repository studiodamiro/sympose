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
  lerpNodeColor,
  nebulaNodeColor,
  nodeRenderVal,
  stepHighlightT,
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
 * Minimum gap between `d3ReheatSimulation()` calls during `animateBirth` —
 * see the identical constant in `knowledge-nebula-2d.tsx` for why: reheating
 * resets `alpha` to 1 every time, so calling it on every single note reveal
 * never lets alpha decay and the whole graph shakes for the entire sequence
 * instead of settling.
 */
const BIRTH_REHEAT_INTERVAL_MS = 300
/** Matches the `nodeOpacity` prop passed to `<ForceGraph3D>` below — kept as
 *  one constant since the per-frame colour loop (ADR-117) has to reproduce
 *  the same `nodeOpacity * colorAlpha(color)` multiply the library itself
 *  does, outside the library's own digest. */
const NODE_OPACITY = 0.95
/**
 * Degrees of orbiting "spin" (see `flyCameraTo`'s `spinDeg` param) applied to
 * click-driven camera flights, by call site — 0 for all of them (ADR-118).
 *
 * The mechanism has a real bug, not just a feel problem: at the flight's very
 * first frame (t=0), `remaining` (in `flyCameraTo`) evaluates to the *full*
 * spin angle, which then gets applied by rotating the camera's actual current
 * position around the look-at point immediately — so frame one is a
 * discontinuous jump to a rotated copy of wherever the camera already was,
 * not a continuation from it, and the rotation only eases back to 0 (the
 * true starting point) as the flight proceeds. That's what read as "the
 * frame suddenly jerks to a random position and then the animation starts" —
 * confirmed by a side-by-side test (spin on vs. isolated off; only removing
 * spin fixed it). Fixing this properly means easing `remaining` in from 0 at
 * t=0 (not out to 0 at t=1) so the flight actually starts at the real
 * position; until that's done, leave this at 0 rather than re-tune the angle.
 */
const CLICK_SPIN_DEG = 0
const BACKGROUND_SPIN_DEG = 0
/** Flat colour a dimmed (non-highlighted) node eases toward/from — `t=0` endpoint of `lerpNodeColor`. */
const DIMMED_RGB_LIGHT = [148, 163, 184] as const
const DIMMED_RGB_DARK = [100, 116, 139] as const
const DIMMED_ALPHA_LIGHT = 0.18
const DIMMED_ALPHA_DARK = 0.15

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
    const flightRafRef = React.useRef<number | null>(null)
    const pendingFlightTimeoutRef = React.useRef<number | null>(null)
    const { w, h } = useElementSize(containerRef)
    const live = interactive ?? !dimmed

    // force-graph mutates the object it is handed (link source/target become node
    // refs, x/y/z get written). Clone so the caller's data — a JSON import module
    // singleton in the showcase — is never touched.
    const data = React.useMemo(() => {
      const cloned = structuredClone(graph) as NebulaGraph
      cloned.nodes.forEach((n: any) => {
        n.__scale = 1.0
        n.__highlightT = 1
      })
      return cloned
    }, [graph])

    const timerRef = React.useRef<any>(null)
    const lastReheatRef = React.useRef(0)

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
    const nodeSeparationRef = React.useRef(nodeSeparation)
    const nodeVividnessRef = React.useRef(nodeVividness)
    showLabelsRef.current = showLabels
    highlightedIdsRef.current = highlightedNodeIds
    hiddenIdsRef.current = hiddenNodeIds
    nodeRelSizeRef.current = nodeRelSize
    isLightRef.current = isLight
    nodeSeparationRef.current = nodeSeparation
    nodeVividnessRef.current = nodeVividness

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
    // Piggybacks the highlight/dim colour-transition step on the same loop.
    //
    // ADR-116/117: three-forcegraph does not re-evaluate `nodeColor` just
    // because `__highlightT` changed underneath it — the first fix for that
    // was calling `fg.refresh()`, its own hook for "something changed outside
    // your props, redraw." That worked, but `refresh()` re-digests *every*
    // node and link and rebuilds any material that differs from what's
    // currently assigned — since colours ease continuously, virtually every
    // node differs on virtually every frame, so it was rebuilding ~900+
    // materials from scratch up to 60 times a second, which is what was
    // actually stuttering. A throttle on how often refresh() ran made it
    // marginally better but each still-heavy call was still a visible hitch,
    // just a sparser one.
    //
    // The fix: skip the library's digest for colour entirely. Each node's
    // default sphere mesh (`node.__threeObj`) already carries a live
    // MeshLambertMaterial once three-forcegraph has created it — clone it
    // once per node (so we're never mutating an instance shared with other
    // nodes at the same resting colour) and from then on just write
    // `.color`/`.opacity` on it directly every frame. That's a couple of
    // cheap property writes per node, no allocation, no digest, and three.js
    // picks it up on its next render regardless — no refresh() call needed.
    React.useEffect(() => {
      let raf = 0
      let last = performance.now()
      const tick = () => {
        raf = requestAnimationFrame(tick)
        const now = performance.now()
        const dt = now - last
        last = now
        const hiForColor = highlightedIdsRef.current
        const light = isLightRef.current
        const dimmedRgb = light ? DIMMED_RGB_LIGHT : DIMMED_RGB_DARK
        const dimmedAlpha = light ? DIMMED_ALPHA_LIGHT : DIMMED_ALPHA_DARK
        const separation = nodeSeparationRef.current
        const vividness = nodeVividnessRef.current
        nodeById.forEach((node: any) => {
          const target = !hiForColor || hiForColor.has(node.id) ? 1 : 0
          const stillEasing = stepHighlightT(node, target, dt)

          const obj = node.__threeObj
          const material = obj?.material
          if (!material) return
          // A node that's already settled and already has its own private
          // material has nothing new to paint — recomputing and rewriting
          // its colour every single frame forever (not just while it's
          // actually transitioning) was the remaining per-frame cost that
          // kept this stuttery even after the digest fix. Only nodes still
          // easing, or ones we've never touched yet (first paint), do any
          // work here.
          if (!stillEasing && material.__owned) return
          if (!material.__owned) {
            obj.material = material.clone()
            obj.material.__owned = true
          }

          const t = clamp(node.__highlightT ?? 1, 0, 1)
          const fullHex = nebulaNodeColor(node, light, separation, vividness)
          const fr = parseInt(fullHex.slice(1, 3), 16)
          const fFg = parseInt(fullHex.slice(3, 5), 16)
          const fb = parseInt(fullHex.slice(5, 7), 16)
          const [dr, dg, db] = dimmedRgb
          const r = Math.round(dr + (fr - dr) * t)
          const g = Math.round(dg + (fFg - dg) * t)
          const b = Math.round(db + (fb - db) * t)
          const a = dimmedAlpha + (1 - dimmedAlpha) * t

          obj.material.color.setHex((r << 16) | (g << 8) | b)
          obj.material.opacity = NODE_OPACITY * a
        })

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

    // Unit vector from the current orbit target toward the current camera —
    // i.e. the direction the camera is presently looking from. Placing a new
    // camera position along this same direction (just at a different
    // distance) dollies the view toward/away from the new target while
    // preserving whatever angle you've orbited to; hardcoding +Z here instead
    // would snap the camera back to a fixed compass heading on every click,
    // producing a jarring swoop any time you're not already looking from +Z.
    // Falls back to +Z before the first render, when there's no camera pose yet.
    const getViewDirection = () => {
      const fg = fgRef.current
      const cam = fg?.camera() as any
      const controls = fg?.controls() as any
      if (!cam || !controls?.target) return { x: 0, y: 0, z: 1 }
      const dx = cam.position.x - controls.target.x
      const dy = cam.position.y - controls.target.y
      const dz = cam.position.z - controls.target.z
      const len = Math.hypot(dx, dy, dz)
      if (len < 1e-6) return { x: 0, y: 0, z: 1 }
      return { x: dx / len, y: dy / len, z: dz / len }
    }

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
      const dir = getViewDirection()

      return {
        lookAt: { x: cx, y: cy, z: cz },
        cameraPos: {
          x: cx + dir.x * targetDistance,
          y: cy + dir.y * targetDistance,
          z: cz + dir.z * targetDistance,
        },
      }
    }

    // Drives camera position AND the orbit-controls look-at target from a
    // single rAF loop on one shared clock. `fg.cameraPosition(pos, lookAt,
    // duration)` looks like it would do this, but the underlying 3d-force-graph
    // library runs them as two *independent* tweens — position over the full
    // duration, look-at over just the first third of it — so the pivot point
    // arrives and sits still while the camera keeps gliding in behind it. That
    // mismatch is what read as a "clunky" click-zoom; syncing both here is the
    // fix.
    const flyCameraTo = React.useCallback(
      (
        cameraPos: { x: number; y: number; z: number },
        lookAt: { x: number; y: number; z: number },
        duration: number,
        spinDeg = 0,
        autoRotateOverride?: boolean
      ) => {
        const fg = fgRef.current
        const cam = fg?.camera() as any
        const controls = fg?.controls() as any
        if (!cam || !controls?.target) return

        if (flightRafRef.current) {
          cancelAnimationFrame(flightRafRef.current)
          flightRafRef.current = null
        }

        const startPos = { x: cam.position.x, y: cam.position.y, z: cam.position.z }
        const startLookAt = { x: controls.target.x, y: controls.target.y, z: controls.target.z }
        const startTime = performance.now()
        // `easeOutQuad` (t*(2-t)) has a non-zero derivative at t=0 — the
        // camera would jump to near-max velocity the instant the flight
        // starts. That's invisible on its own, but now that the colour fade
        // gets a couple hundred stationary milliseconds before the flight
        // begins (ADR-118), that abrupt onset of motion right after a still
        // period reads as a second, separate animation kicking in rather
        // than one continuous motion. Ease in *and* out so velocity starts
        // and ends at zero.
        const easeInOutQuad = (t: number) =>
          t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2

        // Ambient auto-rotate (see the effect below) nudges controls.target's
        // azimuth on its own rAF loop independent of enableRotate — left
        // running, it fights this flight the same way the library's own
        // mismatched tweens did. Pause it and restore whatever it was after.
        // `autoRotateOverride` lets `scheduleFlyCameraTo` hand in a value it
        // captured earlier, at click time, rather than reading it fresh here
        // — see that function for why.
        const wasAutoRotating = autoRotateOverride ?? controls.autoRotate
        controls.autoRotate = false
        controls.enableZoom = false
        controls.enableRotate = false
        controls.enablePan = false

        // Scale the spin by how far the camera is actually travelling — a
        // fixed angle regardless of distance means clicking void again once
        // you're already at the zoomed-out framing (nothing left to travel)
        // still swings through the full spin for no navigational reason,
        // which is what read as "jerking"/repeating identically on repeated
        // clicks. TRAVEL_FOR_FULL_SPIN is the distance at or beyond which the
        // full spinDeg applies; closer than that it tapers toward 0.
        const travelDist = Math.hypot(
          cameraPos.x - startPos.x,
          cameraPos.y - startPos.y,
          cameraPos.z - startPos.z
        )
        const TRAVEL_FOR_FULL_SPIN = 60
        const spinScale = Math.min(1, travelDist / TRAVEL_FOR_FULL_SPIN)
        const spinRad = (spinDeg * spinScale * Math.PI) / 180

        const tick = () => {
          const t = duration <= 0 ? 1 : Math.min(1, (performance.now() - startTime) / duration)
          const eased = easeInOutQuad(t)

          const lookX = startLookAt.x + (lookAt.x - startLookAt.x) * eased
          const lookY = startLookAt.y + (lookAt.y - startLookAt.y) * eased
          const lookZ = startLookAt.z + (lookAt.z - startLookAt.z) * eased

          let posX = startPos.x + (cameraPos.x - startPos.x) * eased
          let posY = startPos.y + (cameraPos.y - startPos.y) * eased
          let posZ = startPos.z + (cameraPos.z - startPos.z) * eased

          // A straight-line camera move reads exactly like the 2D renderer's
          // flat pan/zoom — no parallax gives away that this is a 3D scene.
          // Orbiting the camera around the look-at point on top of the linear
          // move, with the orbit angle decaying from `spinDeg` down to 0 as
          // the flight completes, curls the path into a spin that still lands
          // exactly on the intended framing (0 remaining spin at t=1).
          if (spinRad) {
            const remaining = spinRad * (1 - eased)
            const dx = posX - lookX
            const dz = posZ - lookZ
            const cos = Math.cos(remaining)
            const sin = Math.sin(remaining)
            posX = lookX + dx * cos - dz * sin
            posZ = lookZ + dx * sin + dz * cos
          }

          cam.position.set(posX, posY, posZ)
          controls.target.set(lookX, lookY, lookZ)
          controls.update()

          if (t < 1) {
            flightRafRef.current = requestAnimationFrame(tick)
          } else {
            controls.enableZoom = true
            controls.enableRotate = true
            controls.enablePan = true
            controls.autoRotate = wasAutoRotating
            flightRafRef.current = null
          }
        }
        tick()
      },
      []
    )

    // Click and background-click both fire the highlight/dim change and the
    // camera flight in the same instant, so the colour fade — which is what
    // actually tells you what you clicked — gets buried under a bigger motion
    // happening at the same time and reads as an abrupt snap. Giving the
    // colour change a head start before the camera moves lets it register on
    // its own first. Routed through one cancellable scheduler so a second
    // click before the delay elapses replaces the pending flight rather than
    // stacking two.
    const CLICK_ZOOM_LEAD_MS = 220
    const scheduleFlyCameraTo = React.useCallback(
      (
        cameraPos: { x: number; y: number; z: number },
        lookAt: { x: number; y: number; z: number },
        duration: number,
        spinDeg: number,
        delayMs: number
      ) => {
        if (pendingFlightTimeoutRef.current !== null) {
          window.clearTimeout(pendingFlightTimeoutRef.current)
          pendingFlightTimeoutRef.current = null
        }
        if (delayMs <= 0) {
          flyCameraTo(cameraPos, lookAt, duration, spinDeg)
          return
        }

        // Lock the camera down the instant this is called, not only once the
        // delayed flight itself starts — `flyCameraTo` disabling the controls
        // only when it runs left them fully live for the whole delay, so any
        // residual pointer motion right after the click (the mouse hasn't
        // necessarily gone perfectly still) could nudge the camera during
        // what's supposed to be the colour fade's still period, and the
        // flight would then start from that nudged position instead of
        // where the click actually left things.
        const controls = fgRef.current?.controls() as any
        let wasAutoRotating = false
        if (controls) {
          wasAutoRotating = controls.autoRotate
          controls.autoRotate = false
          controls.enableZoom = false
          controls.enableRotate = false
          controls.enablePan = false
        }

        pendingFlightTimeoutRef.current = window.setTimeout(() => {
          pendingFlightTimeoutRef.current = null
          flyCameraTo(cameraPos, lookAt, duration, spinDeg, wasAutoRotating)
        }, delayMs)
      },
      [flyCameraTo]
    )

    React.useEffect(
      () => () => {
        if (pendingFlightTimeoutRef.current !== null) {
          window.clearTimeout(pendingFlightTimeoutRef.current)
        }
      },
      []
    )

    // Shared by `zoomToFit` and `fitNodes` below: centre + bounding radius of
    // an arbitrary node set, then fly the camera to frame it. `spinDeg` gets
    // an opposite sign from the node-click zoom-in's so zooming out reads as
    // twisting the other way — a deliberate little "in vs. out" distinction.
    const frameAndFly = (
      nodes: any[],
      padding: number,
      duration: number,
      spinDeg: number,
      delayMs = 0
    ) => {
      if (nodes.length === 0) return
      let sumX = 0, sumY = 0, sumZ = 0
      nodes.forEach((n) => {
        sumX += n.x ?? 0
        sumY += n.y ?? 0
        sumZ += n.z ?? 0
      })
      const cx = sumX / nodes.length
      const cy = sumY / nodes.length
      const cz = sumZ / nodes.length

      let maxRadius = 20
      nodes.forEach((n) => {
        const dx = (n.x ?? 0) - cx
        const dy = (n.y ?? 0) - cy
        const dz = (n.z ?? 0) - cz
        const r = Math.hypot(dx, dy, dz)
        if (r > maxRadius) maxRadius = r
      })

      const targetDistance = Math.max(50, maxRadius * 2.2 + padding)
      const dir = getViewDirection()

      scheduleFlyCameraTo(
        {
          x: cx + dir.x * targetDistance,
          y: cy + dir.y * targetDistance,
          z: cz + dir.z * targetDistance,
        },
        { x: cx, y: cy, z: cz },
        duration,
        spinDeg,
        delayMs
      )
    }

    React.useImperativeHandle(ref, () => ({
      zoomToFit: (duration = 600, padding = 48) => {
        frameAndFly(data.nodes as any[], padding, duration, BACKGROUND_SPIN_DEG, CLICK_ZOOM_LEAD_MS)
      },
      focusNode: (nodeOrId: NebulaNode | string, distance?: number, duration = 800) => {
        const fg = fgRef.current
        if (!fg) return
        const id = typeof nodeOrId === "string" ? nodeOrId : nodeOrId.id
        const liveNode = (data.nodes as any[]).find((n) => n.id === id)
        if (!liveNode) return

        const framing = getClusterFraming(liveNode, distance ?? clickZoomDistance)
        flyCameraTo(framing.cameraPos, framing.lookAt, duration, 40)
      },
      fitNodes: (nodeIds: string[] | Set<string>, duration = 800, padding = 40) => {
        const idSet = new Set(nodeIds)
        const matching = (data.nodes as any[]).filter((n) => idSet.has(n.id))
        frameAndFly(matching, padding, duration, CLICK_SPIN_DEG)
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
        lastReheatRef.current = Date.now()

        let currentIdx = 0

        // 2. Spawn notes ONE BY ONE with interval noteDelayMs
        timerRef.current = setInterval(() => {
          if (currentIdx < totalNodes) {
            const node = data.nodes[currentIdx] as any
            node.__birthed = true
            currentIdx++
            fg.refresh?.()
            const now = Date.now()
            if (now - lastReheatRef.current >= BIRTH_REHEAT_INTERVAL_MS) {
              fg.d3ReheatSimulation()
              lastReheatRef.current = now
            }
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
        if (flightRafRef.current) {
          cancelAnimationFrame(flightRafRef.current)
          flightRafRef.current = null
        }
      }
    }, [])

    // The 3D graph only mounts once the container has a measured size (see the
    // `w > 0 && h > 0` gate below), which happens a render or two after this
    // component's first pass. A ref becoming non-null doesn't retrigger effects,
    // so without `graphMounted` in the deps below, this effect would run once
    // against `fgRef.current === undefined` and never again — leaving the graph
    // on three-forcegraph's stock default forces until a slider is touched.
    const graphMounted = w > 0 && h > 0

    // Dynamic d3 force adjustments
    React.useEffect(() => {
      const fg = fgRef.current
      if (!fg) return
      // three-forcegraph wires an unconditional forceCenter(0,0,0) (strength 1)
      // into every simulation by default — it isn't a spring, it hard-recenters
      // the graph's centroid to the origin every tick regardless of any other
      // force. Left in place, "Center force" at 0 still can't let the graph
      // drift/sprawl the way Obsidian's does, because this default is still
      // fully clamping it underneath. The `radial` force below is the only
      // centering force the slider should control, so null this one out.
      fg.d3Force("center", null)
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
    }, [repelForce, linkDistance, linkForce, centerForce, graphMounted])

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

      const shouldRotate = autoRotate
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
    const activeLinkWidthRef = React.useRef(activeLinkWidth)
    activeLinkWidthRef.current = activeLinkWidth

    const handleNodeClick = (node: NodeObject) => {
      const fg = fgRef.current
      if (!fg) return
      const n = node as any
      const framing = getClusterFraming(n, clickZoomDistance)
      // Fire the highlight change first (synchronously, so the very next
      // paint already has it in flight) and only schedule the camera flight
      // after CLICK_ZOOM_LEAD_MS — see the comment on `scheduleFlyCameraTo`.
      onNodeClick?.(n as NebulaNode)
      scheduleFlyCameraTo(framing.cameraPos, framing.lookAt, 800, CLICK_SPIN_DEG, CLICK_ZOOM_LEAD_MS)
    }

    // Every one of these is read through refs and kept at a stable identity
    // (see the comment on the label refs above for why): three-forcegraph
    // treats a *changed function reference* as "the underlying data changed"
    // and reruns a full node/link material rebuild in response — so an inline
    // arrow here would silently force that full rebuild on every unrelated
    // React re-render (e.g. every click, since `highlightedNodeIds` changes),
    // stacking on top of the rAF loop's own deliberate `fg.refresh()` calls
    // during the highlight fade. Keeping these stable means the *only*
    // trigger for a rebuild is that explicit refresh.
    const nodeVisibilityFn = React.useCallback((n: NodeObject) => {
      const node = n as NebulaNode
      if (hiddenIdsRef.current?.has(node.id)) return false
      return (node as any).__birthed !== false
    }, [])
    const linkVisibilityFn = React.useCallback((l: any) => {
      const srcId = typeof l.source === "object" ? l.source.id : l.source
      const tgtId = typeof l.target === "object" ? l.target.id : l.target
      if (hiddenIdsRef.current?.has(srcId) || hiddenIdsRef.current?.has(tgtId)) return false
      const srcBirthed = typeof l.source === "object" ? l.source.__birthed !== false : true
      const tgtBirthed = typeof l.target === "object" ? l.target.__birthed !== false : true
      return srcBirthed && tgtBirthed
    }, [])
    const nodeValFn = React.useCallback(
      (n: NodeObject) => nodeRenderVal(n, highlightedIdsRef.current),
      []
    )
    const nodeColorFn = React.useCallback((n: NodeObject) => {
      const node = n as any
      const t = node.__highlightT ?? 1
      const light = isLightRef.current
      const dimmedRgb = light ? DIMMED_RGB_LIGHT : DIMMED_RGB_DARK
      const dimmedAlpha = light ? DIMMED_ALPHA_LIGHT : DIMMED_ALPHA_DARK
      if (t <= 0) return `rgba(${dimmedRgb.join(",")},${dimmedAlpha})`
      const full = nebulaNodeColor(node, light, nodeSeparationRef.current, nodeVividnessRef.current)
      if (t >= 1) return full
      return lerpNodeColor(t, full, dimmedRgb, dimmedAlpha)
    }, [])
    const linkColorFn = React.useCallback((l: any) => {
      const srcId = typeof l.source === "object" ? l.source.id : l.source
      const tgtId = typeof l.target === "object" ? l.target.id : l.target
      const hi = highlightedIdsRef.current
      if (hi && (!hi.has(srcId) || !hi.has(tgtId))) {
        return isLightRef.current ? "rgba(203,213,225,0.06)" : "rgba(255,255,255,0.02)"
      }
      return isLightRef.current ? "rgba(51,65,85,0.70)" : "rgba(203,213,225,0.65)"
    }, [])
    const linkWidthFn = React.useCallback((l: any) => {
      const srcId = typeof l.source === "object" ? l.source.id : l.source
      const tgtId = typeof l.target === "object" ? l.target.id : l.target
      const hi = highlightedIdsRef.current
      if (hi && (!hi.has(srcId) || !hi.has(tgtId))) return 0.1
      return activeLinkWidthRef.current
    }, [])

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
          <ForceGraph3D
            ref={fgRef}
            width={w}
            height={h}
            graphData={data}
            backgroundColor="rgba(0,0,0,0)"
            showNavInfo={false}
            nodeVisibility={nodeVisibilityFn}
            linkVisibility={linkVisibilityFn}
            nodeRelSize={nodeRelSize}
            nodeResolution={16}
            nodeOpacity={NODE_OPACITY}
            nodeVal={nodeValFn}
            nodeColor={nodeColorFn}
            nodeLabel={tooltipFn}
            nodeThreeObjectExtend={true}
            nodeThreeObject={buildNodeLabel}
            linkColor={linkColorFn}
            linkWidth={linkWidthFn}
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
