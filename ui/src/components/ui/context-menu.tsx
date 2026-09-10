import { ContextMenu as ContextMenuPrimitive } from "@base-ui/react/context-menu"

import { cn } from "@/lib/utils"
import { menuPopupClass } from "@/components/ui/dropdown-menu"

/**
 * Pointer-anchored context menu — right-click on a fine pointer, ~450ms
 * long-press on touch / pen (Base UI handles both, and positions the popup at
 * the contact point). It reuses `menuPopupClass` and the `DropdownMenuItem` /
 * `DropdownMenuSeparator` parts verbatim — `ContextMenu.Item` *is* `Menu.Item`
 * — so a right-click menu and a button dropdown are the same component down to
 * the pixel. The one deliberate difference is size on coarse pointers: a
 * `@media (pointer: coarse)` block in `index.css`, keyed off
 * `[data-slot="context-menu-content"]`, opens the rows up for a fingertip,
 * mirroring the editor's own touch menu.
 */
function ContextMenu(props: ContextMenuPrimitive.Root.Props) {
  return <ContextMenuPrimitive.Root data-slot="context-menu" {...props} />
}

function ContextMenuTrigger(props: ContextMenuPrimitive.Trigger.Props) {
  return (
    <ContextMenuPrimitive.Trigger data-slot="context-menu-trigger" {...props} />
  )
}

function ContextMenuContent({
  className,
  sideOffset = 4,
  ...props
}: ContextMenuPrimitive.Popup.Props &
  Pick<ContextMenuPrimitive.Positioner.Props, "sideOffset">) {
  return (
    <ContextMenuPrimitive.Portal>
      <ContextMenuPrimitive.Positioner
        className="isolate z-50 outline-none"
        sideOffset={sideOffset}
      >
        <ContextMenuPrimitive.Popup
          data-slot="context-menu-content"
          className={cn(menuPopupClass, "min-w-52", className)}
          {...props}
        />
      </ContextMenuPrimitive.Positioner>
    </ContextMenuPrimitive.Portal>
  )
}

export { ContextMenu, ContextMenuTrigger, ContextMenuContent }
