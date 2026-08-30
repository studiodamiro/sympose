import * as React from "react"
import { Link } from "react-router-dom"

import { VAULT_FOLDERS } from "@/lib/vault-folders"
import { ContentPanel, MainMenu, type MainMenuItem } from "@/components/sympose"

const ITEMS: MainMenuItem[] = VAULT_FOLDERS.map((f) => ({
  id: f.name,
  label: f.name,
  icon: f.icon,
}))

/**
 * `<MainMenu>` mounted as the real app shell — full viewport height, no demo
 * frame. The menu and the content panel are both drag-resizable and persist
 * their widths to cookies; the panel's heading tracks the selected folder and
 * stays fused to the active row. Reached at /shell (outside the RootLayout
 * chrome).
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
      {/* remaining stage — the ambient nebula lands here */}
      <div className="min-w-0 flex-1" />
    </div>
  )
}
