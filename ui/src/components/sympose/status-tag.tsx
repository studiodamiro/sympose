import { cva, type VariantProps } from "class-variance-authority"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  AlertCircleIcon,
  CheckmarkCircle02Icon,
  Loading03Icon,
  RecordIcon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"

/**
 * Endpoint / connection status pill used across panel headers and the status
 * bar. Carried over from the vanilla scaffold's `data-status` tags; restated
 * with shadcn `cva` + semantic tokens so it themes in light and dark.
 */
const statusTagVariants = cva(
  "inline-flex h-5 w-fit shrink-0 items-center gap-1.5 rounded-md border px-1.5 font-mono text-[11px] whitespace-nowrap [&>svg]:size-3",
  {
    variants: {
      status: {
        ok: "border-ok/40 text-ok",
        error: "border-danger/40 text-danger",
        loading: "border-border text-fg-muted",
        stub: "border-border text-chip-foreground",
      },
    },
    defaultVariants: {
      status: "loading",
    },
  }
)

const STATUS_ICON = {
  ok: CheckmarkCircle02Icon,
  error: AlertCircleIcon,
  loading: Loading03Icon,
  stub: RecordIcon,
} as const

function StatusTag({
  className,
  status = "loading",
  children,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof statusTagVariants>) {
  const resolved = status ?? "loading"
  return (
    <span
      data-slot="status-tag"
      data-status={resolved}
      className={cn(statusTagVariants({ status: resolved }), className)}
      {...props}
    >
      <HugeiconsIcon
        icon={STATUS_ICON[resolved]}
        className={resolved === "loading" ? "animate-spin" : undefined}
      />
      {children}
    </span>
  )
}

export { StatusTag, statusTagVariants }
