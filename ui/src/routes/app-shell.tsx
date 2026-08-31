import * as React from "react"
import { Link } from "react-router-dom"
import { HugeiconsIcon } from "@hugeicons/react"
import { ThumbsUpIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { getCookieBool } from "@/lib/cookies"
import { useBreakpoint } from "@/lib/use-breakpoint"
import { useFillWidth } from "@/lib/use-fill-width"
import { useTransientFlag } from "@/lib/use-transient-flag"
import { usePanels } from "@/lib/use-panels"
import { VAULT_FOLDERS } from "@/lib/vault-folders"
import {
  ActionBadge,
  ChatActionGroup,
  ChatMessage,
  ChatPanel,
  ContentPanel,
  MainMenu,
  MarkdownPanel,
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  type MainMenuItem,
} from "@/components/sympose"

const ITEMS: MainMenuItem[] = VAULT_FOLDERS.map((f) => ({
  id: f.name,
  label: f.name,
  icon: f.icon,
}))

/** Labels for the non-folder sections the footer rows can select. */
const SECTION_LABELS: Record<string, string> = {
  [MENU_SETTINGS_ID]: "Settings",
  [MENU_ACCOUNT_ID]: "Agent",
}

const AUTO_COLLAPSE_COOKIE = "sympose:pref.autoCollapseMenu"

/**
 * `<MainMenu>` mounted as the real app shell — full viewport height, no demo
 * frame. The three stage panels (content, editor, chat) each toggle
 * independently; on tablet a cap of two is enforced, oldest-evicted, and the
 * rightmost open panel fills the leftover width. All visibility + widths persist
 * to cookies globally and are clamped to the breakpoint on load. Reached at
 * /shell (outside the RootLayout chrome).
 */
export function AppShell() {
  const rootRef = React.useRef<HTMLDivElement>(null)
  const breakpoint = useBreakpoint(rootRef)
  const panels = usePanels(breakpoint)

  const [active, setActive] = React.useState("Projects")

  const selectSection = (id: string) => {
    if (id === active && panels.isOpen("content")) {
      panels.close("content")
    } else {
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
  const editorFill = breakpoint !== "desktop" && editorOpen && !chatOpen

  const activeLabel = SECTION_LABELS[active] ?? active

  return (
    <div
      ref={rootRef}
      className="flex h-svh w-full overflow-hidden bg-background text-foreground"
    >
      <MainMenu
        items={ITEMS}
        // above the stage so the content panel tucks *behind* it on hide
        className="z-20"
        activeId={contentOpen ? active : undefined}
        onSelectItem={(item) => selectSection(item.id)}
        onOpenSettings={() => selectSection(MENU_SETTINGS_ID)}
        onSelectAccount={() => selectSection(MENU_ACCOUNT_ID)}
        collapsed={menu.collapsed}
        onCollapsedChange={(c) =>
          setMenu((m) => ({ ...m, collapsed: c, forced: c ? m.forced : false }))
        }
        storageKey="sympose:shell.menu"
      />

      {/* the stage — content | editor | chat, in fixed order; overflow-hidden
          clips a panel while it is parked off to the left. `relative` anchors
          the action group at the top-right corner. */}
      <div className="relative flex min-w-0 flex-1 overflow-hidden">
        <ChatActionGroup
          className="absolute top-4 right-3 z-30"
          chatOpen={chatOpen}
          onToggleChat={() => panels.toggle("chat")}
        />

        <ContentPanel
          storageKey="sympose:shell.panel"
          contentClassName="p-8"
          open={contentOpen}
          flushBottomLeft={contentOpen && active === MENU_ACCOUNT_ID}
        >
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
            active row again to slide it away. The editor and chat toggle the
            same way. On a tablet only two of the three may be open at once —
            opening a third closes whichever you touched longest ago, and the
            rightmost one grows to fill the space.
          </p>
        </ContentPanel>

        <MarkdownPanel
          storageKey="sympose:shell.md"
          open={editorOpen}
          fill={editorFill}
        />

        {/* chat slot — always mounted. flex-grow:1 makes it adopt the free
            width live, frame by frame, as the editor slides in or out (a plain
            ResizeObserver never sees that — the neighbour only changes its
            margin). max-width clamps it to the same measurement: normally it
            just follows along, but for the ~320ms the chat is itself opening or
            closing (`chatToggling`) the max-width transition is armed so the
            collapse tweens between real pixel widths. On desktop the clamp
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
          <ChatPanel placeholder="Ask Samantha." model="3.7 Flash">
            <ChatMessage
              role="user"
              reaction={<HugeiconsIcon icon={ThumbsUpIcon} />}
            >
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
                  onClick={() => panels.toggle("editor")}
                />
              }
            >
              But I must explain to you how all this mistaken idea of denouncing
              pleasure and praising pain was born and I will give you a complete
              account of the system, and expound the actual teachings of the
              great explorer of the truth, the master-builder of human
              happiness. No one rejects, dislikes, or avoids pleasure itself,
              because it is pleasure, but because
            </ChatMessage>
            <ChatMessage role="persona" handle="samantha">
              I will give you a complete account of the system, and expound the
              actual teachings of the great explorer of the truth, the
              master-builder of human happiness. No one rejects, dislikes, or
              avoids pleasure itself, because it is pleasure, but because
            </ChatMessage>
          </ChatPanel>
        </div>
      </div>
    </div>
  )
}
