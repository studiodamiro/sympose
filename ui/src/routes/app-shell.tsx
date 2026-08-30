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
  type MainMenuItem,
} from "@/components/sympose"

const ITEMS: MainMenuItem[] = VAULT_FOLDERS.map((f) => ({
  id: f.name,
  label: f.name,
  icon: f.icon,
}))

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

  return (
    <div className="flex h-svh w-full overflow-hidden bg-background text-foreground">
      <MainMenu
        items={ITEMS}
        activeId={active}
        onSelectItem={(item) => setActive(item.id)}
        storageKey="sympose:shell.menu"
      />
      <ContentPanel storageKey="sympose:shell.panel" contentClassName="p-8">
        <div className="flex items-center justify-between gap-4">
          <h1 className="font-heading text-2xl font-semibold text-fg-strong">
            {active}
          </h1>
          <Link
            to="/"
            className="shrink-0 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            ← back to demos
          </Link>
        </div>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {active} folder. This page mounts{" "}
          <span className="font-mono text-xs">&lt;MainMenu&gt;</span> as the app
          shell. Drag either right edge to resize — the widths persist across
          reloads. Pick a folder on the left; the heading follows it and the
          active row stays fused to this panel.
        </p>
      </ContentPanel>

      {/* remaining stage — markdown editor | chat, split down the middle with a
          draggable edge; the chat column centres itself in whatever it keeps */}
      <div className="flex min-w-0 flex-1">
        <MarkdownPanel storageKey="sympose:shell.md" />
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
