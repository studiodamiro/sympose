import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Bottom runtime readout (carried from the vanilla scaffold; UI_DESIGN_REFERENCE
 * §5 status row). A single flat mono strip: `label value` items on the left,
 * endpoint links pushed to the right. Horizontally scrolls rather than wraps.
 */
interface StatusBarItem {
  label: string
  value: React.ReactNode
}

interface StatusBarLink {
  label: string
  href: string
}

interface StatusBarProps extends React.ComponentProps<"section"> {
  items: StatusBarItem[]
  links?: StatusBarLink[]
}

function StatusBar({ className, items, links = [], ...props }: StatusBarProps) {
  return (
    <section
      data-slot="status-bar"
      className={cn(
        "flex h-8 items-center gap-5 overflow-x-auto border-t border-border bg-card px-4 font-mono text-[11px] whitespace-nowrap text-fg-muted",
        className
      )}
      {...props}
    >
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span className="text-fg-strong">{item.label}</span>
          <span>{item.value}</span>
        </span>
      ))}
      {links.length > 0 && (
        <span className="ml-auto flex items-center gap-3.5">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-brand hover:underline"
            >
              {link.label}
            </a>
          ))}
        </span>
      )}
    </section>
  )
}

export { StatusBar }
export type { StatusBarItem, StatusBarLink }
