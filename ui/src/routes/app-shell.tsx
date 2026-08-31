import * as React from "react"
import { Link } from "react-router-dom"
import { HugeiconsIcon } from "@hugeicons/react"
import { ThumbsUpIcon } from "@hugeicons/core-free-icons"

import { VAULT_FOLDERS } from "@/lib/vault-folders"
import {
  ActionBadge,
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

/**
 * `<MainMenu>` mounted as the real app shell — full viewport height, no demo
 * frame. The menu and the content panel are both drag-resizable and persist
 * their widths to cookies; the panel's heading tracks the selected folder and
 * stays fused to the active row. The remaining stage hosts `<ChatPanel>`,
 * whose reading column stays centred in whatever space is left. Reached at
 * /shell (outside the RootLayout chrome).
 */
export function AppShell() {
  const [active, setActive] = React.useState("Projects")
  // The content panel starts open. Every menu row — folders plus the Settings
  // and account footer rows — routes through selectSection: re-clicking the
  // active row toggles the panel (same reveal/slide as the editor), clicking a
  // different one switches to it and re-opens.
  const [panelOpen, setPanelOpen] = React.useState(true)
  // The markdown editor starts hidden; the [WRITE_NOTE] badge in the chat
  // toggles it, sliding it in from the left.
  const [mdOpen, setMdOpen] = React.useState(false)

  const selectSection = (id: string) => {
    if (id === active) {
      setPanelOpen((v) => !v)
    } else {
      setActive(id)
      setPanelOpen(true)
    }
  }

  const activeLabel = SECTION_LABELS[active] ?? active

  return (
    <div className="flex h-svh w-full overflow-hidden bg-background text-foreground">
      <MainMenu
        items={ITEMS}
        // above the content panel so it tucks *behind* the menu on hide
        className="z-20"
        activeId={panelOpen ? active : undefined}
        onSelectItem={(item) => selectSection(item.id)}
        onOpenSettings={() => selectSection(MENU_SETTINGS_ID)}
        onSelectAccount={() => selectSection(MENU_ACCOUNT_ID)}
        storageKey="sympose:shell.menu"
      />
      <ContentPanel
        storageKey="sympose:shell.panel"
        contentClassName="p-8"
        open={panelOpen}
        flushBottomLeft={panelOpen && active === MENU_ACCOUNT_ID}
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
          {activeLabel} section. This page mounts{" "}
          <span className="font-mono text-xs">&lt;MainMenu&gt;</span> as the app
          shell. Drag either right edge to resize — the widths persist across
          reloads. Click any menu row to switch sections; click the active row
          (folder, Settings, or the account) again to slide this panel away, and
          once more to bring it back.
        </p>
      </ContentPanel>

      {/* remaining stage — markdown editor | chat, split down the middle with a
          draggable edge; the chat column centres itself in whatever it keeps.
          overflow-hidden clips the editor while it is parked off to the left. */}
      <div className="flex min-w-0 flex-1 overflow-hidden">
        <MarkdownPanel storageKey="sympose:shell.md" open={mdOpen} />
        <div className="min-w-0 flex-1 pe-2">
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
                  aria-pressed={mdOpen}
                  onClick={() => setMdOpen((v) => !v)}
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
