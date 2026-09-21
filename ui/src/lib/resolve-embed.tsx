import type { ReactNode } from "react"
import { Stylo } from "@damiro/stylo"
import type { VaultNode } from "@/components/sympose"
import { findNoteByWikilink } from "./find-note-by-wikilink"
import { fetchVaultNote } from "./vault-note-api"

/**
 * Resolves one `![[ref]]` note embed for stylo's `embedSource` — its
 * content rendered read-only via a nested `<Stylo mode="preview">`. Returns
 * `null` (stylo's "keep it literal" signal) when `ref` is empty, doesn't
 * resolve to a note in the sandboxed tree, or the note fetch fails. Image
 * embeds aren't handled — asset serving isn't implemented on the backend.
 *
 * A `#Heading` / `#^blockid` suffix is recognized and stripped before
 * resolving, but not yet honored — a heading-scoped embed transcludes the
 * *whole* note rather than just that section. No backend support for
 * extracting a section exists yet; worth a follow-up once this ships.
 *
 * The nested preview is given no `embedSource` of its own, so an `![[…]]`
 * inside an embedded note renders literally rather than resolving — a
 * deliberate one-level depth cap, the simplest way to rule out circular
 * transclusion (A embeds B embeds A) without tracking a resolution chain.
 */
export async function resolveEmbed(
  tree: VaultNode[],
  persona: string,
  ref: string
): Promise<ReactNode> {
  const rawTarget = ref.split("|")[0]
  const path = rawTarget?.split("#")[0]?.trim()
  if (!path) return null

  const node = findNoteByWikilink(tree, path)
  if (!node) return null
  const result = await fetchVaultNote(node.path, persona)
  if (!result) return null
  return <Stylo mode="preview" value={result.content} onChange={() => {}} softBreaks />
}
