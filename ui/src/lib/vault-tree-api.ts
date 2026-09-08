import type { VaultNode } from "@/components/sympose"

/**
 * Client for `GET /api/vault/tree` — the ADR-078 manifest projected into a
 * nested `VaultNode` tree, scoped to a persona's allowed vault folders. Returns
 * `[]` when the backend is unreachable (offline dev) so the browser still
 * renders an empty state rather than throwing.
 */
interface VaultTreeResponse {
  persona: string
  tree: VaultNode[]
}

export async function fetchVaultTree(persona: string): Promise<VaultNode[]> {
  try {
    const res = await fetch(
      `/api/vault/tree?persona=${encodeURIComponent(persona)}`
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as VaultTreeResponse
    return data.tree ?? []
  } catch (err) {
    console.info(
      `[vault-tree] /api/vault/tree unreachable (${err}) — showing an empty tree`
    )
    return []
  }
}
