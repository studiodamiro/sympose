import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import type { IconSvgElement } from "@hugeicons/react"
import {
  ArrowRight01Icon,
  Calendar03Icon,
  Cancel01Icon,
  Clock01Icon,
  Folder01Icon,
  FolderOpenIcon,
  MoreHorizontalIcon,
  Note01Icon,
  PinIcon,
  PinOffIcon,
} from "@hugeicons/core-free-icons"

import { cn, stripMdExtension } from "@/lib/utils"
import { getCookie, setCookie } from "@/lib/cookies"
import { startNoteDrag, isNoteDrag, readNoteDrag } from "@/lib/vault-drag"
import { useAnimatedNodeList } from "@/lib/use-animated-node-list"
import { VaultRowMenu } from "@/components/sympose/vault-row-menu"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"

/**
 * Vault directory tree. Collapsible,
 * sandbox-aware — system folders (`.obsidian`, `.git`, `Attachments`, `.trash`)
 * are filtered out. Folders use a disclosure row; note leaves render in the
 * `--entity` accent. Pure presentation: pass a tree, get selection callbacks.
 *
 * With a `storageKey`, the set of expanded folder paths is persisted to that
 * cookie so the open/closed shape survives a reload. Paths are vault-absolute
 * and therefore unique across folder views, so one key can back every panel.
 *
 * Pass `persona` + the `onRenamed` / `onDeleted` / `onCreated` callbacks to
 * enable per-row actions (rename / delete a note, new note in / delete a
 * folder): a `⋯` button on hover / focus, or right-click on the row.
 *
 * Pass `isPinned` / `onTogglePin` to badge a note's row with a pin glyph and
 * offer Pin/Unpin from its menu (cookie-backed pin state); pass
 * `pinnedNodes` to also render every pinned note under the current *root*
 * folder as its own group at the top of the list (the caller scopes this
 * per root folder, never vault-wide and never mixed across root folders;
 * `pinnedShowPath` labels those rows by full path instead of bare
 * filename, worth it only when that root folder actually has subfolders).
 * Pass `recentNodes` the same way for a genuinely vault-wide "Recent" group
 * under it.
 */
export interface VaultNode {
  name: string
  /** Full vault-relative path, used as the stable key + selection id. */
  path: string
  type: "folder" | "note"
  children?: VaultNode[]
  /** Frontmatter tags, without the leading `#` — notes only. */
  tags?: string[]
  /** Wikilink neighbours (outgoing targets and incoming backlinks, by
   *  stem) — notes only. */
  links?: string[]
}

const IGNORED = new Set([".obsidian", ".git", "Attachments", ".trash"])

// A stable reference for the `?? []` fallback below — every note lacks a
// `children` array, so a fresh `[]` literal there would change identity on
// every render and re-trigger `useAnimatedNodeList`'s effect indefinitely.
const NO_CHILDREN: VaultNode[] = []

// A "Recent" row isn't tracked by `useAnimatedNodeList` (its order is
// recency, not vault-tree membership — see `recentNodes` below), so it never
// actually has an exit animation to complete; `VaultTreeRow` still requires
// the callback.
function noop() {}

export function filterVaultTree(nodes: VaultNode[]): VaultNode[] {
  return nodes
    .filter((node) => !IGNORED.has(node.name))
    .map((node) =>
      node.children
        ? { ...node, children: filterVaultTree(node.children) }
        : node
    )
}

/**
 * Client-side vault search (round-trip-frugal — filters the tree already in
 * memory, no backend query). A node matches on its full vault-relative
 * `path` — so a query matching an ancestor folder's name surfaces everything
 * under it, not just a leaf whose own filename happens to contain it — or,
 * for a note, on any of its frontmatter tags or wikilink neighbours (both
 * outgoing links and incoming backlinks). A folder matching by its own path
 * keeps its whole subtree as-is; otherwise only its matching descendants
 * survive. Case-insensitive substring match throughout.
 */
export function filterTreeByQuery(
  nodes: VaultNode[],
  query: string
): VaultNode[] {
  const q = query.trim().toLowerCase()
  if (!q) return nodes
  const walk = (list: VaultNode[]): VaultNode[] =>
    list.reduce<VaultNode[]>((acc, node) => {
      const selfMatch =
        node.path.toLowerCase().includes(q) ||
        (node.tags?.some((t) => t.toLowerCase().includes(q)) ?? false) ||
        (node.links?.some((l) => l.toLowerCase().includes(q)) ?? false)
      if (node.type === "folder") {
        const children = selfMatch ? (node.children ?? []) : walk(node.children ?? [])
        if (selfMatch || children.length > 0) {
          acc.push({ ...node, children })
        }
      } else if (selfMatch) {
        acc.push(node)
      }
      return acc
    }, [])
  return walk(nodes)
}


/**
 * A group caption ("Pinned", "Recent", …) above a run of same-purpose rows,
 * styled to match `VaultContentSearch`'s "N matches beyond {folder}" row
 * (same icon-plus-label treatment) so every such grouping reads as one
 * visual language. `menuItems`, when given, wires the same two-way access a
 * row's own menu offers (`VaultRowMenu`): a hover-revealed `⋯` button, and
 * right-click / long-press anywhere on the caption. Omit it for a plain,
 * non-interactive caption.
 */
function GroupCaption({
  icon,
  label,
  paddingLeft,
  menuItems,
}: {
  icon: IconSvgElement
  label: string
  paddingLeft: number
  menuItems?: React.ReactNode
}) {
  const inner = (
    <>
      <HugeiconsIcon icon={icon} className="size-3 text-fg-muted" />
      <span className="text-xs text-fg-muted">{label}</span>

      {menuItems && (
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger
            aria-label={`${label} group actions`}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              "absolute top-1/2 right-1 grid size-6 -translate-y-1/2 place-items-center rounded text-fg-muted",
              "opacity-0 transition-opacity hover:bg-accent hover:text-foreground",
              "group-hover/section-caption:opacity-100 focus-visible:opacity-100 data-popup-open:opacity-100"
            )}
          >
            <HugeiconsIcon icon={MoreHorizontalIcon} className="size-3.5" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
            {menuItems}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </>
  )

  if (!menuItems) {
    return (
      <div
        className="flex items-center gap-1.5 pt-2 pb-1"
        style={{ paddingLeft: `${paddingLeft}px` }}
      >
        {inner}
      </div>
    )
  }

  return (
    <ContextMenu>
      <ContextMenuTrigger
        className="group/section-caption relative flex items-center gap-1.5 pt-2 pr-8 pb-1"
        style={{ paddingLeft: `${paddingLeft}px` }}
      >
        {inner}
      </ContextMenuTrigger>
      <ContextMenuContent className="duration-thumb ease-snappy">
        {menuItems}
      </ContextMenuContent>
    </ContextMenu>
  )
}

/** "Pinned" group caption with its "Unpin all" action, scoped to just this
 *  group's own paths (its level, not the whole vault). */
function PinnedSectionCaption({
  paddingLeft,
  paths,
  onUnpinAll,
}: {
  paddingLeft: number
  paths: string[]
  /** Unpin every path in this group. Omit to hide "Unpin all" entirely. */
  onUnpinAll?: (paths: string[]) => void
}) {
  return (
    <GroupCaption
      icon={PinIcon}
      label="Pinned"
      paddingLeft={paddingLeft}
      menuItems={
        onUnpinAll && (
          <DropdownMenuItem onClick={() => onUnpinAll(paths)}>
            <HugeiconsIcon icon={PinOffIcon} />
            Unpin all
          </DropdownMenuItem>
        )
      }
    />
  )
}

/** "Recent" group caption with its "Clear recents" action, emptying the
 *  whole history — not just what's currently shown. */
function RecentSectionCaption({
  paddingLeft,
  onClearRecents,
}: {
  paddingLeft: number
  /** Empty the whole Recent history. Omit to hide "Clear recents" entirely. */
  onClearRecents?: () => void
}) {
  return (
    <GroupCaption
      icon={Clock01Icon}
      label="Recent"
      paddingLeft={paddingLeft}
      menuItems={
        onClearRecents && (
          <DropdownMenuItem onClick={onClearRecents}>
            <HugeiconsIcon icon={Cancel01Icon} />
            Clear recents
          </DropdownMenuItem>
        )
      }
    />
  )
}

/** Every folder path in a tree, depth-first — used to seed `defaultExpanded`
 *  so a search result's matching folders open regardless of their normal
 *  collapsed state, without touching the persisted expanded-folders cookie. */
export function collectFolderPaths(nodes: VaultNode[]): string[] {
  return nodes.flatMap((node) =>
    node.type === "folder"
      ? [node.path, ...collectFolderPaths(node.children ?? [])]
      : []
  )
}

export interface FlatVaultMatch {
  node: VaultNode
  reason: "tag" | "link" | "path"
  /** The matched tag, wikilink target, or — for a plain path match — the
   *  ancestor folder whose name matched (undefined when the note's own path
   *  matched directly, since its own path is already shown as the row). */
  detail?: string
}

/**
 * `filterTreeByQuery`'s flat counterpart: no folder rows, no nesting — every
 * matching note as its own entry, tagged with *why* it matched, so a caller
 * can render a plain list (pathname + a one-line reason) instead of a
 * collapsible tree. A note under a folder that matches by name (e.g.
 * "quote" -> "Quotes/") is included with `reason: "path"` even though the
 * note itself has no tag/link/filename hit — same recall as
 * `filterTreeByQuery`'s whole-subtree-on-folder-match behavior, just
 * flattened for display.
 */
export function flatSearchTree(
  nodes: VaultNode[],
  query: string
): FlatVaultMatch[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  const out: FlatVaultMatch[] = []
  const walk = (list: VaultNode[], matchedFolder?: string) => {
    for (const node of list) {
      if (node.type === "folder") {
        const selfMatch = node.path.toLowerCase().includes(q)
        walk(node.children ?? [], selfMatch ? node.name : matchedFolder)
        continue
      }
      const matchedTag = node.tags?.find((t) => t.toLowerCase().includes(q))
      const matchedLink = node.links?.find((l) => l.toLowerCase().includes(q))
      if (matchedTag) {
        out.push({ node, reason: "tag", detail: matchedTag })
      } else if (matchedLink) {
        out.push({ node, reason: "link", detail: matchedLink })
      } else if (node.path.toLowerCase().includes(q)) {
        out.push({ node, reason: "path" })
      } else if (matchedFolder) {
        out.push({ node, reason: "path", detail: matchedFolder })
      }
    }
  }
  walk(nodes)
  return out
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
  /** Is this note path pinned — feeds the row's "Pin note" / "Unpin note"
   *  menu item and its badge. */
  isPinned?: (path: string) => boolean
  /** Toggle a note path's pinned state. */
  onTogglePin?: (path: string) => void
  /**
   * A note row was dragged onto a folder row: the note's own path,
   * and the folder it was dropped on. Independent of `menuReady` — like
   * `onTogglePin`, it needs no `persona` gate of its own — so wiring just
   * this alone is enough to make note rows draggable and folder rows drop
   * targets, no rename/delete/create callbacks required.
   */
  onMoveNote?: (path: string, destFolder: string) => void
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
  /** Hide the trailing `.md` on note labels (Settings > Markdown editor >
   *  File extensions). Default shown, matching the raw vault filename. */
  hideExtension?: boolean
  /**
   * Every pinned note under the current root folder, already resolved to its
   * real `VaultNode` — scoped per root folder, not vault-wide and
   * not just the immediate parent folder: a note pinned anywhere under
   * "Daily" shows while browsing Daily regardless of depth, never mixed with
   * another root folder's own pinned notes. The caller resolves this against
   * the *full* tree, not just this instance's own `nodes`, and decides the
   * scope. Rendered as its own "Pinned" group at the top of the list.
   */
  pinnedNodes?: VaultNode[]
  /** Label each Pinned row by its full path rather than its bare filename —
   *  worth it only when the current root folder actually has nested
   *  subfolders (e.g. Daily's year/month structure), where a bare filename
   *  alone wouldn't say where the note lives. */
  pinnedShowPath?: boolean
  /** Unpin every currently pinned note in one call — the "Pinned" group
   *  caption's "Unpin all". */
  onUnpinAll?: (paths: string[]) => void
  /**
   * Recently opened notes, most-recent-first, already resolved to their real
   * `VaultNode` and capped to the Settings "Recent notes shown" count
   * (`use-recent-notes.ts`) — vault-wide, so a caller resolves them against
   * the *full* tree, not just this instance's own `nodes`. Rendered as a
   * "Recent" group under Pinned.
   */
  recentNodes?: VaultNode[]
  /** Drop one note out of the Recent history — each recent row's own
   *  "Remove from recents" menu item. */
  onRemoveFromRecents?: (path: string) => void
  /** Empty the whole Recent history — the "Recent" group caption's
   *  "Clear recents". */
  onClearRecents?: () => void
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
  isPinned,
  onTogglePin,
  onMoveNote,
  hideExtension = false,
  pinnedNodes = NO_CHILDREN,
  pinnedShowPath = false,
  onUnpinAll,
  recentNodes = NO_CHILDREN,
  onRemoveFromRecents,
  onClearRecents,
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
  const { display, onExitComplete } = useAnimatedNodeList(visible)
  const actions: RowActions = {
    persona,
    onRenamed,
    onDeleted,
    onCreated,
    isPinned,
    onTogglePin,
    onMoveNote,
  }

  return (
    <div
      data-slot="vault-tree"
      role="tree"
      className={cn("flex flex-col py-1 text-sm", className)}
      {...props}
    >
      {pinnedNodes.length > 0 && (
        <>
          <PinnedSectionCaption
            paddingLeft={0}
            paths={pinnedNodes.map((node) => node.path)}
            onUnpinAll={onUnpinAll}
          />
          {pinnedNodes.map((node) => (
            <VaultTreeRow
              key={`pinned:${node.path}`}
              node={node}
              closing={false}
              onExitComplete={noop}
              depth={0}
              expanded={expanded}
              onToggle={toggle}
              selectedPath={selectedPath}
              onSelect={onSelect}
              actions={actions}
              hideExtension={hideExtension}
              showPath={pinnedShowPath}
            />
          ))}
        </>
      )}

      {pinnedNodes.length > 0 && recentNodes.length > 0 && (
        <div className="h-3" aria-hidden="true" />
      )}

      {recentNodes.length > 0 && (
        <>
          <RecentSectionCaption
            paddingLeft={0}
            onClearRecents={onClearRecents}
          />
          {recentNodes.map((node) => (
            <VaultTreeRow
              key={`recent:${node.path}`}
              node={node}
              closing={false}
              onExitComplete={noop}
              depth={0}
              expanded={expanded}
              onToggle={toggle}
              selectedPath={selectedPath}
              onSelect={onSelect}
              actions={actions}
              hideExtension={hideExtension}
              onRemoveFromRecents={
                onRemoveFromRecents
                  ? () => onRemoveFromRecents(node.path)
                  : undefined
              }
            />
          ))}
        </>
      )}

      {(pinnedNodes.length > 0 || recentNodes.length > 0) &&
        display.length > 0 && <div className="h-3" aria-hidden="true" />}

      {display.map(({ node, closing }) => (
        <VaultTreeRow
          key={node.path}
          node={node}
          closing={closing}
          onExitComplete={onExitComplete}
          depth={0}
          expanded={expanded}
          onToggle={toggle}
          selectedPath={selectedPath}
          onSelect={onSelect}
          actions={actions}
          hideExtension={hideExtension}
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
  closing,
  onExitComplete,
  depth,
  expanded,
  onToggle,
  selectedPath,
  onSelect,
  actions,
  hideExtension,
  showPath = false,
  onRemoveFromRecents,
}: {
  node: VaultNode
  /** This row's node just left the vault tree (deleted, or moved by a
   *  rename) — still mounted to play its exit animation. */
  closing: boolean
  onExitComplete: (path: string) => void
  depth: number
  expanded: Set<string>
  onToggle: (path: string) => void
  selectedPath?: string
  onSelect?: (node: VaultNode) => void
  actions: RowActions
  hideExtension: boolean
  /** Label by the note's full vault-relative path instead of its bare
   *  filename — the vault-wide "Pinned" group, shown outside the
   *  folder the note actually lives in. */
  showPath?: boolean
  /** This row is a "Recent" group entry — drop just this path from the
   *  history. Omit outside that group. */
  onRemoveFromRecents?: () => void
}) {
  const isOpen = expanded.has(node.path)
  const isSelected = selectedPath === node.path
  const basePad = depth * 14
  const pinned = node.type === "note" && !!actions.isPinned?.(node.path)
  const [dragOver, setDragOver] = React.useState(false)
  const canMove = !!actions.onMoveNote
  const folderDropProps: React.HTMLAttributes<HTMLButtonElement> = canMove
    ? {
        onDragOver: (e) => {
          if (!isNoteDrag(e)) return
          e.preventDefault()
          e.dataTransfer.dropEffect = "move"
        },
        onDragEnter: (e) => {
          if (!isNoteDrag(e)) return
          setDragOver(true)
        },
        onDragLeave: () => setDragOver(false),
        onDrop: (e) => {
          const path = readNoteDrag(e)
          if (!path) return
          e.preventDefault()
          setDragOver(false)
          actions.onMoveNote!(path, node.path)
        },
      }
    : {}

  // Called unconditionally (a note has no children, so this just tracks an
  // empty list) rather than only inside the folder branch below — `node.type`
  // never changes for a given mounted row, so either way is safe, but this
  // keeps every hook call unconditional regardless.
  const { display: childDisplay, onExitComplete: onChildExitComplete } =
    useAnimatedNodeList(node.children ?? NO_CHILDREN)

  // Entrance (a genuinely new row mounting) vs. exit (this node just
  // dropped out of the vault tree — held here by the parent's
  // `useAnimatedNodeList` so it can play this animation before it actually
  // unmounts, instead of vanishing the instant a refetch comes back without
  // it). Both read `duration-thumb` so a row enters and leaves at
  // the same speed it fades in and out of the scrollbar thumb.
  const rowMotionClass = closing
    ? "pointer-events-none animate-out fade-out-0 slide-out-to-left-1 duration-thumb"
    : "animate-in fade-in-0 slide-in-from-left-1 duration-thumb"
  const onRowAnimationEnd = closing
    ? () => onExitComplete(node.path)
    : undefined

  // Row actions (`⋯` button + right-click / long-press context menu) need the
  // full callback set; the showcases pass a bare tree and get plain rows.
  const menuReady =
    !!actions.persona &&
    !!actions.onRenamed &&
    !!actions.onDeleted &&
    !!actions.onCreated

  // Wrap the row's `<button>` in its action host, or a plain `group/row` line
  // when actions aren't wired. Pinning is independent of the rest of the
  // menu — it needs no `persona` or API round-trip — so it's offered
  // whenever `onTogglePin` is wired, not gated behind `menuReady`.
  const line = (rowButton: React.ReactNode, pad: number) =>
    menuReady ? (
      <VaultRowMenu
        node={node}
        persona={actions.persona!}
        paddingLeft={pad}
        onRenamed={actions.onRenamed!}
        onDeleted={actions.onDeleted!}
        onCreated={actions.onCreated!}
        pinned={pinned}
        onTogglePin={actions.onTogglePin}
        onRemoveFromRecents={onRemoveFromRecents}
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
      // Keyed on `node.path` by the parent map, so this only mounts (and
      // animates in) for a genuinely new folder — an existing row re-renders
      // in place on every vault refresh without replaying the entrance.
      <div
        role="treeitem"
        aria-expanded={isOpen}
        aria-hidden={closing || undefined}
        className={rowMotionClass}
        onAnimationEnd={onRowAnimationEnd}
      >
        {line(
          <button
            type="button"
            onClick={() => onToggle(node.path)}
            style={{ paddingLeft: `${basePad}px` }}
            className={cn(
              "flex min-w-0 flex-1 items-center gap-1.5 py-1 pr-0 text-left text-muted-foreground transition-[color,padding-right] duration-thumb ease-snappy hover:text-foreground",
              "group-hover/row:pr-8 group-focus-within/row:pr-8 group-has-data-popup-open/row:pr-8",
              "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
              dragOver && "rounded-md bg-accent/60 text-foreground ring-1 ring-inset ring-brand/60"
            )}
            {...folderDropProps}
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
          childDisplay.map(({ node: child, closing: childClosing }) => (
            <VaultTreeRow
              key={child.path}
              node={child}
              closing={childClosing}
              onExitComplete={onChildExitComplete}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              selectedPath={selectedPath}
              onSelect={onSelect}
              actions={actions}
              hideExtension={hideExtension}
            />
          ))}
      </div>
    )
  }

  // A pinned row shows outside the folder it actually lives in (the
  // vault-wide "Pinned" group), so its full path stands in for the bare
  // filename other rows use, to keep it unambiguous.
  const rawLabel = showPath ? node.path : node.name
  const noteLabel = hideExtension ? stripMdExtension(rawLabel) : rawLabel

  return (
    // Keyed on `node.path` by the parent map, so this only mounts (and
    // animates in) for a genuinely new note — an existing row re-renders in
    // place on every vault refresh without replaying the entrance.
    <div
      role="treeitem"
      aria-selected={isSelected}
      aria-hidden={closing || undefined}
      className={rowMotionClass}
      onAnimationEnd={onRowAnimationEnd}
    >
      {line(
        <button
          type="button"
          onClick={() => onSelect?.(node)}
          draggable={canMove}
          onDragStart={canMove ? (e) => startNoteDrag(e, node.path) : undefined}
          // Nested notes align under the parent folder's label (+20 clears the
          // disclosure chevron); top-level notes have no folder above them, so
          // they sit flush with the panel gutter (matching Settings / Persona).
          style={{ paddingLeft: `${basePad + (depth > 0 ? 20 : 0)}px` }}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-1.5 py-1 pr-0 text-left transition-[color,padding-right] duration-thumb ease-snappy",
            "group-hover/row:pr-8 group-focus-within/row:pr-8 group-has-data-popup-open/row:pr-8",
            "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
            isSelected
              ? "text-entity"
              : "text-entity/85 hover:text-entity"
          )}
        >
          <HugeiconsIcon
            // This row only renders once the folder branch above has already
            // returned, so `node` is always a note here — trust `node.type`
            // (already resolved by the backend) rather than re-deriving it
            // from the filename, which only recognized `.md` and missed the
            // `.markdown`/`.txt` extensions vault_snapshot.py also treats as
            // notes.
            icon={Note01Icon}
            className="size-3.5 shrink-0 text-fg-muted"
          />
          <span className="truncate">{noteLabel}</span>
          {pinned && (
            <HugeiconsIcon
              icon={PinIcon}
              aria-label="Pinned"
              className="size-3 shrink-0 text-fg-muted"
            />
          )}
        </button>,
        basePad + (depth > 0 ? 20 : 0)
      )}
    </div>
  )
}

export { VaultTree }
