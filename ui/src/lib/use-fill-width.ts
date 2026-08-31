import * as React from "react"

/**
 * Width available to a stage panel: its flex parent's inner width minus its own
 * inline-start offset (everything currently to its left). Returned as a real
 * measured pixel value, so transitioning `max-width` / `flex-basis` to and from
 * it tweens the whole distance instead of snapping off a sentinel like `100vw`.
 *
 * It is kept live two ways, because the two things that change it need different
 * hooks:
 *
 * - **`ResizeObserver`** on the stage and every left-hand sibling — catches the
 *   viewport resizing and a neighbour panel being *dragged* (content-box size
 *   changes).
 * - **A per-frame sample while any stage transition runs** — catches a neighbour
 *   panel *sliding in or out*. That animates `margin-inline-start`, a position
 *   change a `ResizeObserver` never reports, yet it is exactly what shifts this
 *   panel's offset and frees (or takes) the width it should adopt. Transition
 *   events bubble, so one listener on the stage covers every panel; the sampler
 *   runs on a self-expiring deadline so a stray `transitionrun` can't leave it
 *   looping.
 */
export function useFillWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [w, setW] = React.useState(0)

  const measure = React.useCallback(() => {
    const el = ref.current
    const stage = el?.parentElement
    if (!el || !stage) return
    setW(Math.max(0, stage.clientWidth - el.offsetLeft))
  }, [ref])

  React.useEffect(() => {
    const el = ref.current
    const stage = el?.parentElement
    if (!el || !stage) return

    measure()

    const ro = new ResizeObserver(measure)
    ro.observe(stage)
    for (let s = el.previousElementSibling; s; s = s.previousElementSibling) {
      ro.observe(s)
    }

    let raf = 0
    let deadline = 0
    const sample = () => {
      measure()
      raf = performance.now() < deadline ? requestAnimationFrame(sample) : 0
    }
    const kick = () => {
      deadline = performance.now() + 600
      if (!raf) raf = requestAnimationFrame(sample)
    }
    // `transitionrun` starts the sampler; `transitionend` gives it one last kick
    // so the final settled width is captured even if a frame was missed.
    stage.addEventListener("transitionrun", kick)
    stage.addEventListener("transitionend", kick)

    return () => {
      ro.disconnect()
      stage.removeEventListener("transitionrun", kick)
      stage.removeEventListener("transitionend", kick)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [measure, ref])

  return w
}
