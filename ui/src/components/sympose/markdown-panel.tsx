import * as React from "react"
import { Stylo, splitFrontmatter, type ToolbarConfig } from "@damiro/stylo"
import { languages as CODE_LANGUAGES } from "@codemirror/language-data"
import { toast } from "sonner"
import "@damiro/stylo/styles.css"
import "@damiro/stylo/katex.css"
import { HugeiconsIcon } from "@hugeicons/react"
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
import { fetchVaultNote, saveVaultNote } from "@/lib/vault-note-api"
import { extractWikilinks } from "@/lib/extract-wikilinks"
import type { EditorPreferences } from "@/lib/use-editor-preferences"
import { FrontmatterCard } from "@/components/sympose/frontmatter-card"

/**
 * The markdown editor / reader — the middle stage panel, between `<ContentPanel>`
 * and the chat. When another panel sits to its right its right edge is a drag
 * handle (width free between a third and two-thirds of the stage, cookie-backed
 * via `storageKey`); when nothing does, pass `fill` and it takes the leftover
 * width instead.
 *
 * The editing surface is `stylo` (`@damiro/stylo`) in its default `in-place`
 * mode — frontmatter, headings, and wikilinks render inline in the canvas, so
 * there is no separate read-only mock to keep in sync with the real document.
 * `toolbar.sticky` is deliberately left unset: the panel already gives stylo a
 * bounded height (`min-h-0 flex-1`), so its own toolbar stays pinned as a plain
 * flex sibling of the scrolling canvas — no `position: fixed`, no watchdog.
 *
 * Loading is wired to the vault (`GET /api/vault/note`); saving goes back
 * through `PUT /api/vault/note` (ADR-081). `onSave` recombines the frontmatter
 * card's `---` block with stylo's body and writes the whole note verbatim —
 * driven by the toolbar `save` button and `⌘/Ctrl-S`, or automatically a beat
 * after typing stops when Settings › Markdown editor › Autosave is on.
 */
interface MarkdownPanelProps extends React.ComponentProps<"div"> {
  storageKey?: string
  /** Relative vault path of the note to load. `undefined` shows the empty state. */
  path?: string
  /** Persona handle to scope the `/api/vault/note` request to. */
  persona?: string
  /** Fires when the reader clicks a `[[wikilink]]` in the canvas. */
  onWikiLinkClick?: (target: string) => void
  /** Editing surface/decoration preferences — Settings > Markdown editor. */
  preferences: EditorPreferences
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

/** stylo's default toolbar minus `undo`/`redo`/`link`/`wikilink`/`hr`/`frontmatter`/
 *  `table`/`math` — the same command set the old mock's inert buttons implied,
 *  plus `underline` (opt-in upstream) and `save` (disabled without `onSave`). */
const TOOLBAR_ITEMS: ToolbarConfig = {
  items: [
    "h1",
    "h2",
    "|",
    "bold",
    "italic",
    "underline",
    "strike",
    "|",
    "bulletList",
    "orderedList",
    "|",
    "codeBlock",
    "quote",
    "|",
    "save",
  ],
}

const TOOLBAR_ICONS = {
  h1: <HugeiconsIcon icon={Heading01Icon} className="size-4" />,
  h2: <HugeiconsIcon icon={Heading02Icon} className="size-4" />,
  bold: <HugeiconsIcon icon={TextBoldIcon} className="size-4" />,
  italic: <HugeiconsIcon icon={TextItalicIcon} className="size-4" />,
  underline: <HugeiconsIcon icon={TextUnderlineIcon} className="size-4" />,
  strike: <HugeiconsIcon icon={TextStrikethroughIcon} className="size-4" />,
  bulletList: (
    <HugeiconsIcon icon={LeftToRightListBulletIcon} className="size-4" />
  ),
  orderedList: (
    <HugeiconsIcon icon={LeftToRightListNumberIcon} className="size-4" />
  ),
  codeBlock: <HugeiconsIcon icon={SourceCodeIcon} className="size-4" />,
  quote: <HugeiconsIcon icon={QuoteDownIcon} className="size-4" />,
  save: <HugeiconsIcon icon={FloppyDiskIcon} className="size-4" />,
} as const

type NoteLoadState =
  | { status: "empty" }
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; content: string }

/** How long typing has to pause before an autosave fires (ms). */
const AUTOSAVE_DELAY = 1500

/**
 * Reassemble the full note the way the vault stores it: the frontmatter card's
 * `---` block (its inner text, no fences — same shape `splitFrontmatter` yields)
 * back in front of stylo's body. `null` frontmatter means the note never had a
 * block, so the body is the whole document.
 */
function joinNote(frontmatter: string | null, body: string): string {
  if (frontmatter === null) return body
  return `---\n${frontmatter.replace(/\s+$/, "")}\n---\n\n${body}`
}

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

function MarkdownPanel({
  className,
  storageKey,
  path,
  persona = "samantha",
  onWikiLinkClick,
  preferences,
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

  // Minimum is an eighth of the shell row — the exact rule `<ContentPanel>`
  // uses — so neither working panel can be dragged narrower than the other.
  // Otherwise free up to two-thirds of the split area, defaulting to half; the
  // `|| fallback` covers the first render before anything has been measured.
  const min = React.useCallback(() => Math.round(shellW / 8) || 180, [shellW])
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

  // "empty" is derived straight from `path`, not effect-driven state — nothing
  // to synchronize with an external system until there's a path to fetch. On a
  // note switch the previous note's content is left showing (no loading flash)
  // until the new fetch resolves — the same convention `fetchVaultTree` uses.
  const [fetch, setFetch] = React.useState<Exclude<NoteLoadState, { status: "empty" }>>(
    { status: "loading" }
  )
  const note: NoteLoadState = React.useMemo(
    () => (path ? fetch : { status: "empty" }),
    [path, fetch]
  )
  // The frontmatter card owns the `---` block entirely — stylo's own value
  // never sees it, so editing a pill never touches CodeMirror's undo history.
  const [frontmatter, setFrontmatter] = React.useState<string | null>(null)
  const [body, setBody] = React.useState("")
  const { surface, reveal, selectionUI, focusOutline, autosave } = preferences

  // The note text as last persisted (in `joinNote` form, so the dirty check
  // compares like with like). A save-in-flight guard keeps a slow write or a
  // fast typist from stacking overlapping `PUT`s. `loadedPathRef` is the path
  // whose content is actually in `body`/`frontmatter` right now — on a note
  // switch `path` changes a frame before the fetch resolves, and saving in that
  // gap would write the old body to the new note.
  const savedTextRef = React.useRef<string>("")
  const savingRef = React.useRef(false)
  const loadedPathRef = React.useRef<string | undefined>(undefined)

  React.useEffect(() => {
    if (!path) return
    let alive = true
    fetchVaultNote(path, persona).then((result) => {
      if (!alive) return
      if (!result) {
        setFetch({ status: "error" })
        return
      }
      const split = splitFrontmatter(result.content)
      const fm = split ? split.frontmatter : null
      const bd = split ? split.body : result.content
      setFrontmatter(fm)
      setBody(bd)
      savedTextRef.current = joinNote(fm, bd)
      loadedPathRef.current = path
      setFetch({ status: "ready", content: result.content })
    })
    return () => {
      alive = false
    }
  }, [path, persona])

  // Persist the current frontmatter + body to the vault. Shared by the toolbar
  // `save` button, `⌘/Ctrl-S` (both via stylo's `onSave`), and the autosave
  // timer. No-ops when there is nothing to save or a write is already running;
  // `silent` keeps autosave from toasting on every idle pause.
  const saveNote = React.useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!path || savingRef.current || loadedPathRef.current !== path) return
      const text = joinNote(frontmatter, body)
      if (text === savedTextRef.current) return
      savingRef.current = true
      const result = await saveVaultNote(path, text, persona)
      savingRef.current = false
      if (result.ok) {
        savedTextRef.current = text
        if (!silent) toast.success("Note saved")
      } else {
        toast.error(result.error)
      }
    },
    [path, persona, frontmatter, body]
  )

  // Autosave — a trailing debounce on every body/frontmatter change. Off by
  // default (Settings › Markdown editor); the explicit save paths stay live
  // regardless. Re-armed on each edit, cancelled on unmount / note switch.
  React.useEffect(() => {
    if (autosave !== "on" || note.status !== "ready") return
    const id = window.setTimeout(() => void saveNote({ silent: true }), AUTOSAVE_DELAY)
    return () => window.clearTimeout(id)
  }, [autosave, note.status, saveNote])

  // Outbound `[[wikilinks]]` for the footer — derived from the note as loaded,
  // not from live keystrokes, so typing never re-scans the whole document.
  const links = React.useMemo(
    () => (note.status === "ready" ? extractWikilinks(note.content) : []),
    [note]
  )

  return (
    <div
      ref={wrapRef}
      data-slot="markdown-panel"
      data-state={open ? "open" : "closed"}
      data-dragging={dragging || undefined}
      data-phone={phone || undefined}
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
        {note.status === "empty" && (
          <div className="grid flex-1 place-items-center px-6 text-center text-sm text-fg-muted">
            Select a note to open it here.
          </div>
        )}

        {note.status === "loading" && (
          <div className="grid flex-1 place-items-center px-6 text-center text-sm text-fg-muted">
            Loading…
          </div>
        )}

        {note.status === "error" && (
          <div className="grid flex-1 place-items-center px-6 text-center text-sm text-fg-muted">
            Couldn't load this note.
          </div>
        )}

        {note.status === "ready" && (
          // stylo owns its own toolbar + scrolling canvas as one bounded flex
          // column (`min-h-0` here is what lets its `flex: 1 1 auto` surface
          // scroll internally instead of the toolbar scrolling away with it).
          // The key remounts on a note switch (so CodeMirror's undo history and
          // selection never leak from one note into another) and on a surface/
          // reveal/selectionUI change from Settings — `inPlace` config and mode
          // are both applied-at-mount, per stylo's own documented contract.
          //
          // Full panel width, no reading-column cap — the frontmatter card
          // shares it. The frontmatter card itself rides `toolbar.render`
          // (below) instead of sitting before `<Stylo>`, so it lands *between*
          // the toolbar and the canvas: the toolbar stays the panel's very
          // first row, flush with the stage's floating action group.
          <div
            data-focus-outline={focusOutline}
            className="flex min-h-0 w-full flex-1 flex-col text-sm leading-relaxed"
          >
            <Stylo
              key={`${path}:${surface}:${reveal}:${selectionUI}`}
              value={body}
              onChange={setBody}
              onSave={() => void saveNote()}
              onWikiLinkClick={onWikiLinkClick}
              mode={surface}
              inPlace={{ reveal, selectionUI }}
              toolbar={{
                ...TOOLBAR_ITEMS,
                render: (bar) => (
                  <>
                    {bar}
                    {frontmatter !== null && (
                      <FrontmatterCard
                        raw={frontmatter}
                        onChange={setFrontmatter}
                        onLinkClick={onWikiLinkClick}
                        // `mt-2` — the card's own left/right `mx-2` (see
                        // frontmatter-card.tsx), applied to the top too, so the
                        // toolbar-to-card gap matches the card's own side
                        // margins instead of sitting flush underneath it.
                        // Horizontal *content* padding is the established
                        // gutter (`px-6 sm:px-8`/`px-4` on phone) minus that
                        // same `mx-2`, so the labels still land on the note
                        // body's own left edge rather than double-counting it.
                        className={cn("mt-2", phone ? "px-2" : "px-4 sm:px-6")}
                      />
                    )}
                  </>
                ),
              }}
              icons={TOOLBAR_ICONS}
              codeLanguages={CODE_LANGUAGES}
              placeholder="Start writing…"
              className="h-full min-h-0 flex-1"
            />
            {links.length > 0 && (
              <div
                className={cn(
                  // Same established gutter as the frontmatter card above and
                  // every other panel (`<ChatPanel>`, `<ContentPanel>`).
                  "flex shrink-0 flex-wrap items-center gap-2 border-t border-border py-3",
                  phone ? "px-4" : "px-6 sm:px-8"
                )}
              >
                <span className="font-mono text-xs text-fg-muted uppercase">
                  Links
                </span>
                {links.map((target) => (
                  <button
                    key={target}
                    type="button"
                    onClick={() => onWikiLinkClick?.(target)}
                    className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {target}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
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
