import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { notify } from "@/lib/notify"
import {
  Add01Icon,
  ArrowLeft01Icon,
  ArrowRight01Icon,
  Cancel01Icon,
  File01Icon,
  Folder01Icon,
  FolderAddIcon,
  Note01Icon,
  Search01Icon,
} from "@hugeicons/core-free-icons"

import { cn, stripMdExtension } from "@/lib/utils"
import {
  getCookie,
  getCookieBool,
  setCookie,
  setCookieBool,
  vaultScopedKey,
} from "@/lib/cookies"
import { useBreakpoint } from "@/lib/use-breakpoint"
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
import { useRecentNotes } from "@/lib/use-recent-notes"
import { useVaultScopedState } from "@/lib/use-vault-scoped-state"
import { useNotificationPreferences } from "@/lib/use-notification-preferences"
import { useNebulaPreferences } from "@/lib/use-nebula-preferences"
import { useNebulaGraph } from "@/lib/use-nebula-graph"
import { useBrandMarkLabel } from "@/lib/use-brand-mark-preference"
import {
  addVault,
  fetchVaults,
  setActiveVault,
  type VaultsState,
} from "@/lib/vaults-api"
import {
  fetchPersonas,
  resolvePersonaVisuals,
  type LivePersona,
} from "@/lib/personas"
import { fetchVaultTree } from "@/lib/vault-tree-api"
import { searchVault, type VaultSearchResult } from "@/lib/vault-search-api"
import {
  createVaultNote,
  createVaultFolder,
  moveVaultNote,
} from "@/lib/vault-note-api"
import { isNoteDrag, readNoteDrag } from "@/lib/vault-drag"
import { findNoteByWikilink } from "@/lib/find-note-by-wikilink"
import { findNodeByPath } from "@/lib/find-node-by-path"
import { matchWikilinkTargets } from "@/lib/vault-wikilink-completions"
import { matchTagTargets } from "@/lib/vault-tag-completions"
import { resolveEmbed } from "@/lib/resolve-embed"
import { VAULT_FOLDERS } from "@/lib/vault-folders"
import {
  PersonaCard,
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
  RecentNotesPreferencesSection,
  ThemeToggle,
  TopBar,
  TrashList,
  VaultTree,
  WorkspaceSection,
  collectFolderPaths,
  filterTreeByQuery,
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
  [MENU_ACCOUNT_ID]: "Persona",
  [MENU_TRASH_ID]: "Bin",
}

const AUTO_COLLAPSE_COOKIE = "sympose:pref.autoCollapseMenu"
const SECTION_COOKIE = "sympose:shell.section"
const RAIL_COOKIE = "sympose:shell.rail"
const NOTE_COOKIE = "sympose:shell.note"
function readSelectedNote(raw: string | null): string | undefined {
  return raw || undefined
}
function serializeSelectedNote(path: string | undefined): string {
  return path ?? ""
}
/** The note a vault switch/add should open to, read straight from that
 *  vault's own scoped cookie — `handleSwitchVault`/`handleAddVault` call
 *  this directly (bypassing `useVaultScopedState`'s own, one-render-later
 *  reseed) so `<MarkdownPanel>` never sees the new vault paired with the
 *  outgoing vault's still-selected note. */
function resolveSelectedNoteFor(vaultPath: string | null): string | undefined {
  return readSelectedNote(getCookie(vaultScopedKey(NOTE_COOKIE, vaultPath)))
}
/** How long the search field waits after the last keystroke before firing
 *  `/api/vault/search`. */
const SEARCH_DEBOUNCE_MS = 250
/** A stable reference for "no search results yet/stale" — see its use
 *  below for why a fresh `[]` literal per render isn't good enough. */
const EMPTY_SEARCH_RESULTS: VaultSearchResult[] = []

/**
 * One row in the search results supplement (in-folder content matches, or
 * beyond-folder matches of any type) — shared so the two sections render
 * identically instead of drifting apart as separate copies. `label` is the
 * bare filename for an in-folder row, the full vault-relative path for a
 * beyond-folder one (folder context matters there, since the row isn't
 * nested under anything that already shows it).
 */
function SearchResultRow({
  label,
  detail,
  onSelect,
}: {
  label: string
  detail?: React.ReactNode
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="group/result flex w-full flex-col items-start gap-0.5 py-1 text-left focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <span className="flex w-full items-start gap-1.5 text-sm text-entity/85 transition-colors group-hover/result:text-entity">
        <HugeiconsIcon
          icon={Note01Icon}
          className="mt-0.5 size-3.5 shrink-0 text-fg-muted"
        />
        <span className="line-clamp-2 min-w-0 flex-1">{label}</span>
      </span>
      {detail && (
        <span className="flex w-full min-w-0 items-center gap-1 pl-5 text-xs text-fg-muted">
          {detail}
        </span>
      )}
    </button>
  )
}

/**
 * `SearchResultRow`'s `detail` line for one match — a content match's line
 * number and snippet, separated by a chevron; any other match type's
 * snippet alone (it's already self-descriptive: `#tag` for a tag match,
 * a title-line preview for a title match — no line number applies).
 * Shared by both search-result sections so they can't drift apart into
 * two slightly different renderings of the same data.
 */
function searchMatchDetail(r: VaultSearchResult): React.ReactNode {
  if (!r.snippet) return undefined
  if (r.match_type !== "content") {
    return <span className="truncate">{r.snippet}</span>
  }
  return (
    <>
      <span className="shrink-0">line {r.line_no}</span>
      <HugeiconsIcon icon={ArrowRight01Icon} className="size-3 shrink-0" />
      <span className="truncate">{r.snippet}</span>
    </>
  )
}

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
  // back/forward toolbar buttons. Stack and cursor live together in one
  // state value so the buttons' disabled state is always current — no
  // ref-plus-forced-rerender needed. `navigatingHistory` suppresses the
  // effect's own push when `active` changes because a back/forward click
  // set it.
  const [history, setHistory] = React.useState(() => ({
    stack: [active],
    index: 0,
  }))
  const navigatingHistory = React.useRef(false)
  React.useEffect(() => {
    if (navigatingHistory.current) {
      navigatingHistory.current = false
      return
    }
    setHistory((prev) => {
      if (prev.stack[prev.index] === active) return prev
      const stack = [...prev.stack.slice(0, prev.index + 1), active]
      return { stack, index: stack.length - 1 }
    })
  }, [active])
  const canGoBack = history.index > 0
  const canGoForward = history.index < history.stack.length - 1
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
    setActive(history.stack[history.index - 1])
    setHistory((prev) => ({ ...prev, index: prev.index - 1 }))
  }
  const goForward = () => {
    if (!canGoForward) return
    navigatingHistory.current = true
    setContentDirection("forward")
    setActive(history.stack[history.index + 1])
    setHistory((prev) => ({ ...prev, index: prev.index + 1 }))
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
  const beforeVault = React.useRef<"editor" | null>(null)

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
    beforeVault.current = panels.isOpen("editor") ? "editor" : null
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
    // On phone, jumping to Settings / Persona from the TopBar slides the menu away
    // (folder picks keep it, so its highlight stays visible next to the panel).
    if (isPhone && (id === MENU_SETTINGS_ID || id === MENU_ACCOUNT_ID)) {
      setMenuShown(false)
    }
    // A root note row (README.md) also selects it in the tree.
    if (noteIds.has(id)) selectNote(id)
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

  const contentOpen = panels.isOpen("content")
  const editorOpen = panels.isOpen("editor")
  // Editor grows into the content panel's area when that's closed — but only
  // on the smaller breakpoints, where screen room is scarce. On desktop the
  // editor keeps its dragged, cookie-persisted width and the resize handle
  // stays live so that width is the user's to set. Content never grows — it
  // is navigation, it keeps its dragged width even when alone.
  const editorFill = editorOpen && breakpoint !== "desktop"

  // Persona picker — the active persona is client state (a cookie), and the
  // roster is fetched once. Both feed the `MENU_ACCOUNT_ID` panel; the handle
  // is lifted here so the vault panels can scope their `?persona=` calls to it
  // once those land.
  const [activePersona, setActivePersona] = useActivePersona()
  const [editorPrefs, setEditorPref] = useEditorPreferences()
  const [toolbarItems, setToolbarItems] = useToolbarItems()

  // The workspace switcher (ADR 003/004) — every configured vault plus which
  // one is active. Declared before `usePinnedNotes`/`useRecentNotes` below,
  // which key their own cookies off `vaultsState.active` so pinned/recent
  // notes don't leak across a vault switch. Bumping `vaultRefreshKey` after
  // a switch (declared further down, alongside the tree fetch it already
  // drives) re-pulls the tree, the nebula graph, and any live search against
  // the newly active vault.
  const [vaultsState, setVaultsState] = React.useState<VaultsState>({
    vaults: [],
    active: null,
  })
  React.useEffect(() => {
    let alive = true
    fetchVaults().then((state) => {
      if (alive) setVaultsState(state)
    })
    return () => {
      alive = false
    }
  }, [])
  const [brandMarkLabel, setBrandMarkLabel] = useBrandMarkLabel()

  const { isPinned, togglePin, unpinMany, pinnedPaths } = usePinnedNotes(
    vaultsState.active
  )
  const {
    recentPaths,
    shownCount,
    setShownCount,
    enabled: recentsEnabled,
    setEnabled: setRecentsEnabled,
    recordVisit,
    removeFromRecents,
    clearRecents,
  } = useRecentNotes(vaultsState.active)
  const [notifyPrefs, setNotifyPref] = useNotificationPreferences()
  const [nebulaPrefs, setNebulaPref] = useNebulaPreferences()
  // Bumped after a note is created, or the active vault is switched, to
  // re-pull the tree, the nebula graph, and any live search so they follow
  // without a persona switch.
  const [vaultRefreshKey, setVaultRefreshKey] = React.useState(0)
  // Lifted here (not called inside `<AmbientNebula>`) so the one fetch also
  // backs `tagSource` below — the ambient layer and the editor's `#tag`
  // autocomplete share the same master graph instead of each hitting
  // `GET /api/vault/graph` on its own. Re-fetches when `vaultRefreshKey`
  // bumps, since the graph is vault-scoped, not persona-scoped.
  const { graph: nebulaGraph, source: nebulaGraphSource } = useNebulaGraph(
    vaultRefreshKey,
    vaultsState.active
  )
  const explore = nebulaPrefs.interaction === "explore"

  // Explore auto-collapses the stage panels — content, editor —
  // so the whole canvas is click-through to the nebula underneath; the trip
  // back to Focus reopens exactly what was showing before, oldest-first,
  // the same order `usePanels`
  // itself keeps. A ref (not a `panels` dependency) reads the live panel
  // handle so this effect only fires on an actual mode change, not on every
  // panel-order write `usePanels` makes.
  const panelsRef = React.useRef(panels)
  React.useEffect(() => {
    panelsRef.current = panels
  })
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
      ? window.requestIdleCallback(() => setNebulaReady(true), {
          timeout: 2000,
        })
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
  // Self-heal a persona cookie left over from a roster that has since
  // shrunk (e.g. a persona removed as a shipped default) — otherwise the
  // account row is stuck showing a raw, unresolvable handle forever, since
  // nothing else ever clears a stale cookie value on its own.
  React.useEffect(() => {
    if (personas.length === 0) return
    if (personas.some((p) => p.handle === activePersona)) return
    setActivePersona(personas.find((p) => p.isDefault)?.handle ?? personas[0].handle)
  }, [personas, activePersona, setActivePersona])

  // Vault browser — the persona-scoped directory tree (GET /api/vault/tree),
  // re-fetched whenever the active persona changes so the sandbox follows the
  // switcher. Every folder row opens the same panel: the whole scoped tree.
  const [vaultTree, setVaultTree] = React.useState<VaultNode[]>([])
  // The vault root's display name (master vault directory basename) — the
  // leading segment of the editor's read-mode breadcrumb. `null` until the
  // first `/api/vault/tree` response lands, or permanently if the backend
  // has no `VAULT_PATHS` configured.
  const [vaultName, setVaultName] = React.useState<string | null>(null)
  // Persisted across a refresh so the editor reopens on the same note instead
  // of coming back empty — same cookie convention as `active` (SECTION_COOKIE).
  // Scoped per vault and reseeded on a vault switch via `useVaultScopedState`
  // (see its doc comment) — a note path is a reference into one vault's
  // content, meaningless in another, so each vault remembers its own
  // last-open note rather than one shared globally.
  const [selectedNote, setSelectedNote] = useVaultScopedState(
    NOTE_COOKIE,
    vaultsState.active,
    readSelectedNote,
    serializeSelectedNote
  )
  // A note genuinely opened by the user (row click, wikilink, search result,
  // newly created) — as opposed to `setSelectedNote` alone, used to just
  // remap the still-open note's path after a rename or clear it after a
  // delete, neither of which is a new "visit" worth recording.
  const selectNote = React.useCallback(
    (path: string) => {
      setSelectedNote(path)
      recordVisit(path)
    },
    [recordVisit, setSelectedNote]
  )
  // Nebula node ids are the note's full vault-relative path, matching
  // `selectedNote` exactly — `vault_manifest_build._node()` deliberately
  // uses the full path rather than the bare filename stem, "so two notes
  // named the same thing in different folders don't collide on one node"
  // (its own comment). `_stem()` still exists in that module, but only for
  // resolving bare `[[wikilink]]` targets, not for node identity — so
  // whichever note becomes active in the content panel can drive the
  // ambient nebula's focus/highlight (see `AmbientNebula`'s
  // `activeNoteId`) with no transformation needed at all.
  const activeNoteId = selectedNote
  // `null` = no create-input open; otherwise which kind is being named, with
  // its current typed value in `createName`.
  const [pendingCreate, setPendingCreate] = React.useState<
    "note" | "folder" | null
  >(null)
  const [createName, setCreateName] = React.useState("")
  const [creating, setCreating] = React.useState(false)
  // Filters `panelNodes` client-side (name/path substring match) rather than
  // round-tripping to the backend — round-trip frugality, and the tree is
  // already fetched. Only scoped to the vault-folder listing, not Bin /
  // Settings / Persona, which the same toolbar field sits above but don't read
  // it.
  const [vaultSearch, setVaultSearch] = React.useState("")
  // Search, like new note/folder, is an icon-toggled field rather than
  // always-visible — collapsed by default, closing it also clears the query
  // so the filtered view resets.
  const [searchOpen, setSearchOpen] = React.useState(false)
  const closeCreate = () => {
    setPendingCreate(null)
    setCreateName("")
  }
  const closeSearch = () => {
    setSearchOpen(false)
    setVaultSearch("")
  }
  // Toggling any of these fields open moves focus into it — the shared input
  // element persists across the "note"/"folder" switch (no remount), so a
  // plain `autoFocus` prop only fires once; re-focusing on every open has to
  // go through an effect instead.
  const searchInputRef = React.useRef<HTMLInputElement>(null)
  const noteInputRef = React.useRef<HTMLInputElement>(null)
  const folderInputRef = React.useRef<HTMLInputElement>(null)
  React.useEffect(() => {
    if (searchOpen) searchInputRef.current?.focus()
  }, [searchOpen])
  React.useEffect(() => {
    if (pendingCreate === "note") noteInputRef.current?.focus()
    else if (pendingCreate === "folder") folderInputRef.current?.focus()
  }, [pendingCreate])
  // The vault panel shows the bin instead of the tree when the main-menu
  // Bin row is the active section.
  const trashView = active === MENU_TRASH_ID
  React.useEffect(() => {
    let alive = true
    fetchVaultTree(activePersona).then(({ tree, vaultName }) => {
      if (!alive) return
      setVaultTree(tree)
      setVaultName(vaultName)
    })
    return () => {
      alive = false
    }
  }, [activePersona, vaultRefreshKey])

  // Workspace switcher: persist the choice, then re-pull everything scoped
  // to "the active vault" via the same `vaultRefreshKey` bump a note create
  // already uses.
  const handleSwitchVault = React.useCallback(
    async (path: string) => {
      const res = await setActiveVault(path)
      if (res.ok) {
        setVaultsState(res.state)
        // Resolved synchronously, in the same batch as `setVaultsState`
        // above, rather than left to `useVaultScopedState`'s own reseed
        // effect — otherwise `<MarkdownPanel>` sees the new `vaultPath` one
        // render before `selectedNote` catches up, and fetches the outgoing
        // vault's note path against the already-switched backend.
        setSelectedNote(
          resolveSelectedNoteFor(res.state.active)
        )
        setVaultRefreshKey((k) => k + 1)
        const name = res.state.vaults.find((v) => v.path === path)?.name
        notify.success(name ? `Switched to ${name}` : "Vault switched")
      } else {
        notify.error(res.error)
      }
    },
    [setVaultsState, setSelectedNote, setVaultRefreshKey]
  )

  // Workspace switcher's add-path input (ADR 004) — adds and activates in
  // one round trip. Resolves `false` on failure so the switcher's input
  // keeps the typed path instead of clearing it.
  const handleAddVault = React.useCallback(
    async (path: string) => {
      const res = await addVault(path)
      if (res.ok) {
        setVaultsState(res.state)
        // Same synchronous resolution as `handleSwitchVault` above, and for
        // the same reason — this also activates a vault in one round trip.
        setSelectedNote(
          resolveSelectedNoteFor(res.state.active)
        )
        setVaultRefreshKey((k) => k + 1)
        const name = res.state.vaults.find((v) => v.path === res.state.active)?.name
        notify.success(name ? `Added ${name}` : "Vault added")
        return true
      }
      notify.error(res.error)
      return false
    },
    [setVaultsState, setSelectedNote, setVaultRefreshKey]
  )

  // Main menu = the vault's surface (top-level folders + root notes like
  // README.md), in the tree's own order, with curated icons where the folder
  // name is known. The two footer sentinels (Settings, Persona) stay separate.
  const menuItems: MainMenuItem[] = React.useMemo(
    () =>
      vaultTree.map((node) => ({
        id: node.path,
        label:
          editorPrefs.hideExtension === "on"
            ? stripMdExtension(node.name)
            : node.name,
        icon: menuIconFor(node),
        type: node.type,
      })),
    [vaultTree, editorPrefs.hideExtension]
  )
  const noteIds = React.useMemo(
    () => new Set(vaultTree.filter((n) => n.type === "note").map((n) => n.path)),
    [vaultTree]
  )

  // A `[[wikilink]]` clicked inside the open note — resolve it against the
  // full (nested) tree by filename stem and jump the editor there. Silently
  // does nothing for a target the sandboxed tree doesn't contain.
  const openWikilink = (target: string) => {
    const match = findNoteByWikilink(vaultTree, target)
    if (match) {
      selectNote(match.path)
      panels.open("editor")
    }
  }

  // stylo's `wikiLinkSource` (>=0.7.0) is read once, at mount — so the
  // function identity handed to `<Stylo>` must stay stable across a tree
  // refetch (new persona, new note create) rather than being rebuilt
  // every render. A ref carries the live tree; the callback itself never
  // changes.
  const vaultTreeRef = React.useRef(vaultTree)
  React.useEffect(() => {
    vaultTreeRef.current = vaultTree
  })
  const wikiLinkSource = React.useCallback(
    (query: string) => matchWikilinkTargets(vaultTreeRef.current, query),
    []
  )

  // stylo's `tagSource` (>=0.12.0) is the same read-once-at-mount contract as
  // `wikiLinkSource` above — a ref carries the live graph, the callback never
  // changes. Candidates come from `buildMasterGraph`'s pre-indexed tag hubs
  // (`nebula-graph.ts`), not a separate client-side vault scan.
  const nebulaGraphRef = React.useRef(nebulaGraph)
  React.useEffect(() => {
    nebulaGraphRef.current = nebulaGraph
  })
  const tagSource = React.useCallback(
    (query: string) => matchTagTargets(nebulaGraphRef.current, query),
    []
  )

  // stylo's `embedSource` (>=0.13.x) resolves `![[ref]]` transclusion —
  // reactive in `preview` but read once, at mount, on the in-place canvas
  // (same contract as `wikiLinkSource`/`tagSource` above), so it needs the
  // same ref-plus-stable-callback shape. `activePersona` gets its own ref
  // here (unlike `tagSource`'s `nebulaGraphRef`) since a persona switch
  // alone doesn't remount `<Stylo>` — see `resolve-embed.tsx` for what
  // actually resolves image vs. note refs.
  const activePersonaRef = React.useRef(activePersona)
  React.useEffect(() => {
    activePersonaRef.current = activePersona
  })
  const embedSource = React.useCallback(
    (ref: string) => resolveEmbed(vaultTreeRef.current, activePersonaRef.current, ref),
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
  const panelNodes: VaultNode[] = React.useMemo(
    () =>
      activeNode?.type === "folder"
        ? (activeNode.children ?? [])
        : activeNode
          ? [activeNode]
          : [],
    [activeNode]
  )

  // Client-side filter within the folder currently in view — round-trip
  // frugality, the tree is already fetched. Browsing (no query) shows just
  // the folder in view via `panelNodes`, unfiltered.
  const vaultSearchQuery = vaultSearch.trim()
  const searchedPanelNodes = React.useMemo(
    () =>
      vaultSearchQuery
        ? filterTreeByQuery(panelNodes, vaultSearchQuery)
        : panelNodes,
    [panelNodes, vaultSearchQuery]
  )

  // Backend search — body text isn't in the already-fetched tree, so this
  // can't be done client-side like the name/tag/link filter above. One
  // debounced, whole-persona-scope round trip to `/api/vault/search` (never
  // narrowed to a folder — see that module's own docstring for why) covers
  // both result tiers below: a note whose path falls under the folder
  // currently in view supplements `searchedPanelNodes` (only its `content`
  // matches are new there — title/tag hits *inside* the folder are already
  // surfaced instantly by that client-side filter); everything else is the
  // beyond-folder tier, where every match type is kept, since nothing else
  // surfaces a title or tag hit on a note living in a different folder.
  //
  // Stored keyed to the query/persona/vault it was actually fetched for,
  // rather than cleared via effect-driven setState, so retyping the query
  // (or switching personas, or switching the active vault) can never
  // display a stale response — a fetch whose key no longer matches the
  // current one is simply never read, in whatever order responses arrive.
  // Switching which folder is in view needs no new fetch at all — both
  // tiers below just re-derive from whatever's already in memory.
  const searchKey = `${vaultSearchQuery}\u0000${activePersona}\u0000${vaultRefreshKey}`
  const [searchState, setSearchState] = React.useState<{
    key: string
    results: VaultSearchResult[]
  }>({ key: "", results: [] })
  React.useEffect(() => {
    if (!vaultSearchQuery || isSentinel) return
    const key = searchKey
    const controller = new AbortController()
    const t = setTimeout(() => {
      searchVault(vaultSearchQuery, activePersona, controller.signal).then(
        (results) => {
          if (!controller.signal.aborted) setSearchState({ key, results })
        }
      )
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      clearTimeout(t)
      controller.abort()
    }
  }, [vaultSearchQuery, isSentinel, activePersona, searchKey])
  // A stable empty-array reference, not a fresh `[]` literal each render —
  // otherwise the memos below would see a "changed" dependency on every
  // render while a search is inactive/stale, defeating their memoization.
  const searchResults =
    searchState.key === searchKey ? searchState.results : EMPTY_SEARCH_RESULTS

  const contentMatches = React.useMemo(
    () =>
      searchResults.filter(
        (r) =>
          r.match_type === "content" &&
          (r.rel_path === resolvedActive || r.rel_path.startsWith(`${resolvedActive}/`))
      ),
    [searchResults, resolvedActive]
  )
  const beyondFolderMatches = React.useMemo(
    () =>
      searchResults.filter(
        (r) =>
          r.rel_path !== resolvedActive && !r.rel_path.startsWith(`${resolvedActive}/`)
      ),
    [searchResults, resolvedActive]
  )

  // Pinned is scoped to the current *root* folder (the top-level menu entry
  // — `activeNode` itself, since the content panel never changes which
  // top-level entry it's showing just because a nested subfolder inside it
  // is expanded/collapsed) — not vault-wide, and not the immediate parent
  // folder either: a note pinned anywhere under "Daily" shows while browsing
  // Daily regardless of how deep it lives, but never mixes in with "Code"'s
  // own pinned notes. A stale path (renamed/deleted since) or anything that
  // resolves to a folder is silently dropped rather than shown broken.
  const activeRootFolder =
    activeNode?.type === "folder" ? activeNode : undefined
  const pinnedNodes = React.useMemo(
    () =>
      activeRootFolder
        ? pinnedPaths
            .filter((path) => path.startsWith(`${activeRootFolder.path}/`))
            .map((path) => findNodeByPath(vaultTree, path))
            .filter((node): node is VaultNode => node?.type === "note")
        : [],
    [activeRootFolder, pinnedPaths, vaultTree]
  )
  // A pinned row shown outside the folder it lives in only needs its full
  // path spelled out when that root folder actually has nested subfolders
  // (e.g. Daily's year/month structure) — a flat root folder's own bare
  // filenames are already unambiguous.
  const pinnedShowPath = React.useMemo(
    () => activeRootFolder?.children?.some((n) => n.type === "folder") ?? false,
    [activeRootFolder]
  )

  // Recent, unlike Pinned, is genuinely vault-wide — each path is
  // resolved against the *full* tree regardless of which folder is
  // currently in view, so a note surfaces there no matter where it lives.
  const recentNodes = React.useMemo(
    () =>
      recentPaths
        .map((path) => findNodeByPath(vaultTree, path))
        .filter((node): node is VaultNode => node?.type === "note"),
    [recentPaths, vaultTree]
  )
  // Only gates the "this folder is empty" message — while searching, an
  // empty *current* folder shouldn't hide vault-wide matches found elsewhere.
  const panelEmpty = !vaultSearchQuery && panelNodes.length === 0

  const activeLabel = SECTION_LABELS[resolvedActive] ?? resolvedActive

  // Highlight state for the "drop here to move to the root of the folder
  // currently in view" target below — the folder heading itself, since
  // `<VaultTree>` only ever renders *that* folder's own subtree (its
  // children), never a row for the folder itself to drop onto.
  const [dragOverRootHeading, setDragOverRootHeading] = React.useState(false)

  // Drag-and-drop a note onto a folder row — either a subfolder inside the
  // tree currently in view, or a root folder in the main menu.
  // Both drop surfaces hand this the same (path, destFolder) pair; the
  // no-op case (dropped back on its own folder) resolves without a fetch
  // inside `moveVaultNote` itself, so nothing here needs to guard it.
  const moveNote = async (path: string, destFolder: string) => {
    const res = await moveVaultNote(path, destFolder, activePersona)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    if (res.path === path) return
    setVaultRefreshKey((k) => k + 1)
    if (selectedNote === path) setSelectedNote(res.path)
    notify.success(res.detail)
  }

  // Shared row callbacks for both `<VaultTree>` instances below (the folder
  // in view, and the "beyond {activeLabel}" tier) — identical behavior
  // either way, just spread onto each with its own `nodes`/`key`.
  const vaultTreeActions = {
    selectedPath: selectedNote,
    onSelect: (node: VaultNode) => {
      // Picking a note always brings the editor forward — same as creating
      // one (`onCreated`) or following a wikilink.
      selectNote(node.path)
      panels.open("editor")
    },
    persona: activePersona,
    onRenamed: (oldPath: string, newPath: string) => {
      setVaultRefreshKey((k) => k + 1)
      if (selectedNote === oldPath) setSelectedNote(newPath)
    },
    onDeleted: (path: string) => {
      setVaultRefreshKey((k) => k + 1)
      // `path` is a note's own path for a note-row delete, or a folder's
      // path when a whole folder went to the bin — either way,
      // close the editor if it was showing something that just moved.
      if (selectedNote === path || selectedNote?.startsWith(`${path}/`)) {
        setSelectedNote(undefined)
      }
    },
    onCreated: (path: string) => {
      setVaultRefreshKey((k) => k + 1)
      selectNote(path)
      panels.open("editor")
    },
    isPinned,
    onTogglePin: togglePin,
    onMoveNote: moveNote,
    onUnpinAll: unpinMany,
    onRemoveFromRecents: removeFromRecents,
    onClearRecents: clearRecents,
    hideExtension: editorPrefs.hideExtension === "on",
  }

  // Create a note or folder in the folder currently in view (or the vault
  // root when a root note is the active surface). A new note opens in the
  // editor; a new folder just refreshes the tree.
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
      selectNote(`${target}.md`)
      panels.open("editor")
    }
    notify.success(`Created ${name}`)
  }

  // The main-menu account row wears the active persona's name, icon and accent.
  const activePersonaName =
    personas.find((p) => p.handle === activePersona)?.name ?? activePersona
  const activePersonaVisuals = resolvePersonaVisuals(activePersona)
  // The brand-mark wordmark: the fixed product name, or the active vault's
  // name when the Workspace setting asks for it (falling back to the name
  // while the vault name hasn't loaded yet, or there's none configured).
  const vaultLabel =
    brandMarkLabel === "vault" ? (vaultName ?? "Sympose") : "Sympose"
  // Phone: the rail only shows alongside the content panel — the two are one
  // view. Desktop / tablet: always shown.
  const menuOpen = isPhone ? menuShown && contentOpen : true
  // Settings / Persona on phone are plain destination pages, styled off the chat
  // panel (same background, same gutter) rather than the vault content surface.
  const plainPage =
    isPhone && (active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID)

  // The panel-wide toolbar (back/forward, new note/folder) — pinned to the
  // content panel's own top edge via `<ContentPanel header>`, mirroring the
  // editor toolbar's chrome exactly rather than sitting inline with the
  // section title. Shown on every surface (vault folders, Bin, Settings,
  // Persona) so back/forward always works; new note/folder only make sense
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
      <div className="flex items-center gap-0.5">
        <div
          className={cn(
            // `h-7` on the wrapper (not just the input) is load-bearing: `w-0`
            // only clips width, so an unconstrained-height input still pushes
            // the whole toolbar row taller by its own natural line-height even
            // while invisibly zero-width. Fixing the wrapper's height to match
            // the buttons keeps the row at their 28px regardless.
            "h-7 overflow-hidden rounded-[calc(var(--radius-md)-3px)] transition-[width] duration-snappy ease-snappy",
            searchOpen ? "w-40" : "w-0"
          )}
        >
          <div className="relative h-7 w-full">
            <input
              ref={searchInputRef}
              type="text"
              value={vaultSearch}
              onChange={(e) => setVaultSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") closeSearch()
              }}
              // A blur while the field still holds a query keeps it open —
              // otherwise focusing the results below (or anything else) would
              // wipe the query out from under the list it's filtering.
              // Empty-field blur still auto-hides, same as new note/folder.
              onBlur={() => {
                if (!vaultSearch) closeSearch()
              }}
              placeholder="Search vault"
              aria-label="Search vault"
              tabIndex={searchOpen ? 0 : -1}
              // Sized off stylo's own `.stylo-search-field` (the find/replace
              // input this was modeled on): `radius-md - 3px`, not the toolbar's
              // plain `rounded-md`, and its 11px `font-size` (sympose's own
              // override of stylo's field, see index.css) — matching `text-sm`
              // here read visibly larger and rounder than that reference field.
              // New note/folder share this exact styling for visual parity.
              className="h-7 w-full rounded-[calc(var(--radius-md)-3px)] border border-border bg-background py-1 pr-6 pl-2 text-[0.6875rem] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            />
            {vaultSearch && (
              <button
                type="button"
                // Runs before the input's blur, so the clear can't be read as
                // "field went empty because it lost focus" and re-hide it.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setVaultSearch("")
                  searchInputRef.current?.focus()
                }}
                aria-label="Clear search"
                className="absolute top-1/2 right-1.5 grid size-3.5 -translate-y-1/2 place-items-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
              >
                <HugeiconsIcon icon={Cancel01Icon} className="size-3" />
              </button>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            if (searchOpen) closeSearch()
            else setSearchOpen(true)
          }}
          aria-label="Search vault"
          aria-pressed={searchOpen}
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground aria-pressed:text-foreground"
        >
          <HugeiconsIcon icon={Search01Icon} className="size-4" />
        </button>
        {!isSentinel && (
          <>
            <div
              className={cn(
                "h-7 overflow-hidden rounded-[calc(var(--radius-md)-3px)] transition-[width] duration-snappy ease-snappy",
                pendingCreate === "note" ? "w-40" : "w-0"
              )}
            >
              <input
                ref={noteInputRef}
                value={pendingCreate === "note" ? createName : ""}
                disabled={creating}
                onChange={(e) => setCreateName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submitCreate()
                  else if (e.key === "Escape") closeCreate()
                }}
                onBlur={closeCreate}
                placeholder="Filename"
                aria-label="New note filename"
                tabIndex={pendingCreate === "note" ? 0 : -1}
                className="h-7 w-full rounded-[calc(var(--radius-md)-3px)] border border-border bg-background px-2 text-[0.6875rem] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
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
            <div
              className={cn(
                "h-7 overflow-hidden rounded-[calc(var(--radius-md)-3px)] transition-[width] duration-snappy ease-snappy",
                pendingCreate === "folder" ? "w-40" : "w-0"
              )}
            >
              <input
                ref={folderInputRef}
                value={pendingCreate === "folder" ? createName : ""}
                disabled={creating}
                onChange={(e) => setCreateName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submitCreate()
                  else if (e.key === "Escape") closeCreate()
                }}
                onBlur={closeCreate}
                placeholder="Folder name"
                aria-label="New folder name"
                tabIndex={pendingCreate === "folder" ? 0 : -1}
                className="h-7 w-full rounded-[calc(var(--radius-md)-3px)] border border-border bg-background px-2 text-[0.6875rem] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
              />
            </div>
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
          </>
        )}
      </div>
    </div>
  )

  const contentBody =
    active === MENU_ACCOUNT_ID ? (
      <PersonaCard
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
        <WorkspaceSection
          brandMarkLabel={brandMarkLabel}
          setBrandMarkLabel={setBrandMarkLabel}
        />
        <EditorPreferencesSection
          prefs={editorPrefs}
          setPref={setEditorPref}
          toolbarItems={toolbarItems}
          onToolbarItemsChange={setToolbarItems}
        />
        <NotificationsSection prefs={notifyPrefs} setPref={setNotifyPref} />
        <NebulaAppearanceSection prefs={nebulaPrefs} setPref={setNebulaPref} />
        <RecentNotesPreferencesSection
          enabled={recentsEnabled}
          setEnabled={setRecentsEnabled}
          shownCount={shownCount}
          setShownCount={setShownCount}
        />
      </ControlSectionsProvider>
    ) : (
      <div className="flex flex-col gap-2">
        <h2
          className={cn(
            "-mx-2 min-w-0 truncate rounded-md px-2 font-heading text-2xl font-semibold text-fg-strong transition-colors",
            dragOverRootHeading &&
              "bg-accent/60 ring-1 ring-inset ring-brand/60"
          )}
          onDragOver={
            activeRootFolder
              ? (e) => {
                  if (!isNoteDrag(e)) return
                  e.preventDefault()
                  e.dataTransfer.dropEffect = "move"
                }
              : undefined
          }
          onDragEnter={
            activeRootFolder
              ? (e) => {
                  if (!isNoteDrag(e)) return
                  setDragOverRootHeading(true)
                }
              : undefined
          }
          onDragLeave={
            activeRootFolder
              ? () => setDragOverRootHeading(false)
              : undefined
          }
          onDrop={
            activeRootFolder
              ? (e) => {
                  const path = readNoteDrag(e)
                  if (!path) return
                  e.preventDefault()
                  setDragOverRootHeading(false)
                  moveNote(path, activeRootFolder.path)
                }
              : undefined
          }
        >
          {trashView ? "Bin" : activeLabel || "Vault"}
        </h2>
        {trashView ? (
          <TrashList
            persona={activePersona}
            refreshKey={vaultRefreshKey}
            onRestored={() => setVaultRefreshKey((k) => k + 1)}
          />
        ) : vaultTree.length === 0 ? (
          <p className="text-sm text-fg-muted">
            No notes in scope — check that the dashboard API is reachable
            and the persona has vault folders.
          </p>
        ) : (
          <>
            {panelEmpty && (
              <p className="text-sm text-fg-muted">This folder is empty.</p>
            )}
            {!panelEmpty &&
              vaultSearchQuery &&
              searchedPanelNodes.length === 0 &&
              contentMatches.length === 0 && (
                <p className="text-sm text-fg-muted">
                  No matches for "{vaultSearchQuery}" in {activeLabel}.
                </p>
              )}
            {(searchedPanelNodes.length > 0 ||
              pinnedNodes.length > 0 ||
              recentNodes.length > 0) && (
              <VaultTree
                // Remounts between browsing and searching so a search's
                // matching folders start expanded (`defaultExpanded`, a
                // one-time seed) without disturbing the persisted
                // expanded-folders cookie used the rest of the time.
                key={vaultSearchQuery ? "search" : "browse"}
                nodes={searchedPanelNodes}
                pinnedNodes={pinnedNodes}
                pinnedShowPath={pinnedShowPath}
                recentNodes={recentNodes}
                defaultExpanded={
                  vaultSearchQuery
                    ? collectFolderPaths(searchedPanelNodes)
                    : []
                }
                storageKey={
                  vaultSearchQuery ? undefined : "sympose:vault.expanded"
                }
                {...vaultTreeActions}
              />
            )}
            {vaultSearchQuery && contentMatches.length > 0 && (
              <div className="mt-4">
                <p className="mb-1.5 text-xs font-medium text-fg-muted">
                  Also found in {activeLabel}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {contentMatches.map((r) => (
                    <li key={r.rel_path}>
                      <SearchResultRow
                        label={stripMdExtension(r.file_name)}
                        onSelect={() => {
                          selectNote(r.rel_path)
                          panels.open("editor")
                        }}
                        detail={searchMatchDetail(r)}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {vaultSearchQuery && beyondFolderMatches.length > 0 && (
              <div className="mt-4">
                <p className="mb-1.5 text-xs font-medium text-fg-muted">
                  {beyondFolderMatches.length} match
                  {beyondFolderMatches.length === 1 ? "" : "es"} beyond{" "}
                  {activeLabel}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {beyondFolderMatches.map((r) => (
                    <li key={r.rel_path}>
                      <SearchResultRow
                        label={stripMdExtension(r.rel_path)}
                        onSelect={() => {
                          selectNote(r.rel_path)
                          panels.open("editor")
                        }}
                        detail={searchMatchDetail(r)}
                      />
                    </li>
                  ))}
                </ul>
              </div>
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

  return (
    <div
      ref={rootRef}
      className={cn(
        "flex h-svh w-full overflow-hidden bg-background text-foreground",
        isPhone && "flex-col"
      )}
      // Feeds `.sy-frosted-panel` — the content and editor panels only
      // (blur dropped). `off` (the default: opacity 1) →
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
            graph={nebulaGraph}
            source={nebulaGraphSource}
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
          menuOpen={menuShown}
          onToggleMenu={revealMenu}
          settingsActive={contentOpen && active === MENU_SETTINGS_ID}
          onSettings={() => selectSection(MENU_SETTINGS_ID)}
          accountActive={contentOpen && active === MENU_ACCOUNT_ID}
          onAccount={() => selectSection(MENU_ACCOUNT_ID)}
          vaults={vaultsState.vaults}
          activeVault={vaultsState.active}
          onSwitchVault={handleSwitchVault}
          onAddVault={handleAddVault}
          vaultLabel={vaultLabel}
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
      <div className="pointer-events-none relative flex min-h-0 min-w-0 flex-1 overflow-hidden">
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
          onDropNote={moveNote}
          vaults={vaultsState.vaults}
          activeVault={vaultsState.active}
          onSwitchVault={handleSwitchVault}
          onAddVault={handleAddVault}
          vaultLabel={vaultLabel}
          account={{
            name: activePersonaName,
            icon: activePersonaVisuals.icon,
            accent: activePersonaVisuals.accent,
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

        {/* the stage — content | editor, in fixed order; overflow-hidden
            clips a panel while it is parked off to the left. `relative` anchors
            the nebula mode toggle at the top-right corner. `pointer-events-none`
            so an empty stretch of stage (nothing open) doesn't sit as a dead
            hit-target above the always-bottom ambient nebula — each child
            claims `pointer-events-auto` back explicitly, both open and closed,
            so ordinary interaction is unaffected. */}
        <div className="pointer-events-none relative flex min-w-0 flex-1 overflow-hidden">
          {!isPhone && (
            // `top-[10.5px]` centers this 32px-tall row on the editor toolbar's
            // own vertical center: the panel's `py-2` outer margin (8px) plus
            // half its 37px toolbar row (4px padding + a 28px button + a 1px
            // border) — 8 + 37/2 - 32/2 = 10.5. A flat `top-4` (16px) sat
            // 5.5px low against it.
            <div className="pointer-events-auto absolute top-[10.5px] right-3 z-30 flex items-center gap-2">
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
              // Settings, Persona and the Vault view all share one gutter: `p-8`
              // on desktop/tablet, `px-4 py-6` on the phone plain page, `p-6`
              // for the phone vault surface. The persona card cancels this same
              // pad with its own negative-margin accent band (see PersonaCard).
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
              // Pinned below the scroll surface (not inside it) so a tall
              // Settings list can't scroll it out of reach, the same way the
              // editor panel's own "Links" row stays put under the note body.
              active === MENU_SETTINGS_ID ? (
                <div className="flex items-center justify-end">
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
            vaultPath={vaultsState.active}
            onWikiLinkClick={openWikilink}
            wikiLinkSource={wikiLinkSource}
            tagSource={tagSource}
            embedSource={embedSource}
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
            onNavigateToRootFolder={selectSection}
            vaultName={vaultName}
            preferences={editorPrefs}
            toolbarItems={toolbarItems}
            open={editorOpen}
            fill={editorFill}
            phone={isPhone}
          />
        </div>
      </div>
    </div>
  )
}
