import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { HugeiconsIcon } from "@hugeicons/react"

import { cn } from "@/lib/utils"
import { getPersona, type Persona } from "@/lib/personas"

/**
 * `@handle` identity pill — leads every chat turn (UI_DESIGN_REFERENCE.md §7).
 * The persona accent is applied as inline `--persona-accent` /
 * `--persona-accent-dark` custom properties so runtime-created personas work
 * without a build-time Tailwind class; the `dark:` utilities pick the second.
 */
const personaPillVariants = cva(
  "group/persona-pill inline-flex w-fit shrink-0 items-center gap-1.5 rounded-4xl border font-medium whitespace-nowrap [&>svg]:shrink-0",
  {
    variants: {
      size: {
        sm: "h-5 px-1.5 text-xs [&>svg]:size-3",
        default: "h-6 px-2 text-sm [&>svg]:size-3.5",
      },
      tone: {
        soft: cn(
          "border-[color-mix(in_oklch,var(--persona-accent)_35%,transparent)] bg-[color-mix(in_oklch,var(--persona-accent)_12%,transparent)] text-(--persona-accent)",
          "dark:border-[color-mix(in_oklch,var(--persona-accent-dark)_40%,transparent)] dark:bg-[color-mix(in_oklch,var(--persona-accent-dark)_16%,transparent)] dark:text-(--persona-accent-dark)"
        ),
        solid:
          "border-transparent bg-(--persona-accent) text-background dark:bg-(--persona-accent-dark)",
      },
    },
    defaultVariants: { size: "default", tone: "soft" },
  }
)

interface PersonaPillProps
  extends Omit<React.ComponentProps<"span">, "children">,
    VariantProps<typeof personaPillVariants> {
  /** Persona handle, with or without a leading `@`. */
  handle: string
  /** Override the resolved persona (for personas not in the static roster). */
  persona?: Persona
  showIcon?: boolean
}

function PersonaPill({
  className,
  handle,
  persona,
  size,
  tone,
  showIcon = true,
  style,
  ...props
}: PersonaPillProps) {
  const resolved = persona ?? getPersona(handle)
  const accent = resolved?.accent ?? "var(--brand)"
  const accentDark = resolved?.accentDark ?? "var(--brand)"

  return (
    <span
      data-slot="persona-pill"
      data-tier={resolved?.tier}
      className={cn(personaPillVariants({ size, tone }), className)}
      style={
        {
          "--persona-accent": accent,
          "--persona-accent-dark": accentDark,
          ...style,
        } as React.CSSProperties
      }
      {...props}
    >
      {showIcon && resolved ? <HugeiconsIcon icon={resolved.icon} /> : null}
      <span>@{resolved?.handle ?? handle.replace(/^@/, "")}</span>
    </span>
  )
}

export { PersonaPill, personaPillVariants }
