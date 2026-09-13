import type { ReactNode } from "react"
import { Stylo } from "@damiro/stylo"
import type { VaultNode } from "@/components/sympose"
import { findNoteByWikilink } from "./find-note-by-wikilink"
import { fetchVaultNote } from "./vault-note-api"
import { vaultAssetUrl } from "./vault-asset-api"

const IMAGE_EXT = /\.(png|jpe?g|gif|svg|webp|bmp|avif)$/i

/** Reads a positive size out of an Obsidian-style `|300` or `|300x200` embed
 *  suffix; `undefined` for anything absent or non-numeric, so the `<img>`
 *  falls back to its natural size rather than rendering `0`/`NaN`. */
function parseDimension(raw: string | undefined): number | undefined {
  const n = raw ? Number(raw) : NaN
  return Number.isFinite(n) && n > 0 ? n : undefined
}

/**
 * Resolves one `![[ref]]` embed for stylo's `embedSource` — an image
 * reference becomes a vault-asset `<img>`, a note reference becomes its
 * content rendered read-only via a nested `<Stylo mode="preview">`. Returns
 * `null` (stylo's "keep it literal" signal) when `ref` is empty, doesn't
 * resolve to anything in the sandboxed tree, or the note fetch fails.
 *
 * A `#Heading` / `#^blockid` suffix is recognized and stripped before
 * resolving, but not yet honored — a heading-scoped embed transcludes the
 * *whole* note rather than just that section. No backend support for
 * extracting a section exists yet; worth a follow-up once this ships.
 *
 * The nested preview for a note embed is given no `embedSource` of its own,
 * so an `![[…]]` inside an embedded note renders literally rather than
 * resolving — a deliberate one-level depth cap, the simplest way to rule
 * out circular transclusion (A embeds B embeds A) without tracking a
 * resolution chain.
 */
export async function resolveEmbed(
  tree: VaultNode[],
  persona: string,
  ref: string
): Promise<ReactNode> {
  const [rawTarget, sizeHint] = ref.split("|")
  const path = rawTarget?.split("#")[0]?.trim()
  if (!path) return null

  if (IMAGE_EXT.test(path)) {
    const [width, height] = (sizeHint ?? "").split("x").map(parseDimension)
    return <img src={vaultAssetUrl(path, persona)} alt="" width={width} height={height} />
  }

  const node = findNoteByWikilink(tree, path)
  if (!node) return null
  const result = await fetchVaultNote(node.path, persona)
  if (!result) return null
  return <Stylo mode="preview" value={result.content} onChange={() => {}} />
}
