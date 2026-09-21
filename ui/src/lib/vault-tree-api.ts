import type { VaultNode } from "@/components/sympose"

/**
 * Client for `GET /api/vault/tree` — the vault manifest projected into a
 * nested `VaultNode` tree, scoped to a persona's allowed vault folders. Returns
 * an empty tree and `vaultName: null` when the backend is unreachable
 * (offline dev) so the browser still renders an empty state rather than
 * throwing.
 */
interface VaultTreeResponse {
  persona: string
  tree: VaultNode[]
  /** The master vault directory's basename, for the editor's read-mode
   *  breadcrumb — `null` when `MASTER_VAULT_PATH` isn't configured. */
  vaultName: string | null
}

export interface VaultTreeResult {
  tree: VaultNode[]
  vaultName: string | null
}

export async function fetchVaultTree(persona: string): Promise<VaultTreeResult> {
  try {
    const res = await fetch(
      `/api/vault/tree?persona=${encodeURIComponent(persona)}`
    )
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as VaultTreeResponse
    return { tree: data.tree ?? [], vaultName: data.vaultName ?? null }
  } catch (err) {
    console.info(
      `[vault-tree] /api/vault/tree unreachable (${err}) — showing an empty tree`
    )
    return { tree: [], vaultName: null }
  }
}
