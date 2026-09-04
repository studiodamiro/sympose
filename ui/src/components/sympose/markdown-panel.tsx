import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import type { IconSvgElement } from "@hugeicons/react"
import {
  FloppyDiskIcon,
  Heading01Icon,
  Heading02Icon,
  LeftToRightListBulletIcon,
  LeftToRightListNumberIcon,
  QuoteDownIcon,
  SourceCodeIcon,
  TextBoldIcon,
  TextItalicIcon,
  TextStrikethroughIcon,
  TextUnderlineIcon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { useResizable } from "@/lib/use-resizable"
import { useFillWidth } from "@/lib/use-fill-width"
import { useTransientFlag } from "@/lib/use-transient-flag"

/**
 * The markdown editor / reader — the middle stage panel, between `<ContentPanel>`
 * and the chat. When another panel sits to its right its right edge is a drag
 * handle (width free between a third and two-thirds of the stage, cookie-backed
 * via `storageKey`); when nothing does, pass `fill` and it takes the leftover
 * width instead.
 *
 * Scope for now is a *reader* with an editing chrome on top — the toolbar marks
 * are inert placeholders. What a first cut should carry, and why:
 *
 * - A frontmatter header (title / date / agent / tags) — every vault note is a
 *   YAML-front-matter markdown file; surfacing it read-only anchors the note's
 *   identity without a raw `---` block.
 * - Prose with a real type hierarchy (heading, body, blockquote) at a capped
 *   measure — this is a reading surface first.
 * - Inline `[[wikilinks]]`, de-bracketed and in `--brand` for reader mode, plus
 *   an outbound-links footer — the vault is a graph; links are load-bearing.
 * - A minimal toolbar (H1 / H2 · bold / italic / underline / strike · lists ·
 *   code · quote) and a save action. No heading-level dropdown, no tables UI,
 *   no slash menu yet — those are the second pass.
 */
interface MarkdownPanelProps extends React.ComponentProps<"div"> {
  storageKey?: string
  /**
   * Revealed when true (default), collapsed when false. The panel stays mounted
   * either way and transitions its width / opacity / offset, so it fades and
   * slides in from the left on reveal and back out on hide.
   */
  open?: boolean
  /**
   * Grow into the leftover stage width (in addition to the dragged basis) —
   * used when nothing sits to the editor's right, so it occupies the chat's
   * area. No resize handle in this mode. Only meaningful while `open`.
   */
  fill?: boolean
  /**
   * Phone shell: fill the view (no dragged width, no handle) and drop the card
   * — no `bg-panel`, no rounding, no elevation — so the editor reads on the same
   * plain background as the chat.
   */
  phone?: boolean
}

interface Frontmatter {
  title: string
  date: string
  agent: string
  tags: string[]
}

const SAMPLE_FRONTMATTER: Frontmatter = {
  title: "Fonts particular weight",
  date: "2060-08-24",
  agent: "Samantha",
  tags: ["jour", "projects", "finance", "virginia"],
}

const SAMPLE_LINKS = ["mapping", "designer", "fonts"]

/**
 * Live width of an ancestor `levels` up from `ref`. `<ContentPanel>` reads its
 * parent once on mount because that parent is the viewport-wide shell row; this
 * panel's parent is a derived flex child that only settles a frame after
 * `<ContentPanel>` commits, so it has to observe. Level 1 is the split area
 * (drives max / default); level 2 is that same shell row (drives the minimum,
 * so it lines up with `<ContentPanel>`'s).
 */
function useAncestorWidth(
  ref: React.RefObject<HTMLElement | null>,
  levels: number
): number {
  const [w, setW] = React.useState(0)
  React.useEffect(() => {
    let el: HTMLElement | null = ref.current
    for (let i = 0; i < levels && el; i++) el = el.parentElement
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setW(entry.contentRect.width))
    ro.observe(el)
    setW(el.getBoundingClientRect().width)
    return () => ro.disconnect()
  }, [ref, levels])
  return w
}

/** One mark button in the toolbar — inert in this mock. */
function MarkButton({ icon, label }: { icon: IconSvgElement; label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      className="grid size-8 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <HugeiconsIcon icon={icon} className="size-4" />
    </button>
  )
}

/** A cluster of related mark buttons — clusters wrap as units on narrow widths. */
function MarkGroup({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center gap-0.5">{children}</div>
}

/** Reader-mode wikilink — de-bracketed, `--brand`, opens the note on click. */
function DocLink({ children }: { children: React.ReactNode }) {
  return (
    <button
      type="button"
      className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {children}
    </button>
  )
}

function MarkdownPanel({
  className,
  storageKey,
  open = true,
  fill = false,
  phone = false,
  style,
  ...props
}: MarkdownPanelProps) {
  const wrapRef = React.useRef<HTMLDivElement>(null)
  const stageW = useAncestorWidth(wrapRef, 1)
  const shellW = useAncestorWidth(wrapRef, 2)
  // Space actually free to the editor's right — what it grows to when filling,
  // remeasured every frame while a panel slides.
  const availW = useFillWidth(wrapRef)
  // Arm the max-width transition only while `fill` is actually flipping. The
  // rest of the time max-width follows the live measurement instantly, so the
  // editor tracks the content panel sliding out instead of lagging behind it.
  const fillToggling = useTransientFlag(fill)

  // Minimum is a quarter of the shell row — the exact rule `<ContentPanel>`
  // uses — so neither working panel can be dragged narrower than the other.
  // Otherwise free up to two-thirds of the split area, defaulting to half; the
  // `|| fallback` covers the first render before anything has been measured.
  const min = React.useCallback(() => Math.round(shellW / 4) || 360, [shellW])
  const max = React.useCallback(
    () => Math.round((stageW * 2) / 3) || 9999,
    [stageW]
  )
  const defaultSize = React.useCallback(
    () => Math.round(stageW / 2) || 480,
    [stageW]
  )

  const { size, dragging, handleProps } = useResizable({
    min,
    max,
    defaultSize,
    storageKey,
  })

  const fm = SAMPLE_FRONTMATTER

  return (
    <div
      ref={wrapRef}
      data-slot="markdown-panel"
      data-state={open ? "open" : "closed"}
      data-dragging={dragging || undefined}
      className={cn(
        // same wrapper insets as <ContentPanel>: py-2 top/bottom margin, pe-2
        // right margin — so the gap to <ContentPanel> (its pe-2), the gap to the
        // chat (this pe-2), and the panel's top/bottom margins are all one step.
        // z-10: sits below <ContentPanel> (z-20) but above the chat slot (z-0),
        // so a parked panel is always hidden behind its left-hand neighbour and
        // appears to slide out from that neighbour's right edge.
        "group/md z-10 min-w-0 data-dragging:select-none",
        phone
          ? // phone: one surface at a time — an absolute layer that crossfades
            // and slides a touch from the left on reveal
            "absolute inset-0 flex flex-col transition-[opacity,translate] duration-300 ease-in-out"
          : cn(
              "relative shrink-0 py-2 pe-2 transition-[margin,opacity] duration-300 ease-in-out data-dragging:transition-none",
              // max-width only transitioned while `fill` flips — otherwise it
              // follows the live measurement so the editor glides with a
              // neighbour's slide rather than lagging it
              fillToggling && "transition-[margin,opacity,max-width]"
            ),
        phone && !open && "-translate-x-3",
        open ? "opacity-100" : "pointer-events-none opacity-0",
        className
      )}
      style={
        phone
          ? style
          : {
              // Always growable, but clamped: to the dragged width normally, to
              // the space actually free to its right when filling. Both are real
              // measured pixels, so animating the clamp tweens the editor across
              // the whole distance as the chat panel comes and goes — in lockstep
              // with the chat slot's own flex-basis tween. (An oversized clamp
              // like `100vw` would burn most of the duration invisibly, then
              // snap — the old jerk.)
              flexBasis: size,
              flexGrow: 1,
              maxWidth: fill ? availW || size : size,
              marginInlineStart: open ? 0 : -size,
              ...style,
            }
      }
      {...props}
    >
      {/* the working surface — a raised `bg-panel` card on the stage; on phone
          it drops to the plain background the chat also sits on */}
      <div
        className={cn(
          "flex h-full w-full flex-col overflow-hidden",
          phone
            ? "text-foreground"
            : "rounded-lg bg-panel text-panel-foreground"
        )}
      >
        {/* toolbar — the mark clusters wrap to multiple rows on narrow widths
            (tablet); the save action stays pinned to the top-right corner. When
            the editor fills the stage, extra end padding clears the floating
            chat action group that overlaps this corner. */}
        <div
          className={cn(
            "flex shrink-0 items-start justify-between gap-2 py-2",
            // no divider on phone — the editor is a plain surface there; the
            // toolbar's gutter matches the chat panel's (`px-4`)
            phone ? "ps-4 pe-4" : "border-b border-border ps-3",
            !phone && (fill ? "pe-24" : "pe-3")
          )}
        >
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <MarkGroup>
              <MarkButton icon={Heading01Icon} label="Heading 1" />
              <MarkButton icon={Heading02Icon} label="Heading 2" />
            </MarkGroup>
            <MarkGroup>
              <MarkButton icon={TextBoldIcon} label="Bold" />
              <MarkButton icon={TextItalicIcon} label="Italic" />
              <MarkButton icon={TextUnderlineIcon} label="Underline" />
              <MarkButton icon={TextStrikethroughIcon} label="Strikethrough" />
            </MarkGroup>
            <MarkGroup>
              <MarkButton
                icon={LeftToRightListBulletIcon}
                label="Bullet list"
              />
              <MarkButton
                icon={LeftToRightListNumberIcon}
                label="Numbered list"
              />
            </MarkGroup>
            <MarkGroup>
              <MarkButton icon={SourceCodeIcon} label="Code block" />
              <MarkButton icon={QuoteDownIcon} label="Blockquote" />
            </MarkGroup>
          </div>
          <button
            type="button"
            aria-label="Save note"
            className="grid size-8 shrink-0 place-items-center self-start rounded-md text-brand transition-colors hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <HugeiconsIcon icon={FloppyDiskIcon} className="size-4" />
          </button>
        </div>

        {/* document — on phone the gutter matches the chat panel's (`px-4`) */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div
            className={cn(
              "mx-auto flex max-w-[68ch] flex-col gap-6",
              phone ? "px-4 py-6" : "px-6 py-6 sm:px-8"
            )}
          >
            {/* frontmatter — inverted to bg-background so it lifts off the
                panel fill (--card is not distinct from --background in light) */}
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 rounded-lg border border-border bg-background p-4 font-mono text-xs">
              <dt className="text-fg-muted uppercase">Title</dt>
              <dd className="text-foreground">{fm.title}</dd>
              <dt className="text-fg-muted uppercase">Date</dt>
              <dd className="text-foreground">{fm.date}</dd>
              <dt className="text-fg-muted uppercase">Agent</dt>
              <dd className="text-foreground">{fm.agent}</dd>
              <dt className="text-fg-muted uppercase">Tags</dt>
              <dd className="text-foreground">{fm.tags.join(", ")}</dd>
            </dl>

            {/* prose */}
            <article className="flex flex-col gap-4 text-sm leading-relaxed text-muted-foreground">
              <h2 className="font-heading text-lg font-semibold text-fg-strong">
                {fm.title}
              </h2>
              <p>
                Most fonts have a particular weight which corresponds to one of
                the numbers in <DocLink>Common weight name mapping</DocLink>.
                However some fonts, called variable fonts, can support a range
                of weights with a more or less fine granularity, and this can
                give the <DocLink>designer</DocLink> a much closer degree of
                control over the chosen weight.
              </p>
              <blockquote className="border-l-2 border-border pl-4 text-fg-muted italic">
                a man who chooses to enjoy a pleasure that has no annoying
                consequences
              </blockquote>
              <p>
                However some fonts, called variable fonts, can support a range
                of weights with a more or less fine granularity, and this can
                give the designer a much closer degree of control over the
                chosen weight.
              </p>
            </article>

            {/* outbound links */}
            <div className="flex flex-col gap-2 border-t border-border pt-4">
              <span className="font-mono text-xs text-fg-muted uppercase">
                Links
              </span>
              <div className="flex flex-wrap gap-2">
                {SAMPLE_LINKS.map((l) => (
                  <button
                    key={l}
                    type="button"
                    className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* right-edge resize handle — mirrors <ContentPanel>; gone when filling
          or on phone (full-view, no dragged width) */}
      {!fill && !phone && (
        <div
          {...handleProps}
          aria-label="Resize editor"
          className="group/md-handle absolute inset-y-0 right-0 z-10 w-1.5 cursor-col-resize touch-none"
        >
          <span className="absolute inset-y-0 right-0 w-px bg-transparent transition-colors group-hover/md-handle:bg-border group-focus-visible/md-handle:bg-brand group-data-dragging/md:bg-brand" />
        </div>
      )}
    </div>
  )
}

export { MarkdownPanel }
