import * as React from "react"

/**
 * `true` for `ms` after `dep` changes, then back to `false`. Skips the initial
 * mount so it never fires on first render.
 *
 * Used to arm a CSS transition only for the moment a panel is deliberately
 * opening or closing. The rest of the time the same width property is being
 * driven per-frame by a neighbour's slide (see `useFillWidth`), and a live
 * transition on it would just make the value lag its target instead of tracking
 * it.
 */
export function useTransientFlag(dep: unknown, ms = 320): boolean {
  const [on, setOn] = React.useState(false)
  const mounted = React.useRef(false)

  React.useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      return
    }
    setOn(true)
    const t = setTimeout(() => setOn(false), ms)
    return () => clearTimeout(t)
  }, [dep, ms])

  return on
}
