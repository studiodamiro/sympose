import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowRight01Icon,
  Calendar03Icon,
  File01Icon,
  Folder01Icon,
  FolderOpenIcon,
  Note01Icon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { getCookie, setCookie } from "@/lib/cookies"
import { VaultRowMenu } from "@/components/sympose/vault-row-menu"

/**
 * Vault directory tree (UI_DESIGN_REFERENCE.md §5 / Module C). Collapsible,
 * sandbox-aware — system folders (`.obsidian`, `.git`, `Attachments`, `.trash`)
 * are filtered out. Folders use a disclosure row; note leaves render in the
 * `--entity` accent. Pure presentation: pass a tree, get selection callbacks.
 *
 * With a `storageKey`, the set of expanded folder paths is persisted to that
 * cookie so the open/closed shape survives a reload. Paths are vault-absolute
 * and therefore unique across folder views, so one key can back every panel.
 *
 * Pass `persona` + the `onRenamed` / `onDeleted` / `onCreated` callbacks to
 * enable per-row actions (rename / delete a note, new note in a folder —
 * ADR-084): a `⋯` button on hover / focus, or right-click on the row.
 */
export interface VaultNode {
  name: string
  /** Full vault-relative path, used as the stable key + selection id. */
  path: string
  type: "folder" | "note"
  children?: VaultNode[]
}

const IGNORED = new Set([".obsidian", ".git", "Attachments", ".trash"])

export function filterVaultTree(nodes: VaultNode[]): VaultNode[] {
  return nodes
    .filter((node) => !IGNORED.has(node.name))
    .map((node) =>
      node.children
        ? { ...node, children: filterVaultTree(node.children) }
        : node
    )
}

interface RowActions {
  /** Persona handle scoping the vault-note API calls. */
  persona?: string
  /** A note row was renamed: old path → new vault-relative path. */
  onRenamed?: (oldPath: string, newPath: string) => void
  /** A note row was moved to trash. */
  onDeleted?: (path: string) => void
  /** A new note was created from a folder row. */
  onCreated?: (path: string) => void
}

interface VaultTreeProps
  extends Omit<React.ComponentProps<"div">, "onSelect">,
    RowActions {
  nodes: VaultNode[]
  selectedPath?: string
  defaultExpanded?: string[]
  /** Cookie key to persist the expanded folder paths under. */
  storageKey?: string
  onSelect?: (node: VaultNode) => void
}

function VaultTree({
  className,
  nodes,
  selectedPath,
  defaultExpanded = [],
  storageKey,
  onSelect,
  persona,
  onRenamed,
  onDeleted,
  onCreated,
  ...props
}: VaultTreeProps) {
  const [expanded, setExpanded] = React.useState<Set<string>>(() => {
    const seed = new Set(defaultExpanded)
    if (storageKey) {
      const saved = getCookie(storageKey)
      if (saved) for (const p of saved.split(",")) if (p) seed.add(p)
    }
    return seed
  })

  React.useEffect(() => {
    if (storageKey) setCookie(storageKey, [...expanded].join(","))
  }, [storageKey, expanded])

  const toggle = React.useCallback((path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const visible = React.useMemo(() => filterVaultTree(nodes), [nodes])
  const actions: RowActions = { persona, onRenamed, onDeleted, onCreated }

  return (
    <div
      data-slot="vault-tree"
      role="tree"
      className={cn("flex flex-col py-1 text-sm", className)}
      {...props}
    >
      {visible.map((node) => (
        <VaultTreeRow
          key={node.path}
          node={node}
          depth={0}
          expanded={expanded}
          onToggle={toggle}
          selectedPath={selectedPath}
          onSelect={onSelect}
          actions={actions}
        />
      ))}
    </div>
  )
}

function isDailyFolder(name: string) {
  return (
    /^\d{4}$/.test(name) || /^\d{2}-[A-Za-z]+$/.test(name) || name === "Daily"
  )
}

function VaultTreeRow({
  node,
  depth,
  expanded,
  onToggle,
  selectedPath,
  onSelect,
  actions,
}: {
  node: VaultNode
  depth: number
  expanded: Set<string>
  onToggle: (path: string) => void
  selectedPath?: string
  onSelect?: (node: VaultNode) => void
  actions: RowActions
}) {
  const isOpen = expanded.has(node.path)
  const isSelected = selectedPath === node.path
  const basePad = depth * 14

  // Row actions (`⋯` button + right-click / long-press context menu) need the
  // full callback set; the showcases pass a bare tree and get plain rows.
  const menuReady =
    !!actions.persona &&
    !!actions.onRenamed &&
    !!actions.onDeleted &&
    !!actions.onCreated

  // Wrap the row's `<button>` in its action host, or a plain `group/row` line
  // when actions aren't wired.
  const line = (rowButton: React.ReactNode, pad: number) =>
    menuReady ? (
      <VaultRowMenu
        node={node}
        persona={actions.persona!}
        paddingLeft={pad}
        onRenamed={actions.onRenamed!}
        onDeleted={actions.onDeleted!}
        onCreated={actions.onCreated!}
      >
        {rowButton}
      </VaultRowMenu>
    ) : (
      <div className="group/row relative flex items-center">{rowButton}</div>
    )

  if (node.type === "folder") {
    const FolderGlyph = isDailyFolder(node.name)
      ? Calendar03Icon
      : isOpen
        ? FolderOpenIcon
        : Folder01Icon
    return (
      <div role="treeitem" aria-expanded={isOpen}>
        {line(
          <button
            type="button"
            onClick={() => onToggle(node.path)}
            style={{ paddingLeft: `${basePad}px` }}
            className={cn(
              "flex min-w-0 flex-1 items-center gap-1.5 py-1 pr-8 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
              "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            )}
          >
            <HugeiconsIcon
              icon={ArrowRight01Icon}
              className={cn(
                "size-3.5 shrink-0 text-fg-muted transition-transform",
                isOpen && "rotate-90"
              )}
            />
            <HugeiconsIcon icon={FolderGlyph} className="size-3.5 shrink-0" />
            <span className="truncate font-mono text-xs">{node.name}</span>
          </button>,
          basePad
        )}
        {isOpen &&
          node.children?.map((child) => (
            <VaultTreeRow
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              selectedPath={selectedPath}
              onSelect={onSelect}
              actions={actions}
            />
          ))}
      </div>
    )
  }

  return (
    <div role="treeitem" aria-selected={isSelected}>
      {line(
        <button
          type="button"
          onClick={() => onSelect?.(node)}
          // Nested notes align under the parent folder's label (+20 clears the
          // disclosure chevron); top-level notes have no folder above them, so
          // they sit flush with the panel gutter (matching Settings / Agent).
          style={{ paddingLeft: `${basePad + (depth > 0 ? 20 : 0)}px` }}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-1.5 py-1 pr-8 text-left transition-colors",
            "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
            isSelected
              ? "bg-accent text-entity"
              : "text-entity/85 hover:bg-accent hover:text-entity"
          )}
        >
          <HugeiconsIcon
            icon={node.name.endsWith(".md") ? Note01Icon : File01Icon}
            className="size-3.5 shrink-0 text-fg-muted"
          />
          <span className="truncate">{node.name}</span>
        </button>,
        basePad + (depth > 0 ? 20 : 0)
      )}
    </div>
  )
}

export { VaultTree }
