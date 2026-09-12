import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowLeft01Icon,
  ArrowRight01Icon,
  Search01Icon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { fetchVaultSearch } from "@/lib/vault-search-api"
import type { FlatVaultMatch } from "@/components/sympose/vault-tree"

const MIN_QUERY_LENGTH = 2
const DEBOUNCE_MS = 300

interface Row {
  path: string
  /** The one-line reason caption — matched tag, wikilink, or content
   *  snippet. Empty for a plain path/folder-name match, since the row's own
   *  path already makes that obvious. */
  detail: string
}

/**
 * Everything a search finds beyond the folder currently in view, as one flat,
 * paginated list (pathname + a one-line reason — no folder nesting, per
 * damiro: "we dont need to display the folder"). Two sources merged:
 *  - `instantMatches` — name/tag/wikilink hits from `flatSearchTree`,
 *    computed client-side by the shell with zero latency.
 *  - a debounced `GET /api/vault/search` call owned by this component,
 *    which adds `content` hits (the one thing the client can't do — it
 *    never has note bodies in memory) and any `tag` hits the instant pass
 *    missed. Rows already covered by `instantMatches` are deduped by path.
 * `match_type: "title"` backend rows are dropped outright — a filename hit
 * is already covered by `instantMatches`' own path matching.
 */
function VaultContentSearch({
  persona,
  query,
  folderLabel,
  instantMatches,
  resultsPerPage,
  onSelect,
  className,
}: {
  persona: string
  query: string
  /** Name of the folder currently in view, for the "N matches beyond X"
   *  caption — e.g. "Code". */
  folderLabel: string
  instantMatches: FlatVaultMatch[]
  /** Rows shown per page (Settings → Search → Results per page). */
  resultsPerPage: number
  /** A result row was picked — vault-relative path of the note. */
  onSelect: (path: string) => void
  className?: string
}) {
  const [contentRows, setContentRows] = React.useState<Row[]>([])
  const [loading, setLoading] = React.useState(false)
  const [page, setPage] = React.useState(0)
  const trimmed = query.trim()

  React.useEffect(() => {
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setContentRows([])
      setLoading(false)
      return
    }
    setLoading(true)
    let alive = true
    const controller = new AbortController()
    const handle = window.setTimeout(() => {
      fetchVaultSearch(trimmed, persona, controller.signal).then((rows) => {
        if (!alive) return
        setContentRows(
          rows
            .filter((r) => r.match_type !== "title")
            .map((r) => ({ path: r.rel_path, detail: r.snippet }))
        )
        setLoading(false)
      })
    }, DEBOUNCE_MS)
    return () => {
      alive = false
      controller.abort()
      window.clearTimeout(handle)
    }
  }, [trimmed, persona])

  // A new query (or a changed page size) starts back at page 1 — otherwise a
  // narrower follow-up query could leave `page` pointing past the new,
  // shorter result list.
  React.useEffect(() => {
    setPage(0)
  }, [trimmed, persona, resultsPerPage])

  if (trimmed.length < MIN_QUERY_LENGTH) return null

  const instantRows: Row[] = instantMatches.map((m) => ({
    path: m.node.path,
    detail:
      m.reason === "tag"
        ? `#${m.detail}`
        : m.reason === "link"
          ? `↔ ${m.detail}`
          : "",
  }))
  const seen = new Set(instantRows.map((r) => r.path))
  const rows = [...instantRows, ...contentRows.filter((r) => !seen.has(r.path))]
  const pageCount = Math.max(1, Math.ceil(rows.length / resultsPerPage))
  const clampedPage = Math.min(page, pageCount - 1)
  const pageRows = rows.slice(
    clampedPage * resultsPerPage,
    (clampedPage + 1) * resultsPerPage
  )

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center gap-1.5 pt-2 pb-1">
        <HugeiconsIcon icon={Search01Icon} className="size-3 text-fg-muted" />
        <span className="text-xs text-fg-muted">
          {rows.length === 0
            ? loading
              ? `Searching beyond ${folderLabel}…`
              : `No matches beyond ${folderLabel}`
            : `${rows.length} match${rows.length === 1 ? "" : "es"} beyond ${folderLabel}${loading ? "…" : ""}`}
        </span>
      </div>
      {pageRows.map((r) => (
        <button
          key={r.path}
          type="button"
          onClick={() => onSelect(r.path)}
          className="flex min-w-0 flex-col items-start gap-0.5 rounded-md px-1.5 py-1 text-left transition-colors hover:bg-accent"
        >
          <span className="w-full truncate font-mono text-sm text-entity/85">
            {r.path}
          </span>
          {r.detail && (
            <span className="line-clamp-1 w-full text-xs text-fg-muted">
              {r.detail}
            </span>
          )}
        </button>
      ))}
      {pageCount > 1 && (
        <div className="flex items-center justify-between pt-1">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={clampedPage === 0}
            aria-label="Previous page"
            className="grid size-6 shrink-0 place-items-center rounded-md text-fg-muted transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
          >
            <HugeiconsIcon icon={ArrowLeft01Icon} className="size-3.5" />
          </button>
          <span className="text-[11px] text-fg-muted">
            Page {clampedPage + 1} of {pageCount}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={clampedPage >= pageCount - 1}
            aria-label="Next page"
            className="grid size-6 shrink-0 place-items-center rounded-md text-fg-muted transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
          >
            <HugeiconsIcon icon={ArrowRight01Icon} className="size-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}

export { VaultContentSearch }
