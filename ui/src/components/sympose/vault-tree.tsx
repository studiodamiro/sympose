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

/**
 * Vault directory tree (UI_DESIGN_REFERENCE.md §5 / Module C). Collapsible,
 * sandbox-aware — system folders (`.obsidian`, `.git`, `Attachments`, `.trash`)
 * are filtered out. Folders use a disclosure row; note leaves render in the
 * `--entity` accent. Pure presentation: pass a tree, get selection callbacks.
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

interface VaultTreeProps extends Omit<React.ComponentProps<"div">, "onSelect"> {
  nodes: VaultNode[]
  selectedPath?: string
  defaultExpanded?: string[]
  onSelect?: (node: VaultNode) => void
}

function VaultTree({
  className,
  nodes,
  selectedPath,
  defaultExpanded = [],
  onSelect,
  ...props
}: VaultTreeProps) {
  const [expanded, setExpanded] = React.useState<Set<string>>(
    () => new Set(defaultExpanded)
  )

  const toggle = React.useCallback((path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  const visible = React.useMemo(() => filterVaultTree(nodes), [nodes])

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
        />
      ))}
    </div>
  )
}

function isDailyFolder(name: string) {
  return /^\d{4}$/.test(name) || /^\d{2}-[A-Za-z]+$/.test(name) || name === "Daily"
}

function VaultTreeRow({
  node,
  depth,
  expanded,
  onToggle,
  selectedPath,
  onSelect,
}: {
  node: VaultNode
  depth: number
  expanded: Set<string>
  onToggle: (path: string) => void
  selectedPath?: string
  onSelect?: (node: VaultNode) => void
}) {
  const isOpen = expanded.has(node.path)
  const isSelected = selectedPath === node.path
  const pad = { paddingLeft: `${depth * 14 + 8}px` }

  if (node.type === "folder") {
    const FolderGlyph = isDailyFolder(node.name)
      ? Calendar03Icon
      : isOpen
        ? FolderOpenIcon
        : Folder01Icon
    return (
      <div role="treeitem" aria-expanded={isOpen}>
        <button
          type="button"
          onClick={() => onToggle(node.path)}
          style={pad}
          className={cn(
            "group/row flex w-full items-center gap-1.5 py-1 pr-2 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
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
        </button>
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
            />
          ))}
      </div>
    )
  }

  return (
    <button
      type="button"
      role="treeitem"
      aria-selected={isSelected}
      onClick={() => onSelect?.(node)}
      style={{ paddingLeft: `${depth * 14 + 8 + 20}px` }}
      className={cn(
        "flex w-full items-center gap-1.5 py-1 pr-2 text-left transition-colors",
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
    </button>
  )
}

export { VaultTree }
