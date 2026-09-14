import * as React from "react"
import { createPortal } from "react-dom"
import { HugeiconsIcon } from "@hugeicons/react"
import { Copy01Icon, Tick02Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { useTransientFlag } from "@/lib/use-transient-flag"

// Mirrors the same regex stylo's own `Preview` bundle runs against a fenced
// block's `language-xxx` class (`src/render/Preview.tsx`'s `code()`
// override) to decide whether to syntax-highlight it — that class survives
// onto the rendered `<code>` either way (highlighted or not, per that same
// source), so reading it back here gets the fence's language for free
// without stylo needing to expose it as its own prop or data attribute.
const LANGUAGE_CLASS_RE = /language-(\w+)/

/**
 * Copy affordance (plus the fence's language, if any) portaled into one
 * rendered `<pre>` fenced code block's top-right corner. `pre` itself is
 * forced `position: relative` (stylo's own preview CSS leaves it static) so
 * this can anchor to that block specifically rather than the whole preview
 * surface.
 */
function CodeBlockOverlay({ pre }: { pre: HTMLPreElement }) {
  const [copiedAt, setCopiedAt] = React.useState(0)
  const copied = useTransientFlag(copiedAt || null, 1200)
  const language = pre.querySelector("code")?.className.match(LANGUAGE_CLASS_RE)?.[1]

  const handleClick = async () => {
    const code = pre.querySelector("code")?.textContent ?? pre.textContent ?? ""
    try {
      await navigator.clipboard.writeText(code)
      setCopiedAt(Date.now())
    } catch {
      // Clipboard permission denied/unavailable — silent no-op, same
      // fallback style as `openMarkdownLink`'s unsupported-scheme case.
    }
  }

  return (
    <div className="absolute top-1.5 right-1.5 flex items-center gap-1.5">
      {language && (
        <span className="select-none font-mono text-[10px] leading-none tracking-wide text-fg-muted/70 uppercase">
          {language}
        </span>
      )}
      <button
        type="button"
        aria-label={copied ? "Copied" : "Copy code"}
        onClick={handleClick}
        className={cn(
          "grid size-6 place-items-center rounded-md text-fg-muted opacity-60 transition-opacity hover:bg-accent hover:text-foreground hover:opacity-100 focus-visible:opacity-100",
          copied && "text-ok opacity-100"
        )}
      >
        <HugeiconsIcon icon={copied ? Tick02Icon : Copy01Icon} className="size-3.5" />
      </button>
    </div>
  )
}

/**
 * Decorates every fenced code block inside `containerRef`'s rendered
 * Markdown with a `<CodeBlockOverlay>` — stylo's own preview output has no
 * copy control (`@damiro/stylo` is a fixed dependency; this layers sympose's
 * own UI onto its DOM from the outside rather than patching it, the same
 * approach `<ScrollThumb>` uses for the scrollbar in `markdown-panel.tsx`).
 *
 * Re-scans on any DOM change under `containerRef` — stylo swaps its whole
 * preview tree on a note switch, and can grow new code blocks later (e.g. a
 * resolved `![[embed]]`) without remounting the container itself.
 */
export function CodeBlockCopyButtons({
  containerRef,
  active,
}: {
  containerRef: React.RefObject<HTMLElement | null>
  active: boolean
}) {
  const [blocks, setBlocks] = React.useState<HTMLPreElement[]>([])

  // `active` turning off clears the list immediately, during render, rather
  // than waiting a tick for the effect below to catch up.
  const [prevActive, setPrevActive] = React.useState(active)
  if (active !== prevActive) {
    setPrevActive(active)
    if (!active) setBlocks([])
  }

  React.useEffect(() => {
    if (!active) return
    const container = containerRef.current
    if (!container) return

    const scan = () => {
      const found = Array.from(container.querySelectorAll<HTMLPreElement>("pre"))
      for (const pre of found) pre.style.position ||= "relative"
      setBlocks(found)
    }
    scan()
    const mo = new MutationObserver(scan)
    mo.observe(container, { childList: true, subtree: true })
    return () => mo.disconnect()
  }, [containerRef, active])

  if (!active) return null
  return (
    <>
      {blocks.map((pre, i) =>
        createPortal(<CodeBlockOverlay pre={pre} />, pre, i)
      )}
    </>
  )
}
