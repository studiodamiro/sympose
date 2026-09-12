import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { notify } from "@/lib/notify"
import {
  Add01Icon,
  ArrowLeft01Icon,
  ArrowRight01Icon,
  File01Icon,
  Folder01Icon,
  FolderAddIcon,
  Note01Icon,
  ThumbsUpIcon,
} from "@hugeicons/core-free-icons"

import { cn, stripMdExtension } from "@/lib/utils"
import {
  getCookie,
  getCookieBool,
  setCookie,
  setCookieBool,
} from "@/lib/cookies"
import { useBreakpoint } from "@/lib/use-breakpoint"
import { useFillWidth } from "@/lib/use-fill-width"
import { useTransientFlag } from "@/lib/use-transient-flag"
import { usePanels, type StagePanel } from "@/lib/use-panels"
import {
  useSlideSwap,
  slideEnterClassName,
  slideExitClassName,
  type SlideDirection,
} from "@/lib/use-slide-swap"
import { useActivePersona } from "@/lib/use-active-persona"
import { useEditorPreferences } from "@/lib/use-editor-preferences"
import { useToolbarItems } from "@/lib/use-toolbar-items"
import { usePinnedNotes } from "@/lib/use-pinned-notes"
import { useNotificationPreferences } from "@/lib/use-notification-preferences"
import { useNebulaPreferences } from "@/lib/use-nebula-preferences"
import {
  fetchPersonas,
  resolvePersonaVisuals,
  type LivePersona,
} from "@/lib/personas"
import { fetchVaultTree } from "@/lib/vault-tree-api"
import { createVaultNote, createVaultFolder } from "@/lib/vault-note-api"
import { findNoteByWikilink } from "@/lib/find-note-by-wikilink"
import { matchWikilinkTargets } from "@/lib/vault-wikilink-completions"
import { VAULT_FOLDERS } from "@/lib/vault-folders"
import {
  ActionBadge,
  AgentCard,
  ChatActionGroup,
  ChatMessage,
  ChatPanel,
  CollapseAllButton,
  ContentPanel,
  ControlSectionsProvider,
  EditorPreferencesSection,
  MainMenu,
  NotificationsSection,
  MarkdownPanel,
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  MENU_TRASH_ID,
  NebulaAppearanceSection,
  NebulaModeToggle,
  SlackStatusPill,
  ThemeToggle,
  TopBar,
  TrashList,
  VaultTree,
  type MainMenuItem,
  type VaultNode,
} from "@/components/sympose"

// Lazy — pulls in `react-force-graph` / `d3-force`. Mounted only after first
// paint (see the idle gate below) so it never delays the shell's TTFT.
const AmbientNebula = React.lazy(() =>
  import("@/components/sympose/ambient-nebula").then((m) => ({
    default: m.AmbientNebula,
  }))
)

/** Curated name → icon map, so known folders keep their glyph when the menu is
 *  driven by the live vault instead of the static `VAULT_FOLDERS` list. */
const FOLDER_ICONS = new Map(VAULT_FOLDERS.map((f) => [f.name, f.icon]))

/** Icon for a top-level vault entry surfaced on the main menu. */
function menuIconFor(node: VaultNode) {
  if (node.type === "note")
    return node.name.endsWith(".md") ? Note01Icon : File01Icon
  return FOLDER_ICONS.get(node.name) ?? Folder01Icon
}

/** Labels for the non-folder sections the footer rows can select. */
const SECTION_LABELS: Record<string, string> = {
  [MENU_SETTINGS_ID]: "Settings",
  [MENU_ACCOUNT_ID]: "Agent",
  [MENU_TRASH_ID]: "Bin",
}

const AUTO_COLLAPSE_COOKIE = "sympose:pref.autoCollapseMenu"
const SECTION_COOKIE = "sympose:shell.section"
const RAIL_COOKIE = "sympose:shell.rail"

/**
 * `<MainMenu>` mounted as the real app shell — full viewport height, no demo
 * frame. The three stage panels (content, editor, chat) toggle independently;
 * tablet caps the stage at two (oldest-evicted, rightmost fills), phone at one.
 * All visibility + widths persist to cookies globally and are clamped to the
 * breakpoint on load.
 *
 * Phone keeps the exact tablet layout — a docked menu rail beside the stage —
 * with two changes: a fixed `<TopBar>` carries the brand mark, the vault
 * button, Settings, the account, and the chat actions; and the menu is hidden
 * by default, sliding in and out (the same park/reveal the panels use) from
 * that vault button. Reached at /shell (outside the RootLayout chrome).
 */
export function AppShell() {
  const rootRef = React.useRef<HTMLDivElement>(null)
  const breakpoint = useBreakpoint(rootRef)
  const panels = usePanels(breakpoint)
  const isPhone = breakpoint === "phone"

  // The highlighted folder / section — persisted, since the content panel is
  // usually hidden on phone and should come back pointed where it was left.
  // The menu is driven by the live vault, so a persisted folder id is only
  // reconciled once the tree has loaded (see the effect below the fetch).
  const [active, setActive] = React.useState<string>(
    () => getCookie(SECTION_COOKIE) || ""
  )
  React.useEffect(() => {
    setCookie(SECTION_COOKIE, active)
  }, [active])

  // Browser-style visit history over `active`, for the content panel's
  // back/forward toolbar buttons. A ref pair holds the stack/cursor (no
  // re-render needed to track them); `historyTick` forces one so the buttons'
  // disabled state stays current. `navigatingHistory` suppresses the effect's
  // own push when `active` changes because a back/forward click set it.
  const historyStack = React.useRef<string[]>([active])
  const historyIndex = React.useRef(0)
  const navigatingHistory = React.useRef(false)
  const [, setHistoryTick] = React.useState(0)
  React.useEffect(() => {
    if (navigatingHistory.current) {
      navigatingHistory.current = false
      return
    }
    if (historyStack.current[historyIndex.current] === active) return
    historyStack.current = [
      ...historyStack.current.slice(0, historyIndex.current + 1),
      active,
    ]
    historyIndex.current = historyStack.current.length - 1
    setHistoryTick((t) => t + 1)
  }, [active])
  const canGoBack = historyIndex.current > 0
  const canGoForward = historyIndex.current < historyStack.current.length - 1
  // Which way the content panel's body should slide on the next `active`
  // change — set right alongside whatever triggered it (a back/forward click,
  // or any other pick, which reads as "forward": it's pushing a new
  // destination, same as browser navigation).
  const [contentDirection, setContentDirection] =
    React.useState<SlideDirection>("forward")
  const goBack = () => {
    if (!canGoBack) return
    navigatingHistory.current = true
    setContentDirection("back")
    historyIndex.current -= 1
    setActive(historyStack.current[historyIndex.current])
    setHistoryTick((t) => t + 1)
  }
  const goForward = () => {
    if (!canGoForward) return
    navigatingHistory.current = true
    setContentDirection("forward")
    historyIndex.current += 1
    setActive(historyStack.current[historyIndex.current])
    setHistoryTick((t) => t + 1)
  }

  // Phone: the TopBar vault button toggles the navigation view — the menu rail
  // and the content panel move together. Its open/closed state is remembered.
  const [menuShown, setMenuShown] = React.useState(() =>
    getCookieBool(RAIL_COOKIE, false)
  )
  React.useEffect(() => {
    setCookieBool(RAIL_COOKIE, menuShown)
  }, [menuShown])

  // What was on screen before the vault view opened, so closing it returns there.
  const beforeVault = React.useRef<"chat" | "editor" | null>(null)

  // Tablet: when the editor is filling and the chat is asked for, shrink the
  // editor to its dragged width *first*, then let the chat in — otherwise the
  // editor's contraction and the chat's entrance collide and the editor snaps.
  const [unfillFirst, setUnfillFirst] = React.useState(false)
  const unfillTimer = React.useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  )
  React.useEffect(() => () => clearTimeout(unfillTimer.current), [])

  // Close the vault view — rail out, content panel out, back to the prior panel.
  const closeVault = () => {
    setMenuShown(false)
    panels.close("content")
    if (beforeVault.current) panels.open(beforeVault.current)
    beforeVault.current = null
  }

  const revealMenu = () => {
    if (menuShown) {
      closeVault()
      return
    }
    // toggle open — rail in, content panel in (on a folder, never a sentinel)
    beforeVault.current = panels.isOpen("chat")
      ? "chat"
      : panels.isOpen("editor")
        ? "editor"
        : null
    if (
      (active === MENU_SETTINGS_ID ||
        active === MENU_ACCOUNT_ID ||
        active === MENU_TRASH_ID) &&
      menuItems.length > 0
    ) {
      setActive(menuItems[0].id)
    }
    panels.open("content")
    setMenuShown(true)
  }

  const selectSection = (id: string) => {
    // On phone, jumping to Settings / Agent from the TopBar slides the menu away
    // (folder picks keep it, so its highlight stays visible next to the panel).
    if (isPhone && (id === MENU_SETTINGS_ID || id === MENU_ACCOUNT_ID)) {
      setMenuShown(false)
    }
    // A root note row (README.md) also selects it in the tree.
    if (noteIds.has(id)) setSelectedNote(id)
    // Leaving the tree for the bin: drop any half-typed create-input name.
    if (id === MENU_TRASH_ID) closeCreate()
    if (id === resolvedActive && panels.isOpen("content")) {
      panels.close("content")
    } else {
      setContentDirection("forward")
      setActive(id)
      panels.open("content")
    }
  }

  // Opening chat or the editor on phone slides the menu out of the way.
  const toggleChat = () => {
    if (isPhone && !panels.isOpen("chat")) setMenuShown(false)
    const openingOverFullEditor =
      !isPhone &&
      breakpoint !== "desktop" &&
      panels.isOpen("editor") &&
      !panels.isOpen("chat")
    if (openingOverFullEditor) {
      // phase 1: editor shrinks to its dragged width; phase 2 (~one transition
      // later): the chat slides into the space it vacated
      setUnfillFirst(true)
      clearTimeout(unfillTimer.current)
      unfillTimer.current = setTimeout(() => {
        setUnfillFirst(false)
        panels.open("chat")
      }, 340)
      return
    }
    panels.toggle("chat")
  }
  const toggleEditor = () => {
    if (isPhone && !panels.isOpen("editor")) setMenuShown(false)
    panels.toggle("editor")
  }

  // Menu: on a small breakpoint it snaps to the rail (if the pref is on) — but
  // stays fully draggable, and a desktop trip back restores the expanded width
  // unless the user has since collapsed it themselves. `forced` remembers that
  // the rail came from the breakpoint, not the user. Adjusted on breakpoint
  // change during render (the React "derive from a changing prop" pattern).
  const autoCollapsePref = React.useMemo(
    () => getCookieBool(AUTO_COLLAPSE_COOKIE, true),
    []
  )
  const [menu, setMenu] = React.useState<{
    collapsed: boolean | undefined
    forced: boolean
    bp: typeof breakpoint
  }>({ collapsed: undefined, forced: false, bp: breakpoint })
  if (breakpoint !== menu.bp) {
    if (breakpoint !== "desktop" && autoCollapsePref) {
      setMenu({ collapsed: true, forced: true, bp: breakpoint })
    } else if (breakpoint === "desktop" && menu.forced) {
      setMenu({ collapsed: false, forced: false, bp: breakpoint })
    } else {
      setMenu((m) => ({ ...m, bp: breakpoint }))
    }
  }

  const chatSlotRef = React.useRef<HTMLDivElement>(null)
  // Real width free to the chat slot, remeasured every frame while any panel
  // slides. The chat fills it with flex-grow (so it adopts the width live as the
  // editor animates out), and clamps to it with max-width so its own collapse
  // has a real pixel target to tween to.
  const chatAvailW = useFillWidth(chatSlotRef)

  const contentOpen = panels.isOpen("content")
  const editorOpen = panels.isOpen("editor")
  const chatOpen = panels.isOpen("chat")
  // Arm the max-width transition only for the ~320ms the chat is deliberately
  // opening or closing. Otherwise max-width just follows the live measurement
  // instantly, so the chat tracks a neighbour's slide instead of lagging it.
  const chatToggling = useTransientFlag(chatOpen)
  // Editor grows into whatever's free to its right (the chat's area, the
  // content panel's if that's closed too) — but only on the smaller
  // breakpoints, where screen room is scarce and a parked chat leaving a blank
  // column reads as broken. On desktop the editor keeps its dragged,
  // cookie-persisted width when the chat is hidden and the vacated space stays
  // empty; the resize handle stays live so that width is the user's to set.
  // Content never grows — it is navigation, it keeps its dragged width even
  // when alone.
  const editorFill =
    editorOpen && !chatOpen && !unfillFirst && breakpoint !== "desktop"

  // Agent picker — the active persona is client state (a cookie), and the
  // roster is fetched once. Both feed the `MENU_ACCOUNT_ID` panel; the handle
  // is lifted here so the vault panels can scope their `?persona=` calls to it
  // once those land.
  const [activePersona, setActivePersona] = useActivePersona()
  const [editorPrefs, setEditorPref] = useEditorPreferences()
  const [toolbarItems, setToolbarItems] = useToolbarItems()
  const { isPinned, togglePin } = usePinnedNotes()
  const [notifyPrefs, setNotifyPref] = useNotificationPreferences()
  const [nebulaPrefs, setNebulaPref] = useNebulaPreferences()
  const explore = nebulaPrefs.interaction === "explore"

  // Explore auto-collapses the three stage panels — content, editor, chat —
  // so the whole canvas is click-through to the nebula underneath (ADR-088's
  // deferred Phase B item, landed in ADR-090); the trip back to Focus reopens
  // exactly what was showing before, oldest-first, the same order `usePanels`
  // itself keeps. A ref (not a `panels` dependency) reads the live panel
  // handle so this effect only fires on an actual mode change, not on every
  // panel-order write `usePanels` makes.
  const panelsRef = React.useRef(panels)
  panelsRef.current = panels
  const stashedPanels = React.useRef<StagePanel[] | null>(null)
  const prevInteraction = React.useRef(nebulaPrefs.interaction)
  React.useEffect(() => {
    const was = prevInteraction.current
    prevInteraction.current = nebulaPrefs.interaction
    if (was === nebulaPrefs.interaction) return
    if (nebulaPrefs.interaction === "explore") {
      stashedPanels.current = panelsRef.current.visible
      for (const p of panelsRef.current.visible) panelsRef.current.close(p)
    } else {
      const stash = stashedPanels.current
      stashedPanels.current = null
      stash?.forEach((p) => panelsRef.current.open(p))
    }
  }, [nebulaPrefs.interaction])

  // The ambient Knowledge Nebula (Module A) sits behind the whole shell. Its
  // renderer chunk is deferred until the browser is idle after first paint so
  // `react-force-graph` never competes with the shell's TTFT.
  const [nebulaReady, setNebulaReady] = React.useState(false)
  React.useEffect(() => {
    const hasIdle = typeof window.requestIdleCallback === "function"
    const handle = hasIdle
      ? window.requestIdleCallback(() => setNebulaReady(true), { timeout: 2000 })
      : window.setTimeout(() => setNebulaReady(true), 400)
    return () => {
      if (hasIdle) window.cancelIdleCallback(handle as number)
      else window.clearTimeout(handle as number)
    }
  }, [])
  const [personas, setPersonas] = React.useState<LivePersona[]>([])
  React.useEffect(() => {
    let alive = true
    fetchPersonas().then((list) => {
      if (alive) setPersonas(list)
    })
    return () => {
      alive = false
    }
  }, [])

  // Vault browser — the persona-scoped directory tree (GET /api/vault/tree),
  // re-fetched whenever the active persona changes so the sandbox follows the
  // switcher. Every folder row opens the same panel: the whole scoped tree.
  const [vaultTree, setVaultTree] = React.useState<VaultNode[]>([])
  const [selectedNote, setSelectedNote] = React.useState<string>()
  // Nebula node ids are the bare filename stem (`vault_manifest_build._stem`
  // on the backend), not the full vault-relative path — so whichever note
  // becomes active in the content panel can drive the ambient nebula's
  // focus/highlight (see `AmbientNebula`'s `activeNoteId`).
  const activeNoteId = selectedNote?.split("/").pop()?.replace(/\.[^./]+$/, "")
  // Bumped after a note is created (ADR-083) to re-pull the tree so the new
  // file shows up without a persona switch.
  const [vaultRefreshKey, setVaultRefreshKey] = React.useState(0)
  // `null` = no create-input open; otherwise which kind is being named, with
  // its current typed value in `createName`.
  const [pendingCreate, setPendingCreate] = React.useState<"note" | "folder" | null>(
    null
  )
  const [createName, setCreateName] = React.useState("")
  const [creating, setCreating] = React.useState(false)
  const closeCreate = () => {
    setPendingCreate(null)
    setCreateName("")
  }
  // The vault panel shows the bin (ADR-085) instead of the tree when the
  // main-menu Bin row is the active section.
  const trashView = active === MENU_TRASH_ID
  React.useEffect(() => {
    let alive = true
    fetchVaultTree(activePersona).then((tree) => {
      if (alive) setVaultTree(tree)
    })
    return () => {
      alive = false
    }
  }, [activePersona, vaultRefreshKey])

  // Main menu = the vault's surface (top-level folders + root notes like
  // README.md), in the tree's own order, with curated icons where the folder
  // name is known. The two footer sentinels (Settings, Agent) stay separate.
  const menuItems: MainMenuItem[] = vaultTree.map((node) => ({
    id: node.path,
    label:
      editorPrefs.hideExtension === "on"
        ? stripMdExtension(node.name)
        : node.name,
    icon: menuIconFor(node),
  }))
  const noteIds = new Set(
    vaultTree.filter((n) => n.type === "note").map((n) => n.path)
  )

  // A `[[wikilink]]` clicked inside the open note — resolve it against the
  // full (nested) tree by filename stem and jump the editor there. Silently
  // does nothing for a target the sandboxed tree doesn't contain.
  const openWikilink = (target: string) => {
    const match = findNoteByWikilink(vaultTree, target)
    if (match) {
      setSelectedNote(match.path)
      panels.open("editor")
    }
  }

  // stylo's `wikiLinkSource` (>=0.7.0) is read once, at mount — so the
  // function identity handed to `<Stylo>` must stay stable across a tree
  // refetch (new persona, new note, ADR-083 create) rather than being rebuilt
  // every render. A ref carries the live tree; the callback itself never
  // changes.
  const vaultTreeRef = React.useRef(vaultTree)
  vaultTreeRef.current = vaultTree
  const wikiLinkSource = React.useCallback(
    (query: string) => matchWikilinkTargets(vaultTreeRef.current, query),
    []
  )

  // `active` holds the user's last explicit pick; a persisted folder id that no
  // longer exists (e.g. after switching to a persona with a narrower sandbox)
  // falls back to the first surface entry — derived, not synced.
  const isSentinel =
    active === MENU_SETTINGS_ID ||
    active === MENU_ACCOUNT_ID ||
    active === MENU_TRASH_ID
  const resolvedActive =
    isSentinel || menuItems.some((i) => i.id === active)
      ? active
      : (menuItems[0]?.id ?? active)

  // The content panel shows the *contents* of the selected surface entry — a
  // folder's own subtree, or a single root note — not the whole vault tree.
  const activeNode = vaultTree.find((n) => n.path === resolvedActive)
  const panelNodes: VaultNode[] =
    activeNode?.type === "folder"
      ? (activeNode.children ?? [])
      : activeNode
        ? [activeNode]
        : []

  const activeLabel = SECTION_LABELS[resolvedActive] ?? resolvedActive

  // Create a note or folder in the folder currently in view (or the vault
  // root when a root note is the active surface). A new note opens in the
  // editor (ADR-083); a new folder (ADR-095) just refreshes the tree.
  const submitCreate = async () => {
    const kind = pendingCreate
    const name = createName
      .trim()
      .replace(/\.md$/i, "")
      .replace(/^\/+|\/+$/g, "")
    if (!kind || !name || creating) return
    const folder = activeNode?.type === "folder" ? resolvedActive : ""
    const target = folder ? `${folder}/${name}` : name
    setCreating(true)
    const result =
      kind === "note"
        ? await createVaultNote(target, activePersona)
        : await createVaultFolder(target, activePersona)
    setCreating(false)
    if (!result.ok) {
      notify.error(result.error)
      return
    }
    closeCreate()
    setVaultRefreshKey((k) => k + 1)
    if (kind === "note") {
      setSelectedNote(`${target}.md`)
      panels.open("editor")
    }
    notify.success(`Created ${name}`)
  }

  // The main-menu account row wears the active persona's name, icon and accent.
  const activeAgentName =
    personas.find((p) => p.handle === activePersona)?.name ?? activePersona
  const activeAgentVisuals = resolvePersonaVisuals(activePersona)
  // Phone: the rail only shows alongside the content panel — the two are one
  // view. Desktop / tablet: always shown.
  const menuOpen = isPhone ? menuShown && contentOpen : true
  // Settings / Agent on phone are plain destination pages, styled off the chat
  // panel (same background, same gutter) rather than the vault content surface.
  const plainPage =
    isPhone && (active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID)

  // The panel-wide toolbar (back/forward, new note/folder) — pinned to the
  // content panel's own top edge via `<ContentPanel header>`, mirroring the
  // editor toolbar's chrome exactly rather than sitting inline with the
  // section title. Shown on every surface (vault folders, Bin, Settings,
  // Agent) so back/forward always works; new note/folder only make sense
  // on an actual vault folder, so that group is dropped on the sentinel
  // surfaces instead of rendering disabled, inert buttons.
  const contentHeader = (
    <div className="flex items-center justify-between gap-1">
      <div className="flex items-center gap-0.5">
        <button
          type="button"
          onClick={goBack}
          disabled={!canGoBack}
          aria-label="Back"
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
        >
          <HugeiconsIcon icon={ArrowLeft01Icon} className="size-4" />
        </button>
        <button
          type="button"
          onClick={goForward}
          disabled={!canGoForward}
          aria-label="Forward"
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
        >
          <HugeiconsIcon icon={ArrowRight01Icon} className="size-4" />
        </button>
      </div>
      {!isSentinel && (
        <div className="flex items-center gap-0.5">
          <div
            className={cn(
              // `h-7` here (not just on the input) is load-bearing: `w-0` only
              // clips width, so an unconstrained-height input still pushes
              // the whole toolbar row taller by its own natural line-height
              // even while invisibly zero-width. Fixing the wrapper's height
              // to match the buttons keeps the row at their 28px regardless.
              "h-7 overflow-hidden rounded-md transition-[width] duration-snappy ease-snappy",
              pendingCreate ? "w-40" : "w-0"
            )}
          >
            <input
              autoFocus
              value={createName}
              disabled={creating}
              onChange={(e) => setCreateName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submitCreate()
                else if (e.key === "Escape") closeCreate()
              }}
              onBlur={closeCreate}
              placeholder={
                pendingCreate === "folder"
                  ? "New folder name… ↵"
                  : activeNode?.type === "folder"
                    ? `New note in ${activeLabel}… ↵`
                    : "New note name… ↵"
              }
              className="h-7 w-full rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
            />
          </div>
          <button
            type="button"
            onClick={() =>
              setPendingCreate((v) => {
                setCreateName("")
                return v === "note" ? null : "note"
              })
            }
            aria-label="New note"
            aria-pressed={pendingCreate === "note"}
            className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground aria-pressed:text-foreground"
          >
            <HugeiconsIcon icon={Add01Icon} className="size-4" />
          </button>
          <button
            type="button"
            onClick={() =>
              setPendingCreate((v) => {
                setCreateName("")
                return v === "folder" ? null : "folder"
              })
            }
            aria-label="New folder"
            aria-pressed={pendingCreate === "folder"}
            className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground aria-pressed:text-foreground"
          >
            <HugeiconsIcon icon={FolderAddIcon} className="size-4" />
          </button>
        </div>
      )}
    </div>
  )

  const contentBody =
    active === MENU_ACCOUNT_ID ? (
      <AgentCard
        personas={personas}
        active={activePersona}
        onSwitch={setActivePersona}
        phone={isPhone}
      />
    ) : active === MENU_SETTINGS_ID ? (
      <ControlSectionsProvider>
        <div className="flex items-center justify-between gap-4">
          <h1 className="font-heading text-2xl font-semibold text-fg-strong">
            {activeLabel}
          </h1>
          <CollapseAllButton />
        </div>
        <EditorPreferencesSection
          prefs={editorPrefs}
          setPref={setEditorPref}
          toolbarItems={toolbarItems}
          onToolbarItemsChange={setToolbarItems}
        />
        <NotificationsSection prefs={notifyPrefs} setPref={setNotifyPref} />
        <NebulaAppearanceSection prefs={nebulaPrefs} setPref={setNebulaPref} />
      </ControlSectionsProvider>
    ) : (
      <div className="flex flex-col gap-2">
        <h2 className="font-heading text-2xl font-semibold text-fg-strong">
          {trashView ? "Bin" : activeLabel || "Vault"}
        </h2>
        {trashView ? (
          <TrashList
            persona={activePersona}
            refreshKey={vaultRefreshKey}
            onRestored={() => setVaultRefreshKey((k) => k + 1)}
          />
        ) : (
          <>
            {vaultTree.length === 0 ? (
              <p className="text-sm text-fg-muted">
                No notes in scope — check that the dashboard API is reachable
                and the persona has vault folders.
              </p>
            ) : panelNodes.length === 0 ? (
              <p className="text-sm text-fg-muted">This folder is empty.</p>
            ) : (
              <VaultTree
                nodes={panelNodes}
                storageKey="sympose:vault.expanded"
                selectedPath={selectedNote}
                onSelect={(node) => {
                  // Picking a note always brings the editor forward — same as
                  // creating one (`onCreated`) or following a wikilink.
                  setSelectedNote(node.path)
                  panels.open("editor")
                }}
                persona={activePersona}
                onRenamed={(oldPath, newPath) => {
                  setVaultRefreshKey((k) => k + 1)
                  if (selectedNote === oldPath) setSelectedNote(newPath)
                }}
                onDeleted={(path) => {
                  setVaultRefreshKey((k) => k + 1)
                  // `path` is a note's own path for a note-row delete, or a
                  // folder's path when a whole folder (ADR-099) went to the
                  // bin — either way, close the editor if it was showing
                  // something that just moved.
                  if (
                    selectedNote === path ||
                    selectedNote?.startsWith(`${path}/`)
                  ) {
                    setSelectedNote(undefined)
                  }
                }}
                onCreated={(path) => {
                  setVaultRefreshKey((k) => k + 1)
                  setSelectedNote(path)
                  panels.open("editor")
                }}
                isPinned={isPinned}
                onTogglePin={togglePin}
                hideExtension={editorPrefs.hideExtension === "on"}
              />
            )}
          </>
        )}
      </div>
    )

  // Sideways slide keyed on the surface actually shown — back/forward-aware
  // (`contentDirection`, set alongside whatever triggered the `active`
  // change above), sequential rather than a crossfade: the outgoing surface
  // finishes its own slide-out before the incoming one starts sliding in
  // (see `useSlideSwap`).
  const {
    displayKey: contentDisplayKey,
    displayPayload: contentDisplayNode,
    exitDirection: contentExitDirection,
    enterDirection: contentEnterDirection,
    onExitComplete: onContentExitComplete,
  } = useSlideSwap(resolvedActive, contentBody, contentDirection)

  const chatMessages = (
    <>
      <ChatMessage role="user" reaction={<HugeiconsIcon icon={ThumbsUpIcon} />}>
        However some fonts, called variable fonts, can support a range of
        weights with a more or less fine granularity
      </ChatMessage>
      <ChatMessage
        role="persona"
        handle="samantha"
        latency="0.68 TTFT"
        footer={
          <ActionBadge
            action="WRITE_NOTE"
            detail="Projects/Sympose/Typography.md"
            aria-pressed={editorOpen}
            onClick={toggleEditor}
          />
        }
      >
        But I must explain to you how all this mistaken idea of denouncing
        pleasure and praising pain was born and I will give you a complete
        account of the system, and expound the actual teachings of the great
        explorer of the truth, the master-builder of human happiness. No one
        rejects, dislikes, or avoids pleasure itself, because it is pleasure,
        but because
      </ChatMessage>
      <ChatMessage role="persona" handle="samantha">
        I will give you a complete account of the system, and expound the actual
        teachings of the great explorer of the truth, the master-builder of
        human happiness. No one rejects, dislikes, or avoids pleasure itself,
        because it is pleasure, but because
      </ChatMessage>
    </>
  )

  return (
    <div
      ref={rootRef}
      className={cn(
        "flex h-svh w-full overflow-hidden bg-background text-foreground",
        isPhone && "flex-col"
      )}
      // Feeds `.sy-frosted-panel` — the content and editor panels only,
      // ADR-088 (blur dropped, ADR-089). `off` (the default: opacity 1) →
      // solid tokens. `tint` → the opacity knob alone.
      data-nebula-frost={nebulaPrefs.panelOpacity < 1 ? "tint" : "off"}
      style={
        {
          "--sy-panel-opacity": String(nebulaPrefs.panelOpacity),
        } as React.CSSProperties
      }
    >
      {/* Module A — the persistent ambient vault graph. Always `fixed inset-0
          z-0`, the literal bottom of the stack in both Focus and Explore —
          the stage below gives up pointer events instead (see its
          `pointer-events-none`), rather than this layer ever climbing above
          the chrome. */}
      {nebulaReady && (
        <React.Suspense fallback={null}>
          <AmbientNebula
            prefs={nebulaPrefs}
            setPref={setNebulaPref}
            activeNoteId={activeNoteId}
          />
        </React.Suspense>
      )}

      {isPhone && (
        <TopBar
          // `relative` (any positioned value) is enough to paint above the
          // fixed z-0 nebula, via DOM order — no z-index needed.
          className="relative"
          chatOpen={chatOpen}
          onToggleChat={toggleChat}
          menuOpen={menuShown}
          onToggleMenu={revealMenu}
          settingsActive={contentOpen && active === MENU_SETTINGS_ID}
          onSettings={() => selectSection(MENU_SETTINGS_ID)}
          accountActive={contentOpen && active === MENU_ACCOUNT_ID}
          onAccount={() => selectSection(MENU_ACCOUNT_ID)}
        />
      )}

      {/* menu + stage row — overflow-hidden clips the menu (and the panels)
          while they are parked off to the inline-start. `pointer-events-none`
          so this row doesn't sit as a dead hit-target above the nebula in
          Explore once its own children (the menu, the stage) have nothing
          reclaiming a given point — mirrors the same pattern the stage div
          already uses one level down; without it, this row's own box (not
          the panels inside it) is what elementFromPoint hits at a closed
          panel's location, and the click never reaches the nebula. */}
      <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden pointer-events-none">
        <MainMenu
          items={menuItems}
          // above the stage so the content panel tucks *behind* it on hide
          className="z-20"
          open={menuOpen}
          hideChrome={isPhone}
          activeId={contentOpen ? resolvedActive : undefined}
          onSelectItem={(item) => selectSection(item.id)}
          onOpenSettings={() => selectSection(MENU_SETTINGS_ID)}
          onSelectAccount={() => selectSection(MENU_ACCOUNT_ID)}
          onSelectTrash={() => selectSection(MENU_TRASH_ID)}
          account={{
            name: activeAgentName,
            icon: activeAgentVisuals.icon,
            accent: activeAgentVisuals.accent,
          }}
          collapsed={menu.collapsed}
          onCollapsedChange={(c) =>
            setMenu((m) => ({
              ...m,
              collapsed: c,
              forced: c ? m.forced : false,
            }))
          }
          storageKey="sympose:shell.menu"
        />

        {/* the stage — content | editor | chat, in fixed order; overflow-hidden
            clips a panel while it is parked off to the left. `relative` anchors
            the action group at the top-right corner. `pointer-events-none` so
            an empty stretch of stage (nothing open) doesn't sit as a dead
            hit-target above the always-bottom ambient nebula — each of its
            three children claims `pointer-events-auto` back explicitly, both
            open and closed, so ordinary interaction is unaffected. */}
        <div className="relative flex min-w-0 flex-1 overflow-hidden pointer-events-none">
          {!isPhone && (
            // `top-[10.5px]` centers this 32px-tall row (size-7 buttons + a
            // 2px pad, see `<ChatActionGroup>`) on the editor toolbar's own
            // vertical center: the panel's `py-2` outer margin (8px) plus
            // half its 37px toolbar row (4px padding + a 28px button + a 1px
            // border) — 8 + 37/2 - 32/2 = 10.5. A flat `top-4` (16px) sat
            // 5.5px low against it.
            <div className="pointer-events-auto absolute top-[10.5px] right-3 z-30 flex items-center gap-2">
              <ChatActionGroup
                chatOpen={chatOpen}
                onToggleChat={toggleChat}
                className={cn(
                  "transition-[opacity,translate] duration-mode ease-mode",
                  explore
                    ? "pointer-events-none translate-x-4 opacity-0"
                    : "translate-x-0 opacity-100"
                )}
              />
              <NebulaModeToggle
                explore={explore}
                onToggle={() =>
                  setNebulaPref("interaction", explore ? "focus" : "explore")
                }
              />
            </div>
          )}

          <ContentPanel
            storageKey="sympose:shell.panel"
            scrollKey="sympose:shell.panel.scroll"
            contentClassName={
              // Settings, Agent and the Vault view all share one gutter: `p-8`
              // on desktop/tablet, `px-4 py-6` on the phone plain page, `p-6`
              // for the phone vault surface. The Agent card cancels this same
              // pad with its own negative-margin accent band (see AgentCard).
              !isPhone ? "p-8" : plainPage ? "px-4 py-6" : "p-6"
            }
            open={contentOpen}
            phone={isPhone}
            plain={plainPage}
            fill={active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID}
            flushBottomLeft={
              !isPhone && contentOpen && active === MENU_ACCOUNT_ID
            }
            header={contentHeader}
            footer={
              // Read-only Slack daemon status (ADR-082) on the left, the
              // compact light/dark switch on the right — pinned below the
              // scroll surface (not inside it) so a tall Settings list can't
              // scroll it out of reach, the same way the editor panel's own
              // "Links" row stays put under the note body.
              active === MENU_SETTINGS_ID ? (
                <div className="flex items-center justify-between gap-4">
                  <SlackStatusPill />
                  <ThemeToggle />
                </div>
              ) : undefined
            }
          >
            <div
              key={contentDisplayKey}
              className={cn(
                "flex flex-col gap-4",
                contentExitDirection
                  ? slideExitClassName(contentExitDirection)
                  : contentEnterDirection &&
                      slideEnterClassName(contentEnterDirection)
              )}
              onAnimationEnd={
                contentExitDirection ? onContentExitComplete : undefined
              }
            >
              {contentDisplayNode}
            </div>
          </ContentPanel>

          <MarkdownPanel
            storageKey="sympose:shell.md"
            path={selectedNote}
            persona={activePersona}
            onWikiLinkClick={openWikilink}
            wikiLinkSource={wikiLinkSource}
            onRenamed={(newPath) => {
              setSelectedNote(newPath)
              setVaultRefreshKey((k) => k + 1)
            }}
            onDeleted={() => {
              setSelectedNote(undefined)
              setVaultRefreshKey((k) => k + 1)
            }}
            isPinned={isPinned}
            onTogglePin={togglePin}
            preferences={editorPrefs}
            toolbarItems={toolbarItems}
            open={editorOpen}
            fill={editorFill}
            phone={isPhone}
          />

          {/* chat slot — always mounted. flex-grow:1 makes it adopt the free
              width live, frame by frame, as the editor slides in or out (a plain
              ResizeObserver never sees that — the neighbour only changes its
              margin). max-width clamps it to the same measurement: normally it
              just follows along, but for the ~320ms the chat is itself opening
              or closing (`chatToggling`) the max-width transition is armed so
              the collapse tweens between real pixel widths — collapsing to 0
              when closed, on every breakpoint, is what actually frees the width
              `editorFill` above grows the editor into; the chat panel itself is
              always faded/translated out regardless, so the toggle still reads
              as a crossfade even though the width is now moving too. Chat sits
              one z-level below the editor, so any horizontal motion starts from
              the editor's edge. */}
          <div
            ref={chatSlotRef}
            data-state={chatOpen ? "open" : "closed"}
            className={cn(
              "relative z-0 min-w-0 overflow-hidden duration-mode ease-mode",
              chatToggling
                ? "transition-[max-width,opacity,translate]"
                : "transition-[opacity,translate]",
              chatOpen
                ? "pointer-events-auto translate-y-0 opacity-100"
                : "pointer-events-none translate-y-2 opacity-0"
            )}
            style={{
              flexGrow: 1,
              flexShrink: 1,
              flexBasis: 0,
              maxWidth: chatOpen ? chatAvailW || 9999 : 0,
            }}
          >
            <ChatPanel
              compact={isPhone}
              placeholder="Ask Samantha."
              model="3.7 Flash"
            >
              {chatMessages}
            </ChatPanel>
          </div>
        </div>
      </div>
    </div>
  )
}
