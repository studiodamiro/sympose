import * as React from "react"
import { Link } from "react-router-dom"

import {
  KnowledgeNebula,
  type KnowledgeNebulaHandle,
} from "@/components/sympose/knowledge-nebula"
import {
  FOLDER_COLORS,
  FOLDER_COLORS_LIGHT,
  foldersInGraph,
  type NebulaGraph,
} from "@/lib/nebula-graph"
import rawGraph from "@/lib/mock-nebula.json"

// Master graph with all notes and tag hubs pre-indexed for zero-reset stable rendering
const masterGraph: NebulaGraph = (() => {
  const rawNodes = rawGraph.nodes as any[]
  const rawLinks = rawGraph.links as any[]

  const tagMap = new Map<string, number>()
  rawNodes.forEach((n) => {
    if (n.tags) {
      n.tags.forEach((t: string) => {
        const clean = t.trim()
        if (clean) tagMap.set(clean, (tagMap.get(clean) || 0) + 1)
      })
    }
  })

  const tagNodes: typeof rawNodes = []
  const tagLinks: typeof rawLinks = []

  tagMap.forEach((count, t) => {
    tagNodes.push({
      id: `tag:${t}`,
      label: `#${t}`,
      folder: "Tags",
      tags: [t],
      isTag: true,
      val: Math.min(8, 2.5 + count * 0.4),
      exists: true,
    })
  })

  rawNodes.forEach((n) => {
    if (n.tags) {
      n.tags.forEach((t: string) => {
        const clean = t.trim()
        if (clean && tagMap.has(clean)) {
          tagLinks.push({
            source: n.id,
            target: `tag:${clean}`,
          })
        }
      })
    }
  })

  return {
    nodes: [...rawNodes, ...tagNodes],
    links: [...rawLinks, ...tagLinks],
  }
})()

export function NebulaShowcase() {
  const nebulaRef = React.useRef<KnowledgeNebulaHandle>(null)

  // Theme & Dock state
  const [theme, setTheme] = React.useState<"dark" | "light">("dark")
  const [controlsOpen, setControlsOpen] = React.useState(true)
  const isLight = theme === "light"

  // Accordion Sections State
  const [filtersOpen, setFiltersOpen] = React.useState(true)
  const [groupsOpen, setGroupsOpen] = React.useState(false)
  const [displayOpen, setDisplayOpen] = React.useState(true)
  const [forcesOpen, setForcesOpen] = React.useState(true)

  // Filters State
  const [searchQuery, setSearchQuery] = React.useState("")
  const [showTags, setShowTags] = React.useState(true)
  const [showAttachments, setShowAttachments] = React.useState(false)
  const [existingOnly, setExistingOnly] = React.useState(false)
  const [showOrphans, setShowOrphans] = React.useState(false) // default false = dim orphans

  // Groups State
  const [customGroups, setCustomGroups] = React.useState<{ id: string; query: string; color: string }[]>([])

  // Display State
  const [showArrows, setShowArrows] = React.useState(false)
  const [autoRotate, setAutoRotate] = React.useState(false)
  const [textFadeThreshold, setTextFadeThreshold] = React.useState(0.00)
  const [nodeRelSize, setNodeRelSize] = React.useState(1.67 * 2.4)
  const [linkWidth, setLinkWidth] = React.useState(0.8)
  const [noteDelayMs, setNoteDelayMs] = React.useState(25)
  const [clickZoomDistance, setClickZoomDistance] = React.useState(60)
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null)

  // Forces State
  const [centerForce, setCenterForce] = React.useState(0.52)
  const [repelForce, setRepelForce] = React.useState(13.89)
  const [linkForce, setLinkForce] = React.useState(1.00)
  const [linkDistance, setLinkDistance] = React.useState(492)

  // Reset to default settings
  const handleResetDefaults = () => {
    setSearchQuery("")
    setShowTags(true)
    setShowAttachments(false)
    setExistingOnly(false)
    setShowOrphans(false)
    setShowArrows(false)
    setAutoRotate(false)
    setTextFadeThreshold(0.00)
    setNodeRelSize(4.0)
    setLinkWidth(0.8)
    setNoteDelayMs(25)
    setClickZoomDistance(60)
    setSelectedNodeId(null)
    setCenterForce(0.52)
    setRepelForce(13.89)
    setLinkForce(1.00)
    setLinkDistance(492)
    nebulaRef.current?.zoomToFit()
  }

  // Calculate highlighted and hidden nodes without resetting the 3D graph stage
  const { highlightedNodeIds, hiddenNodeIds, activeCount } = React.useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    const hidden = new Set<string>()
    let highlighted = new Set<string>()

    const connectedNodeIds = new Set<string>()
    masterGraph.links.forEach((l) => {
      const src = typeof l.source === "string" ? l.source : (l.source as any).id
      const tgt = typeof l.target === "string" ? l.target : (l.target as any).id
      const isTagLink = src.startsWith("tag:") || tgt.startsWith("tag:")
      if (!isTagLink || showTags) {
        connectedNodeIds.add(src)
        connectedNodeIds.add(tgt)
      }
    })

    masterGraph.nodes.forEach((n) => {
      // 1. Tag node visibility
      if (n.isTag && !showTags) {
        hidden.add(n.id)
        return
      }

      // 2. Attachments filter
      if (!showAttachments && n.id.match(/\.(png|jpg|jpeg|gif|svg|pdf|mp4|webm)$/i)) {
        hidden.add(n.id)
        return
      }

      // 3. Existing files filter
      if (existingOnly && n.exists === false) {
        hidden.add(n.id)
        return
      }

      // 4. Orphan check: if showOrphans is false and node has no connections, fade it
      const isConnected = connectedNodeIds.has(n.id)
      if (!showOrphans && !isConnected && !n.isTag) {
        return // Dim orphan node
      }

      // 5. Search query check
      if (query) {
        const match =
          n.id.toLowerCase().includes(query) ||
          n.label.toLowerCase().includes(query) ||
          n.folder.toLowerCase().includes(query) ||
          n.tags?.some((t) => t.toLowerCase().includes(query))
        if (match) {
          highlighted.add(n.id)
        }
      } else {
        highlighted.add(n.id)
      }
    })

    // If a node is selected, focus on selected node + its 1-hop connected neighbors
    if (selectedNodeId) {
      const neighborIds = new Set<string>([selectedNodeId])
      masterGraph.links.forEach((l) => {
        const src = typeof l.source === "string" ? l.source : (l.source as any).id
        const tgt = typeof l.target === "string" ? l.target : (l.target as any).id
        if (src === selectedNodeId) neighborIds.add(tgt)
        if (tgt === selectedNodeId) neighborIds.add(src)
      })

      const focused = new Set<string>()
      highlighted.forEach((id) => {
        if (neighborIds.has(id)) focused.add(id)
      })
      highlighted = focused
    }

    return {
      highlightedNodeIds: highlighted,
      hiddenNodeIds: hidden,
      activeCount: highlighted.size,
    }
  }, [searchQuery, showTags, showAttachments, showOrphans, existingOnly, selectedNodeId])

  // Dynamically update camera zoom distance in real-time as the slider moves
  const isFirstMount = React.useRef(true)
  React.useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false
      return
    }
    if (!selectedNodeId) return
    nebulaRef.current?.focusNode(selectedNodeId, clickZoomDistance, 150)
  }, [clickZoomDistance])

  // Automatically zoom and frame highlighted search result nodes
  React.useEffect(() => {
    const query = searchQuery.trim()
    if (!query) return

    const timer = setTimeout(() => {
      if (highlightedNodeIds && highlightedNodeIds.size > 0) {
        nebulaRef.current?.fitNodes(highlightedNodeIds, 850)
      }
    }, 350)

    return () => clearTimeout(timer)
  }, [searchQuery, highlightedNodeIds])

  const folders = foldersInGraph(masterGraph)
  const folderColors = isLight ? FOLDER_COLORS_LIGHT : FOLDER_COLORS

  // Helper toggle component matching Obsidian pink pill switches
  const ToggleSwitch = ({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) => (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-4.5 w-8 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none ${
        checked ? "bg-rose-500" : isLight ? "bg-slate-300" : "bg-neutral-700"
      }`}
    >
      <span
        className={`pointer-events-none inline-block size-3.5 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
          checked ? "translate-x-4" : "translate-x-0.5"
        } my-0.5`}
      />
    </button>
  )

  return (
    <div
      className={`relative h-svh w-full overflow-hidden transition-colors duration-300 ${
        isLight ? "bg-[#f8fafc] text-slate-900" : "bg-[#0b0d12] text-neutral-100"
      }`}
    >
      <KnowledgeNebula
        ref={nebulaRef}
        graph={masterGraph}
        isLight={isLight}
        autoRotate={autoRotate}
        highlightedNodeIds={highlightedNodeIds}
        hiddenNodeIds={hiddenNodeIds}
        clickZoomDistance={clickZoomDistance}
        nodeRelSize={nodeRelSize}
        linkWidth={linkWidth}
        showArrows={showArrows}
        centerForce={centerForce}
        repelForce={repelForce}
        linkForce={linkForce}
        linkDistance={linkDistance}
        onNodeClick={(n) => setSelectedNodeId(n.id)}
        onBackgroundClick={() => setSelectedNodeId(null)}
        className="absolute inset-0"
      />

      {/* Top Bar: Heading & Light/Dark / Back controls */}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-4 p-4 sm:p-5">
        <div>
          <h1 className="font-heading text-base font-semibold">
            Ambient Knowledge Nebula
          </h1>
          <p className={`mt-0.5 font-mono text-xs ${isLight ? "text-slate-600" : "text-neutral-400"}`}>
            {activeCount} active notes · vault graph
          </p>
        </div>
        <div className="pointer-events-auto flex items-center gap-2">
          <button
            onClick={() => nebulaRef.current?.zoomToFit(600, 48)}
            className={`rounded-md border px-2.5 py-1 text-xs font-mono transition-colors ${
              isLight
                ? "border-slate-300 bg-white/80 text-slate-700 hover:bg-white hover:text-slate-900 shadow-xs"
                : "border-white/15 text-neutral-300 hover:bg-white/10 hover:text-white"
            }`}
          >
            🎯 Center & Fit
          </button>
          <button
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
              isLight
                ? "border-slate-300 bg-white/80 text-slate-700 hover:bg-white hover:text-slate-900 shadow-xs"
                : "border-white/15 text-neutral-300 hover:bg-white/10 hover:text-white"
            }`}
          >
            {isLight ? "🌙 Dark" : "☀️ Light"}
          </button>
          <Link
            to="/"
            className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
              isLight
                ? "border-slate-300 bg-white/80 text-slate-700 hover:bg-white hover:text-slate-900 shadow-xs"
                : "border-white/15 text-neutral-300 hover:bg-white/10 hover:text-white"
            }`}
          >
            ← back
          </Link>
        </div>
      </div>

      {/* Lower Right Docked 1:1 Obsidian Control Stack */}
      <div className="pointer-events-auto absolute bottom-4 right-4 z-20 flex flex-col items-end gap-2">
        {controlsOpen ? (
          <div
            className={`w-72 max-h-[85vh] overflow-y-auto rounded-xl border p-4 shadow-2xl backdrop-blur-xl transition-all ${
              isLight
                ? "border-slate-200/80 bg-white/95 text-slate-800"
                : "border-white/12 bg-[#12141a]/95 text-neutral-200"
            }`}
          >
            {/* Header: Filters + Reset + Close */}
            <div className="flex items-center justify-between border-b pb-2.5 border-white/10">
              <button
                onClick={() => setFiltersOpen((v) => !v)}
                className="flex items-center gap-1.5 font-heading text-xs font-semibold tracking-tight text-left opacity-90 hover:opacity-100"
              >
                <span className={`text-[10px] transition-transform ${filtersOpen ? "rotate-0" : "-rotate-90"}`}>
                  ▾
                </span>
                <span>Filters</span>
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleResetDefaults}
                  title="Reset to defaults"
                  className="opacity-60 transition-opacity hover:opacity-100 text-xs"
                >
                  ↻
                </button>
                <button
                  onClick={() => setControlsOpen(false)}
                  title="Close panel"
                  className="opacity-60 transition-opacity hover:opacity-100 text-xs"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Accordion Content */}
            <div className="space-y-4 pt-3 text-xs">
              {/* 1. FILTERS SECTION */}
              {filtersOpen && (
                <div className="space-y-2.5">
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search files..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className={`w-full rounded-lg border px-3 py-1.5 font-sans text-xs outline-none transition-colors ${
                        isLight
                          ? "border-slate-300 bg-slate-100/80 text-slate-900 focus:border-rose-400"
                          : "border-white/15 bg-black/50 text-neutral-100 focus:border-rose-500"
                      }`}
                    />
                  </div>

                  <div className="space-y-2 pt-1 font-sans text-xs">
                    <div className="flex items-center justify-between opacity-90">
                      <span>Tags</span>
                      <ToggleSwitch checked={showTags} onChange={setShowTags} />
                    </div>
                    <div className="flex items-center justify-between opacity-90">
                      <span>Attachments</span>
                      <ToggleSwitch checked={showAttachments} onChange={setShowAttachments} />
                    </div>
                    <div className="flex items-center justify-between opacity-90">
                      <span>Existing files only</span>
                      <ToggleSwitch checked={existingOnly} onChange={setExistingOnly} />
                    </div>
                    <div className="flex items-center justify-between opacity-90">
                      <span>Orphans</span>
                      <ToggleSwitch checked={showOrphans} onChange={setShowOrphans} />
                    </div>
                  </div>
                </div>
              )}

              {/* 2. GROUPS SECTION */}
              <div className="border-t pt-3 border-white/10">
                <button
                  onClick={() => setGroupsOpen((v) => !v)}
                  className="flex w-full items-center gap-1.5 font-heading text-xs font-semibold text-left opacity-90 hover:opacity-100"
                >
                  <span className={`text-[10px] transition-transform ${groupsOpen ? "rotate-0" : "-rotate-90"}`}>
                    ▾
                  </span>
                  <span>Groups</span>
                </button>
                {groupsOpen && (
                  <div className="mt-2 space-y-2">
                    <button
                      onClick={() =>
                        setCustomGroups((g) => [
                          ...g,
                          { id: String(Date.now()), query: "path:Projects", color: "#ec4899" },
                        ])
                      }
                      className={`w-full rounded-lg border py-1.5 font-sans text-xs transition-colors ${
                        isLight
                          ? "border-slate-300 bg-slate-100 hover:bg-slate-200 text-slate-800"
                          : "border-white/15 bg-white/5 hover:bg-white/10 text-neutral-200"
                      }`}
                    >
                      New group
                    </button>
                    {customGroups.map((g) => (
                      <div key={g.id} className="flex items-center justify-between rounded-md border p-1.5 border-white/10">
                        <span className="font-mono text-[11px] opacity-80">{g.query}</span>
                        <span className="size-2.5 rounded-full" style={{ background: g.color }} />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 3. DISPLAY SECTION */}
              <div className="border-t pt-3 border-white/10">
                <button
                  onClick={() => setDisplayOpen((v) => !v)}
                  className="flex w-full items-center gap-1.5 font-heading text-xs font-semibold text-left opacity-90 hover:opacity-100"
                >
                  <span className={`text-[10px] transition-transform ${displayOpen ? "rotate-0" : "-rotate-90"}`}>
                    ▾
                  </span>
                  <span>Display</span>
                </button>

                {displayOpen && (
                  <div className="mt-2.5 space-y-3">
                    <div className="flex items-center justify-between opacity-90">
                      <span>Arrows</span>
                      <ToggleSwitch checked={showArrows} onChange={setShowArrows} />
                    </div>

                    <div className="flex items-center justify-between opacity-90">
                      <span>Auto Rotate Camera</span>
                      <ToggleSwitch checked={autoRotate} onChange={setAutoRotate} />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Text fade threshold</span>
                        <span>{textFadeThreshold.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={textFadeThreshold}
                        onChange={(e) => setTextFadeThreshold(parseFloat(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Node size</span>
                        <span>{(nodeRelSize / 2.4).toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        step="0.1"
                        value={nodeRelSize}
                        onChange={(e) => setNodeRelSize(parseFloat(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Link thickness</span>
                        <span>{linkWidth.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0.1"
                        max="5.0"
                        step="0.1"
                        value={linkWidth}
                        onChange={(e) => setLinkWidth(parseFloat(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Note Spawn Delay</span>
                        <span>{noteDelayMs}ms</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="150"
                        step="5"
                        value={noteDelayMs}
                        onChange={(e) => setNoteDelayMs(parseInt(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Zoom In Closeness</span>
                        <span>{clickZoomDistance}px</span>
                      </div>
                      <input
                        type="range"
                        min="20"
                        max="180"
                        step="5"
                        value={clickZoomDistance}
                        onChange={(e) => setClickZoomDistance(parseInt(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    {/* ANIMATE & CAMERA BUTTONS */}
                    <div className="flex items-center justify-end gap-2 pt-1">
                      <button
                        onClick={() => {
                          setSelectedNodeId(null)
                          nebulaRef.current?.zoomToFit(600, 48)
                        }}
                        className={`rounded-lg border px-3 py-1.5 font-sans text-xs font-medium shadow-sm transition-all active:scale-95 ${
                          isLight
                            ? "border-slate-300 bg-slate-200/80 text-slate-800 hover:bg-slate-300"
                            : "border-white/15 bg-white/5 text-neutral-200 hover:bg-white/15"
                        }`}
                      >
                        🎯 Center & Fit
                      </button>
                      <button
                        onClick={() => nebulaRef.current?.animateBirth(noteDelayMs)}
                        className={`rounded-lg border px-4 py-1.5 font-sans text-xs font-medium shadow-sm transition-all active:scale-95 ${
                          isLight
                            ? "border-slate-300 bg-slate-200/90 text-slate-900 hover:bg-slate-300"
                            : "border-white/15 bg-white/10 text-white hover:bg-white/20"
                        }`}
                      >
                        Animate
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* 4. FORCES SECTION */}
              <div className="border-t pt-3 border-white/10">
                <button
                  onClick={() => setForcesOpen((v) => !v)}
                  className="flex w-full items-center gap-1.5 font-heading text-xs font-semibold text-left opacity-90 hover:opacity-100"
                >
                  <span className={`text-[10px] transition-transform ${forcesOpen ? "rotate-0" : "-rotate-90"}`}>
                    ▾
                  </span>
                  <span>Forces</span>
                </button>

                {forcesOpen && (
                  <div className="mt-2.5 space-y-3">
                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Center force</span>
                        <span>{centerForce.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={centerForce}
                        onChange={(e) => setCenterForce(parseFloat(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Repel force</span>
                        <span>{repelForce.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="30"
                        step="0.5"
                        value={repelForce}
                        onChange={(e) => setRepelForce(parseFloat(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Link force</span>
                        <span>{linkForce.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0.1"
                        max="2.0"
                        step="0.05"
                        value={linkForce}
                        onChange={(e) => setLinkForce(parseFloat(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="mb-1 flex justify-between font-sans text-[11px] opacity-80">
                        <span>Link distance</span>
                        <span>{Math.round(linkDistance)}</span>
                      </div>
                      <input
                        type="range"
                        min="50"
                        max="800"
                        step="10"
                        value={linkDistance}
                        onChange={(e) => setLinkDistance(parseFloat(e.target.value))}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setControlsOpen(true)}
            className={`rounded-xl border px-3 py-2 text-xs font-mono shadow-lg backdrop-blur-md transition-colors ${
              isLight
                ? "border-slate-300 bg-white/90 text-slate-800 hover:bg-white"
                : "border-white/15 bg-[#14161c]/90 text-neutral-200 hover:bg-[#14161c]"
            }`}
          >
            ⚙ Controls
          </button>
        )}
      </div>

      {/* Lower Left Folder Legend */}
      <div className="pointer-events-none absolute bottom-0 left-0 flex flex-wrap gap-x-4 gap-y-1.5 p-4 sm:p-5 pr-80">
        {folders.map((f) => (
          <span
            key={f}
            className={`flex items-center gap-1.5 font-mono text-[11px] ${
              isLight ? "text-slate-600 font-medium" : "text-neutral-400"
            }`}
          >
            <span
              className="size-2 rounded-full"
              style={{ background: folderColors[f] }}
            />
            {f}
          </span>
        ))}
      </div>
    </div>
  )
}

