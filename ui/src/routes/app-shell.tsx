import * as React from "react"
import { Link } from "react-router-dom"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  File01Icon,
  Folder01Icon,
  Note01Icon,
  ThumbsUpIcon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import {
  getCookie,
  getCookieBool,
  setCookie,
  setCookieBool,
} from "@/lib/cookies"
import { useBreakpoint } from "@/lib/use-breakpoint"
import { useFillWidth } from "@/lib/use-fill-width"
import { useTransientFlag } from "@/lib/use-transient-flag"
import { usePanels } from "@/lib/use-panels"
import { useActivePersona } from "@/lib/use-active-persona"
import { fetchPersonas, type LivePersona } from "@/lib/personas"
import { fetchVaultTree } from "@/lib/vault-tree-api"
import { VAULT_FOLDERS } from "@/lib/vault-folders"
import {
  ActionBadge,
  AgentCard,
  ChatActionGroup,
  ChatMessage,
  ChatPanel,
  ContentPanel,
  MainMenu,
  MarkdownPanel,
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  TopBar,
  VaultTree,
  type MainMenuItem,
  type VaultNode,
} from "@/components/sympose"

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
      (active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID) &&
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
    if (id === resolvedActive && panels.isOpen("content")) {
      panels.close("content")
    } else {
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
  // Editor grows into the chat's area when nothing sits to its right — but only
  // on the smaller breakpoints, where space is scarce. On desktop it keeps its
  // dragged width and the freed area just sits blank when chat closes (a
  // full-bleed editor is an uncomfortable measure on a wide screen). Content
  // never grows — it is navigation, it keeps its dragged width even when alone.
  const editorFill =
    breakpoint !== "desktop" && editorOpen && !chatOpen && !unfillFirst

  // Agent picker — the active persona is client state (a cookie), and the
  // roster is fetched once. Both feed the `MENU_ACCOUNT_ID` panel; the handle
  // is lifted here so the vault panels can scope their `?persona=` calls to it
  // once those land.
  const [activePersona, setActivePersona] = useActivePersona()
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
  React.useEffect(() => {
    let alive = true
    fetchVaultTree(activePersona).then((tree) => {
      if (alive) setVaultTree(tree)
    })
    return () => {
      alive = false
    }
  }, [activePersona])

  // Main menu = the vault's surface (top-level folders + root notes like
  // README.md), in the tree's own order, with curated icons where the folder
  // name is known. The two footer sentinels (Settings, Agent) stay separate.
  const menuItems: MainMenuItem[] = vaultTree.map((node) => ({
    id: node.path,
    label: node.name,
    icon: menuIconFor(node),
  }))
  const noteIds = new Set(
    vaultTree.filter((n) => n.type === "note").map((n) => n.path)
  )

  // `active` holds the user's last explicit pick; a persisted folder id that no
  // longer exists (e.g. after switching to a persona with a narrower sandbox)
  // falls back to the first surface entry — derived, not synced.
  const isSentinel = active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID
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
  // Phone: the rail only shows alongside the content panel — the two are one
  // view. Desktop / tablet: always shown.
  const menuOpen = isPhone ? menuShown && contentOpen : true
  // Settings / Agent on phone are plain destination pages, styled off the chat
  // panel (same background, same gutter) rather than the vault content surface.
  const plainPage =
    isPhone && (active === MENU_SETTINGS_ID || active === MENU_ACCOUNT_ID)

  const contentBody =
    active === MENU_ACCOUNT_ID ? (
      <AgentCard
        personas={personas}
        active={activePersona}
        onSwitch={setActivePersona}
      />
    ) : active === MENU_SETTINGS_ID ? (
      <>
        <div className="flex items-center justify-between gap-4">
          <h1 className="font-heading text-2xl font-semibold text-fg-strong">
            {activeLabel}
          </h1>
          <Link
            to="/"
            className="shrink-0 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            ← back to demos
          </Link>
        </div>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {activeLabel} section. Every menu row toggles this panel; click the
          active row again to slide it away. The editor and chat toggle the same
          way. On a tablet only two of the three may be open at once — opening a
          third closes whichever you touched longest ago, and the rightmost one
          grows to fill the space.
        </p>
      </>
    ) : (
      <div className="flex flex-col gap-2">
        <h2 className="px-2 font-heading text-2xl font-semibold text-fg-strong">
          {activeLabel || "Vault"}
        </h2>
        {vaultTree.length === 0 ? (
          <p className="px-2 text-sm text-fg-muted">
            No notes in scope — check that the dashboard API is reachable and
            the persona has vault folders.
          </p>
        ) : panelNodes.length === 0 ? (
          <p className="px-2 text-sm text-fg-muted">This folder is empty.</p>
        ) : (
          <VaultTree
            nodes={panelNodes}
            storageKey="sympose:vault.expanded"
            selectedPath={selectedNote}
            onSelect={(node) => setSelectedNote(node.path)}
          />
        )}
      </div>
    )

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
    >
      {isPhone && (
        <TopBar
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
          while they are parked off to the inline-start */}
      <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
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
            the action group at the top-right corner. */}
        <div className="relative flex min-w-0 flex-1 overflow-hidden">
          {!isPhone && (
            <ChatActionGroup
              className="absolute top-4 right-3 z-30"
              chatOpen={chatOpen}
              onToggleChat={toggleChat}
            />
          )}

          <ContentPanel
            storageKey="sympose:shell.panel"
            scrollKey="sympose:shell.panel.scroll"
            contentClassName={
              !isPhone ? "p-8" : plainPage ? "px-4 py-6" : "p-6"
            }
            open={contentOpen}
            phone={isPhone}
            plain={plainPage}
            flushBottomLeft={
              !isPhone && contentOpen && active === MENU_ACCOUNT_ID
            }
          >
            {contentBody}
          </ContentPanel>

          <MarkdownPanel
            storageKey="sympose:shell.md"
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
              the collapse tweens between real pixel widths. On desktop the clamp
              stays at the full width even while closed, so the editor keeps its
              width and the area just sits blank — the toggle there reads as a
              crossfade + slide-up-from-below. Chat sits one z-level below the
              editor, so any horizontal motion starts from the editor's edge. */}
          <div
            ref={chatSlotRef}
            data-state={chatOpen ? "open" : "closed"}
            className={cn(
              "relative z-0 min-w-0 overflow-hidden duration-300 ease-in-out",
              chatToggling
                ? "transition-[max-width,opacity,translate]"
                : "transition-[opacity,translate]",
              chatOpen
                ? "translate-y-0 opacity-100"
                : "pointer-events-none translate-y-2 opacity-0"
            )}
            style={{
              flexGrow: 1,
              flexShrink: 1,
              flexBasis: 0,
              maxWidth:
                chatOpen || breakpoint === "desktop" ? chatAvailW || 9999 : 0,
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
