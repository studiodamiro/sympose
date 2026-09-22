/**
 * Client for `/api/vaults*` — the workspace switcher (ADR 003, ADR 004). One
 * active vault at a time; switching it re-scopes every other vault route
 * (tree, search, graph, ...) on their next fetch, since the backend resolves
 * the active vault fresh on every call.
 */

import { detailOf } from "./vault-note-api"

export interface Vault {
  name: string
  path: string
}

export interface VaultsState {
  vaults: Vault[]
  active: string | null
}

/** Stable empty default so an omitted `vaults` prop never re-triggers
 *  `<WorkspaceSwitcher>` on every render with a fresh `[]` literal. */
export const EMPTY_VAULTS: Vault[] = []

/**
 * `GET /api/vaults` — every configured vault plus which one is active.
 * Returns an empty list on any error so a single-vault / offline dev setup
 * just hides the switcher rather than erroring.
 */
export async function fetchVaults(): Promise<VaultsState> {
  try {
    const res = await fetch("/api/vaults")
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as VaultsState
    return { vaults: data.vaults ?? [], active: data.active ?? null }
  } catch (err) {
    console.info(`[vaults] /api/vaults unreachable (${err})`)
    return { vaults: [], active: null }
  }
}

export type SetActiveVaultResult =
  | { ok: true; state: VaultsState }
  | { ok: false; error: string }

/**
 * `POST /api/vaults/active` — switch the active vault. 404 when `path` isn't
 * one of the configured vaults.
 */
export async function setActiveVault(
  path: string
): Promise<SetActiveVaultResult> {
  try {
    const res = await fetch("/api/vaults/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    })
    if (res.ok) return { ok: true, state: (await res.json()) as VaultsState }
    return {
      ok: false,
      error: (await detailOf(res)) || `Switch failed (HTTP ${res.status})`,
    }
  } catch (err) {
    return { ok: false, error: `Switch failed — backend unreachable (${err})` }
  }
}

/**
 * `POST /api/vaults` — add `path` to the configured list and make it active
 * (ADR 004). 400 when `path` isn't an existing directory.
 */
export async function addVault(path: string): Promise<SetActiveVaultResult> {
  try {
    const res = await fetch("/api/vaults", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    })
    if (res.ok) return { ok: true, state: (await res.json()) as VaultsState }
    return {
      ok: false,
      error: (await detailOf(res)) || `Add failed (HTTP ${res.status})`,
    }
  } catch (err) {
    return { ok: false, error: `Add failed — backend unreachable (${err})` }
  }
}
