import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { resolvePersonaVisuals, type LivePersona } from "@/lib/personas"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { ModelChip } from "@/components/sympose/model-chip"

/** First letter of each of the first two words — "Grace Hopper" -> "GH". */
function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("")
}

interface AgentCardProps {
  /** Live roster from `GET /api/personas`. */
  personas: LivePersona[]
  /** Handle of the active persona. */
  active: string
  /** Switch the active persona (writes the cookie upstream). */
  onSwitch: (handle: string) => void
  className?: string
}

/**
 * The Agent panel — identity of the active persona plus a switcher. Soul and
 * Memory open the persona's markdown; both are disabled until their endpoints
 * land (`GET /api/personas/{handle}/soul|memory`). PINNED / RECENT are a later
 * pass. The header band is tinted with the persona's own accent, the same
 * `--persona-accent` custom property `<PersonaPill>` uses, so runtime-created
 * personas that are not in the static roster still get a stable colour.
 */
function AgentCard({ personas, active, onSwitch, className }: AgentCardProps) {
  const current = personas.find((p) => p.handle === active) ?? personas[0]
  const others = personas.filter((p) => p.handle !== current?.handle)

  if (!current) {
    return (
      <p className={cn("text-sm text-fg-muted", className)}>
        No personas found. Check the dashboard API at <code>/api/personas</code>
        .
      </p>
    )
  }

  const visuals = resolvePersonaVisuals(current.handle)

  return (
    <div
      className={cn("flex w-full flex-col gap-4", className)}
      style={
        {
          "--persona-accent": visuals.accent,
          "--persona-accent-dark": visuals.accentDark,
        } as React.CSSProperties
      }
    >
      {/* accent band — bleeds to the panel edges (cancels its `p-6`); the
          panel's own rounded top corners + overflow clip it */}
      <div
        className="-mx-6 -mt-6 h-28 rounded-tl-lg rounded-tr-lg bg-(--persona-accent) dark:bg-(--persona-accent-dark)"
        aria-hidden
      />

      {/* identity — avatar lifts into the band */}
      <div className="-mt-16 flex items-end gap-3">
        <Avatar size="lg" className="size-16 ring-4 ring-panel">
          <AvatarFallback className="bg-muted text-base font-medium text-fg-strong">
            {initials(current.name)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 pb-1">
          <h2 className="truncate font-heading text-lg font-semibold text-fg-strong">
            {current.name}
          </h2>
        </div>
      </div>

      <p className="text-sm leading-snug text-fg-muted">{current.title}</p>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <ModelChip model={current.model} />
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled
            title="Persona soul — coming soon"
          >
            Soul
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled
            title="Persona memory — coming soon"
          >
            Memory
          </Button>
        </div>
      </div>

      {others.length > 0 && (
        <>
          <hr className="border-border" />
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold tracking-wide text-fg-muted uppercase">
              Switch agents
            </span>
            <div className="flex flex-wrap gap-2">
              {others.map((p) => {
                const v = resolvePersonaVisuals(p.handle)
                return (
                  <button
                    key={p.handle}
                    type="button"
                    onClick={() => onSwitch(p.handle)}
                    title={`${p.name} — ${p.title}`}
                    className="rounded-full outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  >
                    <Avatar
                      size="default"
                      className="size-9 transition-transform hover:scale-105"
                    >
                      <AvatarFallback
                        className="text-xs font-medium text-background"
                        style={{ background: v.accent }}
                      >
                        <HugeiconsIcon icon={v.icon} className="size-4" />
                      </AvatarFallback>
                    </Avatar>
                  </button>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export { AgentCard }
