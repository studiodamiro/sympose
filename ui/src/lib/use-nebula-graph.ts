import * as React from "react"

import { buildMasterGraph, type NebulaGraph } from "@/lib/nebula-graph"
import rawMock from "@/lib/mock-nebula.json"

/** Which feed is on screen — the live vault or the bundled offline sample. */
export type NebulaGraphSource = "sample" | "live"

export interface NebulaGraphState {
  /** Master graph (notes + pre-indexed tag hubs), ready for the renderers. */
  graph: NebulaGraph
  /** `"live"` once `GET /api/vault/graph` has answered with nodes. */
  source: NebulaGraphSource
}

const MOCK_MASTER = buildMasterGraph(rawMock as NebulaGraph)
const EMPTY_LIVE = buildMasterGraph({ nodes: [], links: [] })

/**
 * The Knowledge Nebula's data feed. First paint (and the offline fallback) is
 * the bundled `mock-nebula.json`; once `GET /api/vault/graph` answers with
 * an answer (even an empty one) we swap to the live vault and flip `source`
 * to `"live"`; the sample only shows while the backend is unreachable. The endpoint
 * is scoped to the active persona's allowed folders (ADR 010), so `persona`
 * is both a request parameter and a refetch trigger: switching to a
 * restricted persona must not leave the previous persona's wider graph on
 * screen, including when the new fetch fails (see the reset effect below).
 *
 * Shared by the in-shell ambient layer and the standalone `/nebula` showcase
 * so both read exactly one implementation of the fetch + fold.
 *
 * `refreshKey` (opaque; compared by `===` in the effect's dependency array)
 * is the refetch trigger for everything that isn't `persona` — the app shell
 * bumps it after switching the active vault (ADR 003) *and* after creating a
 * note, since the graph is scoped to whichever vault is active and otherwise
 * has no signal that either happened. `vaultPath` (the active vault, when the
 * caller has one) is deliberately *not* also a refetch trigger — the
 * endpoint takes no vault parameter (the backend always answers for
 * whichever vault is active server-side right now), so adding it to that
 * effect's dependency array would only add a redundant refetch the moment
 * it goes from unknown to known at startup, with no server-side change
 * behind it. It still drives its own, separate effect below, purely to
 * decide whether a *failed* fetch should clear the graph — see the
 * `.catch` branch for why a failure needs to tell a real vault switch
 * apart from a same-vault trigger like a note create.
 */
export function useNebulaGraph(
  refreshKey?: unknown,
  vaultPath?: string | null,
  persona?: string
): NebulaGraphState {
  const [state, setState] = React.useState<NebulaGraphState>({
    graph: MOCK_MASTER,
    source: "sample",
  })
  // Whether the currently-displayed graph is known to match `vaultPath` and
  // `persona` — cleared whenever either changes (a persona switch can
  // narrow what's visible just as a vault switch changes it entirely), set again once a fetch (any
  // fetch, whatever triggered it) actually succeeds. Declared as its own
  // effect, before the fetch effect below, so on a commit where a vault
  // switch changes both `vaultPath` and `refreshKey` at once, this one
  // always clears the flag first (effects run in declaration order) —
  // simpler and race-free compared to comparing two independently-updated
  // "which vault" values, which could disagree depending on whether this
  // hook's own fetch or the caller's separate `GET /api/vaults` happens to
  // resolve first.
  //
  // Known, accepted gap: `vaultPath` also transitions once at startup, from
  // unknown (`null`) to the real vault, with no fetch of its own (see the
  // module doc comment on why that transition alone doesn't refetch) — so
  // it clears this flag too, even though nothing about the vault actually
  // changed. A transient failure on the *next* unrelated refetch trigger
  // (e.g. a note create) would, in that narrow window, be misclassified as
  // a real switch and reset an already-correct graph. Fully closing this
  // would need the backend to echo back which vault a response answers
  // for, since the client is otherwise only ever guessing from timing — not
  // worth that API change for a compound, low-odds edge case that's still
  // strictly rarer (and lower-impact) than the bug this mechanism exists
  // to fix in the first place.
  const vaultConfirmedRef = React.useRef(false)
  React.useEffect(() => {
    vaultConfirmedRef.current = false
  }, [vaultPath, persona])

  React.useEffect(() => {
    let cancelled = false
    const query = persona ? `?persona=${encodeURIComponent(persona)}` : ""
    fetch(`/api/vault/graph${query}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: NebulaGraph) => {
        if (cancelled) return
        vaultConfirmedRef.current = true
        if (Array.isArray(data?.nodes)) {
          // An empty answer is a real answer: a persona whose allowed
          // folders hold no notes (or a vault with none yet) gets an empty
          // nebula, not the bundled sample — the sample's mock notes and
          // tags don't exist in that vault, and would also feed the
          // editor's `#tag` autocomplete. Also what clears a previous
          // persona's/vault's graph on a switch to an empty one.
          setState({
            graph: data.nodes.length ? buildMasterGraph(data) : EMPTY_LIVE,
            source: "live",
          })
          console.info(
            `[nebula] live vault · ${data.nodes.length} notes, ${data.links?.length ?? 0} links from /api/vault/graph`
          )
        } else {
          setState({ graph: MOCK_MASTER, source: "sample" })
          console.info(
            "[nebula] /api/vault/graph returned an unexpected shape — showing the bundled sample"
          )
        }
      })
      .catch((err) => {
        if (cancelled) return
        // Same reasoning as the empty-response branch above — a failed
        // request on a real vault switch must not leave the previous
        // vault's graph on screen under the new vault's name — but
        // `refreshKey` also bumps for a same-vault trigger (a note was
        // created), where the vault hasn't changed at all. Only reset when
        // `vaultPath` changed since the last confirmed success: a
        // transient failure on the latter would otherwise blank out a
        // perfectly good, still-current graph over nothing more than a
        // network hiccup unrelated to which vault is active.
        if (!vaultConfirmedRef.current) {
          setState({ graph: MOCK_MASTER, source: "sample" })
          console.info(
            `[nebula] /api/vault/graph unreachable (${err}) — showing the bundled sample`
          )
        } else {
          console.info(
            `[nebula] /api/vault/graph unreachable (${err}) — keeping the last-loaded graph`
          )
        }
      })
    return () => {
      cancelled = true
    }
  }, [refreshKey, persona])

  return state
}
