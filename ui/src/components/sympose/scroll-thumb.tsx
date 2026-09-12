import * as React from "react"

const MIN_THUMB_PX = 24

function thumbHeightFor(clientHeight: number, scrollHeight: number, trackHeight: number) {
  return Math.max(MIN_THUMB_PX, (clientHeight / scrollHeight) * trackHeight)
}

/**
 * Hand-drawn scrollbar for a native scroll container — a `rail` (the
 * full-height click target, invisible) holding a `thumb` (the visible,
 * draggable piece). Standing in for the native scrollbar (hidden via CSS on
 * whatever `getScroller` resolves to) buys two things it can't do: the hover
 * fade is a real, animatable DOM opacity transition rather than a native
 * `::-webkit-scrollbar-thumb` color change (which Chromium doesn't actually
 * animate), and clicking the rail above/below the thumb pages the scroller —
 * the native track-click behavior lost by hiding the real scrollbar.
 *
 * `containerRef` must point at a `position: relative` ancestor of the actual
 * scrolling element, since the rail's absolute geometry is computed from that
 * element's own rect relative to the container. `getScroller` resolves the
 * scrolling element from the container on every DOM change (a
 * `MutationObserver` on the container drives re-binding) rather than
 * assuming a stable node, since some callers (stylo's `.cm-scroller`) remount
 * their scroller on unrelated prop changes.
 */
export function ScrollThumb({
  containerRef,
  getScroller,
}: {
  containerRef: React.RefObject<HTMLElement | null>
  getScroller: (container: HTMLElement) => HTMLElement | null
}) {
  const railRef = React.useRef<HTMLDivElement>(null)
  const thumbRef = React.useRef<HTMLDivElement>(null)
  const scrollerRef = React.useRef<HTMLElement | null>(null)
  const dragRef = React.useRef<{ startY: number; startTop: number } | null>(null)

  React.useEffect(() => {
    const container = containerRef.current
    const rail = railRef.current
    const thumb = thumbRef.current
    if (!container || !rail || !thumb) return

    const update = () => {
      const scroller = scrollerRef.current
      if (!scroller) return
      const { scrollTop, scrollHeight, clientHeight } = scroller
      if (scrollHeight <= clientHeight + 1) {
        rail.style.display = "none"
        return
      }
      const containerTop = container.getBoundingClientRect().top
      const scrollerRect = scroller.getBoundingClientRect()
      rail.style.display = "block"
      rail.style.top = `${scrollerRect.top - containerTop}px`
      rail.style.height = `${scrollerRect.height}px`
      const thumbHeight = thumbHeightFor(clientHeight, scrollHeight, scrollerRect.height)
      const top =
        (scrollerRect.height - thumbHeight) * (scrollTop / (scrollHeight - clientHeight))
      thumb.style.top = `${top}px`
      thumb.style.height = `${thumbHeight}px`
    }

    const bind = () => {
      const scroller = getScroller(container)
      if (scroller === scrollerRef.current) {
        update()
        return
      }
      scrollerRef.current?.removeEventListener("scroll", update)
      scrollerRef.current = scroller
      scroller?.addEventListener("scroll", update, { passive: true })
      update()
    }

    bind()
    const mo = new MutationObserver(bind)
    mo.observe(container, { childList: true, subtree: true })
    const ro = new ResizeObserver(update)
    ro.observe(container)
    window.addEventListener("resize", update)

    return () => {
      mo.disconnect()
      ro.disconnect()
      window.removeEventListener("resize", update)
      scrollerRef.current?.removeEventListener("scroll", update)
    }
  }, [containerRef, getScroller])

  const onThumbPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const scroller = scrollerRef.current
    if (!scroller) return
    e.preventDefault()
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    dragRef.current = { startY: e.clientY, startTop: scroller.scrollTop }
    e.currentTarget.dataset.dragging = "true"
  }
  const onThumbPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const scroller = scrollerRef.current
    const drag = dragRef.current
    if (!scroller || !drag) return
    const { scrollHeight, clientHeight } = scroller
    const trackHeight = scroller.getBoundingClientRect().height
    const thumbHeight = thumbHeightFor(clientHeight, scrollHeight, trackHeight)
    const scrollableTrack = trackHeight - thumbHeight
    if (scrollableTrack <= 0) return
    const deltaY = e.clientY - drag.startY
    scroller.scrollTop =
      drag.startTop + (deltaY / scrollableTrack) * (scrollHeight - clientHeight)
  }
  const onThumbPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    dragRef.current = null
    delete e.currentTarget.dataset.dragging
  }

  // Clicking the bare rail (not the thumb, which stops this from firing)
  // pages the scroller toward the click, same as a native scrollbar track.
  const onRailPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const scroller = scrollerRef.current
    const thumb = thumbRef.current
    if (!scroller || !thumb) return
    const thumbRect = thumb.getBoundingClientRect()
    const direction = e.clientY < thumbRect.top ? -1 : e.clientY > thumbRect.bottom ? 1 : 0
    if (direction !== 0) scroller.scrollTop += direction * scroller.clientHeight
  }

  return (
    <div
      ref={railRef}
      onPointerDown={onRailPointerDown}
      className="absolute right-0 w-2.5 touch-none"
    >
      <div
        ref={thumbRef}
        onPointerDown={onThumbPointerDown}
        onPointerMove={onThumbPointerMove}
        onPointerUp={onThumbPointerUp}
        onPointerCancel={onThumbPointerUp}
        className="absolute inset-x-0.5 touch-none rounded-full bg-border opacity-0 transition-opacity duration-300 ease-out group-hover/scroll-thumb:opacity-100 data-dragging:opacity-100"
      />
    </div>
  )
}
