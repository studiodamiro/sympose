/**
 * URL for `GET /api/vault/asset` — a raw vault file (image, etc.) by
 * vault-relative path, scoped to a persona's allowed vault folders. Meant
 * for direct use as an `<img src>`, not fetched via `fetch()` — the backend
 * streams the file itself, not JSON.
 */
export function vaultAssetUrl(path: string, persona: string): string {
  return `/api/vault/asset?path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`
}
