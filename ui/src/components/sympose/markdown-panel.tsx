import * as React from "react"
import {
  Stylo,
  splitFrontmatter,
  type TagSource,
  type ToolbarItem,
  type WikiLinkSource,
} from "@damiro/stylo"
import { languages as CODE_LANGUAGES } from "@codemirror/language-data"
import { notify } from "@/lib/notify"
import "@damiro/stylo/styles.css"
import "@damiro/stylo/katex.css"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  CodeIcon,
  FloppyDiskIcon,
  Heading01Icon,
  Heading02Icon,
  Heading03Icon,
  LeftToRightListBulletIcon,
  LeftToRightListNumberIcon,
  LinkIcon,
  ListTodoIcon,
  MathIcon,
  ParagraphIcon,
  QuoteDownIcon,
  RedoIcon,
  Search01Icon,
  SecondBracketIcon,
  SeparatorHorizontalIcon,
  SigmaIcon,
  SourceCodeIcon,
  TableIcon,
  TextBoldIcon,
  TextItalicIcon,
  TextStrikethroughIcon,
  TextUnderlineIcon,
  UndoIcon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { getCookieBool, setCookieBool } from "@/lib/cookies"
import { useResizable } from "@/lib/use-resizable"
import { useFillWidth } from "@/lib/use-fill-width"
import { useTransientFlag } from "@/lib/use-transient-flag"
import {
  useSlideSwap,
  slideEnterClassName,
  slideExitClassName,
} from "@/lib/use-slide-swap"
import { fetchVaultNote, saveVaultNote } from "@/lib/vault-note-api"
import { extractWikilinks } from "@/lib/extract-wikilinks"
import { extractInlineTags } from "@/lib/extract-inline-tags"
import { parseFrontmatter, serializeFrontmatter } from "@/lib/frontmatter"
import type { EditorPreferences } from "@/lib/use-editor-preferences"
import { FrontmatterCard } from "@/components/sympose/frontmatter-card"
import { NoteActionsMenu } from "@/components/sympose/note-actions-menu"
import { ScrollThumb } from "@/components/sympose/scroll-thumb"

// Module-level, not inline: a stable reference so `<ScrollThumb>`'s effect
// (MutationObserver + ResizeObserver + scroll listener) doesn't tear down and
// rebind on every keystroke, which re-renders this component.
const getCmScroller = (el: HTMLElement) => el.querySelector<HTMLElement>(".cm-scroller")

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
  /** Supplies `[[wikilink]]` autocomplete candidates (stylo `>=0.7.0`) — omit
   *  to leave the feature off. Read once, at mount, per stylo's own contract;
   *  the caller is responsible for a stable function identity that reads live
   *  data off a ref rather than being rebuilt on every vault-tree refetch. */
  wikiLinkSource?: WikiLinkSource
  /** Supplies `#tag` autocomplete candidates (stylo `>=0.12.0`) — same
   *  read-once-at-mount contract as `wikiLinkSource` above; omit to leave the
   *  feature off. */
  tagSource?: TagSource
  /** The open note was renamed (ADR-084) — value is its new vault-relative path. */
  onRenamed?: (newPath: string) => void
  /** The open note was moved to trash (ADR-084). */
  onDeleted?: () => void
  /** Is the open note pinned — feeds the toolbar `⋯` menu's Pin/Unpin row,
   *  the same local-only prep state the vault-tree row menu toggles. */
  isPinned?: (path: string) => boolean
  /** Toggle the open note's pinned state. */
  onTogglePin?: (path: string) => void
  /** Editing surface/decoration preferences — Settings > Markdown editor. */
  preferences: EditorPreferences
  /** The toolbar's button set — Settings > Markdown editor >
   *  `<StyloToolbarSettings>`. */
  toolbarItems: ToolbarItem[]
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

/** Stylo's own glyph for "frontmatter" on its built-in toolbar — literal
 *  `fm` text in `<code>` (`src/toolbar/icons.tsx` in `@damiro/stylo`; the
 *  package also has an unrelated SVG path under the same name used only for
 *  its in-place YAML-block decoration, not the toolbar). Sizing/weight
 *  copied from stylo's own `._toolbarButton_ code` CSS rule so it sits at
 *  the same visual weight as the mono glyphs elsewhere in that toolbar. */
function FrontmatterIcon() {
  return (
    <code aria-hidden="true" className="font-mono text-[13px] font-medium">
      fm
    </code>
  )
}

/** One Hugeicons glyph per stylo built-in — the full `ToolbarCommandId` set,
 *  not just sympose's own curated default, since `<StyloToolbarSettings>`
 *  lets any user add any of them from "Available" (Settings > Markdown
 *  editor). Leaving one out isn't a bug — stylo's `DEFAULT_ICONS` falls back
 *  cleanly — but it renders as a visibly different (stylo's own default)
 *  icon style sitting next to these, which is the inconsistency this map
 *  exists to avoid. */
const TOOLBAR_ICONS = {
  undo: <HugeiconsIcon icon={UndoIcon} className="size-4" />,
  redo: <HugeiconsIcon icon={RedoIcon} className="size-4" />,
  save: <HugeiconsIcon icon={FloppyDiskIcon} className="size-4" />,
  search: <HugeiconsIcon icon={Search01Icon} className="size-4" />,
  h1: <HugeiconsIcon icon={Heading01Icon} className="size-4" />,
  h2: <HugeiconsIcon icon={Heading02Icon} className="size-4" />,
  h3: <HugeiconsIcon icon={Heading03Icon} className="size-4" />,
  body: <HugeiconsIcon icon={ParagraphIcon} className="size-4" />,
  bold: <HugeiconsIcon icon={TextBoldIcon} className="size-4" />,
  italic: <HugeiconsIcon icon={TextItalicIcon} className="size-4" />,
  strike: <HugeiconsIcon icon={TextStrikethroughIcon} className="size-4" />,
  underline: <HugeiconsIcon icon={TextUnderlineIcon} className="size-4" />,
  code: <HugeiconsIcon icon={CodeIcon} className="size-4" />,
  codeBlock: <HugeiconsIcon icon={SourceCodeIcon} className="size-4" />,
  link: <HugeiconsIcon icon={LinkIcon} className="size-4" />,
  wikilink: <HugeiconsIcon icon={SecondBracketIcon} className="size-4" />,
  quote: <HugeiconsIcon icon={QuoteDownIcon} className="size-4" />,
  bulletList: (
    <HugeiconsIcon icon={LeftToRightListBulletIcon} className="size-4" />
  ),
  orderedList: (
    <HugeiconsIcon icon={LeftToRightListNumberIcon} className="size-4" />
  ),
  task: <HugeiconsIcon icon={ListTodoIcon} className="size-4" />,
  hr: <HugeiconsIcon icon={SeparatorHorizontalIcon} className="size-4" />,
  frontmatter: <FrontmatterIcon />,
  table: <HugeiconsIcon icon={TableIcon} className="size-4" />,
  math: <HugeiconsIcon icon={MathIcon} className="size-4" />,
  mathBlock: <HugeiconsIcon icon={SigmaIcon} className="size-4" />,
} as const

/** Whether the frontmatter card is expanded or collapsed — a global
 *  preference (like the shell rail / auto-collapse cookies in
 *  `app-shell.tsx`), not per-note: it's a viewing convenience, not part of
 *  the note's own state. */
const FRONTMATTER_VISIBLE_COOKIE = "sympose:pref.frontmatterExpanded"

const SAFE_LINK_SCHEMES = new Set(["http:", "https:", "mailto:"])

/** Opens a plain Markdown `[text](url)` link — stylo hands over the raw
 *  `href` and does no navigation of its own (`onWikiLinkClick`/`wikiLinkSource`
 *  above are the separate `[[wikilink]]` path). Restricted to http(s)/mailto:
 *  a note is vault content, not always authored by the current user, so a
 *  `javascript:`/`data:` URI shouldn't get a free ride into `window.open`.
 *  Anything else (including a relative path to another vault file) is a
 *  silent no-op for now, same as before this was wired up. */
function openMarkdownLink(href: string) {
  let url: URL
  try {
    url = new URL(href, window.location.href)
  } catch {
    return
  }
  if (!SAFE_LINK_SCHEMES.has(url.protocol)) return
  window.open(url.href, "_blank", "noopener,noreferrer")
}

type NoteLoadState =
  | { status: "empty" }
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; content: string }

/** How long typing has to pause before an autosave fires (ms). */
const AUTOSAVE_DELAY = 1500

/**
 * Reassemble the full note the way the vault stores it.
 *
 * - No frontmatter block in the original → the body is the whole document.
 * - Block present but the card never touched it → splice the body back onto the
 *   file's *exact* original prefix (`originalPrefix`), so an unrelated body edit
 *   never reformats the YAML (quote style, indentation, blank lines, CRLFs all
 *   survive).
 * - Card edited a field → re-serialise from its parsed model. Normalising the
 *   block is unavoidable and expected here.
 */
function joinNote(
  frontmatter: string | null,
  body: string,
  originalPrefix: string | null,
  frontmatterEdited: boolean
): string {
  if (frontmatter === null) return body
  if (!frontmatterEdited && originalPrefix !== null) return originalPrefix + body
  return `---\n${frontmatter.replace(/\s+$/, "")}\n---\n\n${body}`
}

/**
 * Additive-only sync on save: any `#tag` found in the body that isn't
 * already in the frontmatter `tags:` list (case-insensitively) gets
 * appended, lowercased — the reverse never happens, so deleting a `#tag`
 * from the body leaves frontmatter untouched. `null`/unparseable frontmatter
 * (no `---` block, or something `parseFrontmatter` can't round-trip) is left
 * alone, same fallback `<FrontmatterCard>` itself uses.
 */
function syncInlineTags(
  frontmatter: string | null,
  body: string
): { frontmatter: string | null; changed: boolean } {
  if (frontmatter === null) return { frontmatter, changed: false }
  const data = parseFrontmatter(frontmatter)
  if (data === null) return { frontmatter, changed: false }

  const existing = Array.isArray(data.tags)
    ? data.tags
    : data.tags != null
      ? [data.tags]
      : []
  const existingLower = new Set(existing.map((t) => String(t).toLowerCase()))
  const additions = extractInlineTags(body).filter((t) => !existingLower.has(t))
  if (additions.length === 0) return { frontmatter, changed: false }

  return {
    frontmatter: serializeFrontmatter({ ...data, tags: [...existing, ...additions] }),
    changed: true,
  }
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
  wikiLinkSource,
  tagSource,
  onRenamed,
  onDeleted,
  isPinned,
  onTogglePin,
  preferences,
  toolbarItems,
  open = true,
  fill = false,
  phone = false,
  style,
  ...props
}: MarkdownPanelProps) {
  const wrapRef = React.useRef<HTMLDivElement>(null)
  const editorScrollRef = React.useRef<HTMLDivElement>(null)
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
  // Expanded/collapsed state of the frontmatter card — toggled from the `⋯`
  // row, persisted globally (same convention as `app-shell.tsx`'s rail /
  // auto-collapse cookies).
  const [frontmatterVisible, setFrontmatterVisible] = React.useState(() =>
    getCookieBool(FRONTMATTER_VISIBLE_COOKIE, true)
  )
  React.useEffect(() => {
    setCookieBool(FRONTMATTER_VISIBLE_COOKIE, frontmatterVisible)
  }, [frontmatterVisible])
  const { surface, reveal, selectionUI, tableEditing, focusOutline, autosave } =
    preferences

  // The note text as last persisted (in `joinNote` form, so the dirty check
  // compares like with like). A save-in-flight guard keeps a slow write or a
  // fast typist from stacking overlapping `PUT`s. `loadedPathRef` is the path
  // whose content is actually in `body`/`frontmatter` right now — on a note
  // switch `path` changes a frame before the fetch resolves, and saving in that
  // gap would write the old body to the new note.
  const savedTextRef = React.useRef<string>("")
  const savingRef = React.useRef(false)
  const loadedPathRef = React.useRef<string | undefined>(undefined)
  // The note's exact `---`…`---` prefix as loaded, and whether the frontmatter
  // card has since edited a field — together these let a body-only save keep
  // the original YAML block byte-for-byte (see `joinNote`).
  const originalPrefixRef = React.useRef<string | null>(null)
  const frontmatterEditedRef = React.useRef(false)

  // stylo's `canvasHeader` (>=0.11.0) is read once, at mount — same contract
  // as `inPlace`/`wikiLinkSource` (see `wikiLinkSource` prop doc above). The
  // function identity handed to `<Stylo>` has to survive `frontmatter`/
  // `onWikiLinkClick`/`phone` changing without a remount, so it reads them
  // off a ref kept current every render instead of closing over them directly.
  const frontmatterCardStateRef = React.useRef({
    frontmatter,
    onWikiLinkClick,
    phone,
    frontmatterVisible,
  })
  frontmatterCardStateRef.current = {
    frontmatter,
    onWikiLinkClick,
    phone,
    frontmatterVisible,
  }
  const canvasHeader = React.useCallback(() => {
    const { frontmatter, onWikiLinkClick, phone, frontmatterVisible } =
      frontmatterCardStateRef.current
    if (frontmatter === null) return null
    return (
      // Animate via `grid-template-rows` rather than `max-height` — it tweens
      // to the card's real content height with no guessed cap, and (unlike a
      // hardcoded `max-height`) never needs revisiting if the card's content
      // grows a row. The `overflow-hidden` inner wrapper is what actually
      // clips it; the outer grid is what animates.
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-mode ease-mode",
          frontmatterVisible ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          <FrontmatterCard
            raw={frontmatter}
            onChange={(raw) => {
              // A real card edit — from here on the block is re-serialised on
              // save rather than kept verbatim.
              frontmatterEditedRef.current = true
              setFrontmatter(raw)
            }}
            onLinkClick={onWikiLinkClick}
            className={cn("mt-2", phone ? "px-2" : "px-4 sm:px-6")}
          />
        </div>
      </div>
    )
  }, [])

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
      const prefix = split
        ? result.content.slice(0, result.content.length - split.body.length)
        : null
      setFrontmatter(fm)
      setBody(bd)
      originalPrefixRef.current = prefix
      frontmatterEditedRef.current = false
      savedTextRef.current = joinNote(fm, bd, prefix, false)
      loadedPathRef.current = path
      setFetch({ status: "ready", content: result.content })
    })
    return () => {
      alive = false
    }
  }, [path, persona])

  // Persist the current frontmatter + body to the vault. Shared by the toolbar
  // `save` button, `⌘/Ctrl-S` (both via stylo's `onSave`), autosave, and the
  // leave-note flush below. `silent` keeps autosave (and the flush) from
  // toasting on every idle pause / note switch. `syncTags` is separate from
  // `silent` — it defaults to "explicit save" (`!silent`) but the flush
  // overrides it back on, since leaving a note silently is still a
  // deliberate-enough moment to finalize its tags (see the flush effect below
  // for why autosave itself must stay excluded).
  const saveNote = React.useCallback(
    async ({
      silent = false,
      syncTags = !silent,
    }: { silent?: boolean; syncTags?: boolean } = {}) => {
      // Targets `loadedPathRef.current` — the note `body`/`frontmatter`
      // state actually holds — rather than the `path` prop directly. On a
      // note switch `path` moves to the next note a frame before its fetch
      // resolves; targeting `path` there would write the *old* body onto
      // the *new* note. `loadedPathRef` only updates once a fetch actually
      // lands, so during that gap it still correctly names the note this
      // state belongs to — which is exactly what the leave-note flush below
      // needs to call this mid-switch without racing it.
      const targetPath = loadedPathRef.current
      if (!targetPath || savingRef.current) return

      // Autosave's 1.5s debounce fires on any typing pause, including
      // mid-word inside a tag the user hasn't finished typing yet (`#cs` on
      // the way to `#css`); syncing there would permanently bake in the
      // half-typed fragment, since the merge is additive-only and never
      // removes a tag once added.
      const synced = syncTags
        ? syncInlineTags(frontmatter, body)
        : { frontmatter, changed: false }
      if (synced.changed) {
        frontmatterEditedRef.current = true
        setFrontmatter(synced.frontmatter)
      }

      const text = joinNote(
        synced.frontmatter,
        body,
        originalPrefixRef.current,
        frontmatterEditedRef.current
      )
      if (text === savedTextRef.current) return
      savingRef.current = true
      const result = await saveVaultNote(targetPath, text, persona)
      savingRef.current = false
      if (result.ok) {
        savedTextRef.current = text
        // Refresh `note.content` from the just-written text so the wikilink
        // footer (derived from `note`, not the live buffer) picks up any
        // `[[links]]` added since the last load — without rescanning on
        // every keystroke.
        setFetch({ status: "ready", content: text })
        if (!silent) notify.success("Note saved")
      } else {
        notify.error(result.error)
      }
    },
    [persona, frontmatter, body]
  )

  // `saveNote` gets a new identity on every keystroke (it closes over
  // `frontmatter`/`body`) — the leave-note flush below needs to call
  // whichever version is current *without* re-running its own effect on
  // every edit, so it reads through this ref (updated every render, a plain
  // assignment — cheap) instead of taking `saveNote` as a dependency.
  const saveNoteRef = React.useRef(saveNote)
  saveNoteRef.current = saveNote

  // Flush a save when leaving this note — switching to another one, or the
  // panel unmounting entirely (a full route change away from `/shell`) — so
  // an edit isn't lost just because autosave is off (its default) and the
  // save button never got hit. `path` is the only dependency, so the
  // cleanup fires exactly on a switch or an unmount, never on every
  // keystroke; by the time it runs, `saveNoteRef.current` already targets
  // `loadedPathRef.current` (see above), which still names the *leaving*
  // note during the gap before the next note's fetch resolves. Silent (no
  // toast — a background flush, not something the user asked for) but still
  // syncs tags: unlike autosave's blind timer, leaving the note is a real
  // "I'm done with this one" signal, not a mid-word coincidence.
  React.useEffect(() => {
    return () => {
      void saveNoteRef.current({ silent: true, syncTags: true })
    }
  }, [path])

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

  // Sideways slide keyed on the open note — there's no back/forward concept
  // for the editor (unlike the content panel), so every note switch (a
  // wikilink, a vault-tree pick, a new note) reads as "forward": it's always
  // pushing a new destination. Sequential rather than a crossfade: the
  // outgoing note finishes sliding out before the incoming one starts
  // sliding in (see `useSlideSwap`).
  const noteBody = (
    <>
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
        // reveal/selectionUI/tableEditing change from Settings — `inPlace`
        // config and mode are both applied-at-mount, per stylo's own
        // documented contract.
        //
        // Full panel width, no reading-column cap — the frontmatter card
        // shares it. The frontmatter card rides `canvasHeader` (stylo
        // >=0.11.0), which docks it *inside* the editing surface, under
        // CodeMirror's own find/replace panel and above the document body
        // — the toolbar row (with the note-actions `⋯`) stays a separate,
        // non-scrolling sibling above the whole canvas.
        <div
          ref={editorScrollRef}
          data-focus-outline={focusOutline}
          className="group/scroll-thumb relative flex min-h-0 w-full flex-1 flex-col text-sm leading-relaxed"
        >
          <Stylo
            key={`${path}:${surface}:${reveal}:${selectionUI}:${tableEditing}`}
            value={body}
            onChange={setBody}
            onSave={() => void saveNote()}
            onWikiLinkClick={onWikiLinkClick}
            wikiLinkSource={wikiLinkSource}
            tagSource={tagSource}
            onLinkClick={openMarkdownLink}
            mode={surface}
            inPlace={{ reveal, selectionUI, table: tableEditing }}
            canvasHeader={canvasHeader}
            toolbar={{
              items: toolbarItems,
              render: (bar) => (
                // stylo's toolbar row, with the note-actions `⋯` overlaid
                // at its right edge (the built-in items are left-aligned,
                // so that space is free). Only shown once a note is open.
                <div className="relative">
                  {bar}
                  {path && (
                    <div className="absolute inset-y-0 right-1.5 flex items-center gap-0.5">
                      {frontmatter !== null && (
                        <button
                          type="button"
                          aria-label={
                            frontmatterVisible
                              ? "Hide frontmatter"
                              : "Show frontmatter"
                          }
                          aria-pressed={frontmatterVisible}
                          onClick={() => setFrontmatterVisible((v) => !v)}
                          className={cn(
                            "grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                            frontmatterVisible && "bg-accent text-foreground"
                          )}
                        >
                          {TOOLBAR_ICONS.frontmatter}
                        </button>
                      )}
                      <NoteActionsMenu
                        path={path}
                        persona={persona}
                        onRenamed={(next) => onRenamed?.(next)}
                        onDeleted={() => onDeleted?.()}
                        pinned={!!isPinned?.(path)}
                        onTogglePin={onTogglePin}
                      />
                    </div>
                  )}
                </div>
              ),
            }}
            icons={TOOLBAR_ICONS}
            codeLanguages={CODE_LANGUAGES}
            placeholder="Start writing…"
            className="h-full min-h-0 flex-1"
          />
          <ScrollThumb containerRef={editorScrollRef} getScroller={getCmScroller} />
          {links.length > 0 && (
            <div
              className={cn(
                // Same established gutter as the frontmatter card above and
                // every other panel (`<ChatPanel>`, `<ContentPanel>`).
                // `sy-note-footer`: matched by `slideExitClassName`/
                // `slideEnterClassName`'s `scopeToCmScroller` branch (see
                // `useSlideSwap`) so a note switch slides this bar the same
                // horizontal direction as the canvas instead of leaving it
                // frozen mid-transition. The plain fade-in below is only for
                // a mount with no switch in play (first link typed into an
                // already-open note) — a re-render with the same links
                // doesn't remount it, so it won't replay on every keystroke.
                "flex shrink-0 flex-wrap items-center gap-2 border-t border-border py-3",
                "sy-note-footer animate-in fade-in-0 duration-thumb",
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
                  // Keyed on `target`, so only a genuinely new pill mounts
                  // (and animates in) — existing ones just re-render.
                  className="animate-in fade-in-0 zoom-in-95 rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors duration-thumb hover:text-foreground"
                >
                  {target}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
  // `hasToolbar` rides frozen alongside the note it describes — an exiting
  // "ready" note must still know to scope its slide-out to `.cm-scroller`
  // once the live `note.status` has already moved past it.
  const {
    displayKey: noteDisplayKey,
    displayPayload: notePayload,
    exitDirection: noteExitDirection,
    enterDirection: noteEnterDirection,
    onExitComplete: onNoteExitComplete,
  } = useSlideSwap(
    path ?? "__empty__",
    { node: noteBody, hasToolbar: note.status === "ready" },
    "forward"
  )
  // Stylo bundles its own toolbar and the CodeMirror canvas into one mounted
  // tree (`toolbar`/`inplace` panes under one shared root — see its
  // stylesheet), so sliding the whole ready-state block would drag the
  // toolbar along with the document. `.cm-scroller` is CodeMirror's own
  // stable, public scroll-viewport class (already relied on for
  // `<ScrollThumb>` above) — scoping the slide to it keeps the toolbar
  // planted while just the document surface moves.
  const noteSlideScope = notePayload.hasToolbar

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
            "absolute inset-0 flex flex-col transition-[opacity,translate] duration-mode ease-mode"
          : cn(
              "relative shrink-0 py-2 pe-2 transition-[margin,opacity] duration-mode ease-mode data-dragging:transition-none",
              // max-width only transitioned while `fill` flips — otherwise it
              // follows the live measurement so the editor glides with a
              // neighbour's slide rather than lagging it
              fillToggling && "transition-[margin,opacity,max-width]"
            ),
        phone && !open && "-translate-x-3",
        // explicit both ways — the stage it sits in is `pointer-events-none`
        // so the ambient nebula (always the bottom of the stack) can be
        // clicked through any *other* empty stretch of it (ADR-088).
        open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
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
      {/* the working surface — a raised panel card on the stage (frosted over
          the ambient nebula, ADR-088); on phone it drops to the plain
          background the chat also sits on */}
      <div
        className={cn(
          "flex h-full w-full flex-col overflow-hidden",
          phone
            ? "text-foreground"
            : "rounded-lg sy-frosted-panel text-panel-foreground"
        )}
      >
        <div
          key={noteDisplayKey}
          className={cn(
            "flex h-full w-full flex-col",
            noteExitDirection
              ? slideExitClassName(noteExitDirection, noteSlideScope)
              : noteEnterDirection &&
                  slideEnterClassName(noteEnterDirection, noteSlideScope)
          )}
          onAnimationEnd={noteExitDirection ? onNoteExitComplete : undefined}
        >
          {notePayload.node}
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

export { MarkdownPanel, TOOLBAR_ICONS }
