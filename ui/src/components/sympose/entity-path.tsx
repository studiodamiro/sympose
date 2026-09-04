import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * A vault path / note title rendered in the `--entity` accent with monospace
 * segments (UI_DESIGN_REFERENCE.md §3.2). By default the trailing segment is
 * emphasised and the parent folders are dimmed, so a path reads as
 * "where · what" at a glance.
 */
interface EntityPathProps extends React.ComponentProps<"span"> {
  path: string
  /** Dim the parent folders and emphasise the final segment. Default: true. */
  emphasizeLeaf?: boolean
}

function EntityPath({
  className,
  path,
  emphasizeLeaf = true,
  ...props
}: EntityPathProps) {
  const segments = path.split("/")
  const leaf = segments.pop() ?? path
  const parent = segments.join("/")

  return (
    <span
      data-slot="entity-path"
      className={cn(
        "inline-flex max-w-full items-baseline gap-0 font-mono text-xs break-all",
        className
      )}
      {...props}
    >
      {parent && (
        <span className={emphasizeLeaf ? "text-entity/60" : "text-entity"}>
          {parent}/
        </span>
      )}
      <span className={cn("text-entity", emphasizeLeaf && "font-medium")}>
        {leaf}
      </span>
    </span>
  )
}

export { EntityPath }
