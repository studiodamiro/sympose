import type { VaultNode } from "@/components/sympose"

/**
 * Depth-first search of the vault tree for the node at an exact
 * vault-relative path — used to resolve a recently-opened note (tracked by
 * path alone, in `use-recent-notes.ts`) back to its real `VaultNode` so it
 * can render as a normal row regardless of which folder is currently in
 * view. `undefined` when nothing in the tree matches (the note was since
 * renamed or deleted).
 */
export function findNodeByPath(
  tree: VaultNode[],
  path: string
): VaultNode | undefined {
  for (const node of tree) {
    if (node.path === path) return node
    if (node.children) {
      const found = findNodeByPath(node.children, path)
      if (found) return found
    }
  }
  return undefined
}
