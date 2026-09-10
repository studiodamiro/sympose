import { HugeiconsIcon } from "@hugeicons/react"
import { Moon02Icon, Sun03Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { useTheme } from "@/components/theme-provider"
import { useEffectiveTheme } from "@/lib/use-effective-theme"

/**
 * Compact light/dark switch for the Settings footer — pill-height to match the
 * Slack status pill beside it. Shows the mode in effect and flips to the other
 * on click; it always lands on an explicit `light` / `dark` (a prior `system`
 * choice is replaced). The full three-way `light / dark / system` control still
 * lives in the dev-harness header.
 *
 * The effective theme (via `useEffectiveTheme`) is read from the `dark` /
 * `light` class the `ThemeProvider` writes on `<html>`, so `system` resolves
 * correctly and an OS appearance change keeps the label honest.
 */
function ThemeToggle({ className }: { className?: string }) {
  const { setTheme } = useTheme()
  const effective = useEffectiveTheme()
  const next = effective === "dark" ? "light" : "dark"

  return (
    <button
      type="button"
      data-slot="theme-toggle"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground",
        className
      )}
    >
      <HugeiconsIcon
        icon={effective === "dark" ? Moon02Icon : Sun03Icon}
        className="size-3.5"
      />
      {effective === "dark" ? "Dark" : "Light"}
    </button>
  )
}

export { ThemeToggle }
