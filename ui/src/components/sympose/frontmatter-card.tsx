import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Cancel01Icon, PlusSignIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import {
  parseFrontmatter,
  serializeFrontmatter,
  type FrontmatterData,
  type FrontmatterScalar,
} from "@/lib/frontmatter"
import { parseWikilink } from "@/lib/extract-wikilinks"

/** One frontmatter list value as a removable pill. */
function Pill({ children, onRemove }: { children: React.ReactNode; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-chip px-2 py-0.5 text-xs text-chip-foreground">
      {children}
      <button
        type="button"
        aria-label="Remove"
        onClick={onRemove}
        className="grid size-3.5 place-items-center rounded-full text-fg-muted transition-colors hover:bg-accent hover:text-foreground"
      >
        <HugeiconsIcon icon={Cancel01Icon} className="size-3" />
      </button>
    </span>
  )
}

/** A pill's label — a `[[wikilink]]` renders as a clickable link, brackets dropped. */
function PillLabel({
  value,
  onLinkClick,
}: {
  value: FrontmatterScalar
  onLinkClick?: (target: string) => void
}) {
  const link = typeof value === "string" ? parseWikilink(value) : null
  if (!link) return <>{String(value)}</>
  return (
    <button
      type="button"
      onClick={() => onLinkClick?.(link.target)}
      className="text-entity underline-offset-2 hover:underline"
    >
      {link.label}
    </button>
  )
}

/** A frontmatter array field — its items as pills, plus an "add" affordance. */
function PillRow({
  values,
  onChange,
  onLinkClick,
}: {
  values: FrontmatterScalar[]
  onChange: (next: FrontmatterScalar[]) => void
  onLinkClick?: (target: string) => void
}) {
  const [adding, setAdding] = React.useState(false)
  const [draft, setDraft] = React.useState("")
  const inputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (adding) inputRef.current?.focus()
  }, [adding])

  const commitAdd = () => {
    const trimmed = draft.trim()
    if (trimmed) onChange([...values, trimmed])
    setDraft("")
    setAdding(false)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {values.map((v, i) => (
        <Pill key={i} onRemove={() => onChange(values.filter((_, j) => j !== i))}>
          <PillLabel value={v} onLinkClick={onLinkClick} />
        </Pill>
      ))}
      {adding ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitAdd}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitAdd()
            if (e.key === "Escape") {
              setDraft("")
              setAdding(false)
            }
          }}
          className="h-5 w-20 rounded-full border border-border bg-background px-2 text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
      ) : (
        <button
          type="button"
          aria-label="Add"
          onClick={() => setAdding(true)}
          className="grid size-5 place-items-center rounded-full border border-dashed border-border text-fg-muted transition-colors hover:border-solid hover:bg-accent hover:text-foreground"
        >
          <HugeiconsIcon icon={PlusSignIcon} className="size-3" />
        </button>
      )}
    </div>
  )
}

/** A scalar frontmatter value — plain text until clicked, then an inline input. */
function ScalarField({
  value,
  onChange,
  onLinkClick,
}: {
  value: FrontmatterScalar
  onChange: (next: string) => void
  onLinkClick?: (target: string) => void
}) {
  const [editing, setEditing] = React.useState(false)
  const [draft, setDraft] = React.useState(String(value ?? ""))
  const inputRef = React.useRef<HTMLInputElement>(null)

  // Runs once per entry into edit mode, not on every keystroke — an inline
  // ref callback re-invokes on every render, which re-selects (then the next
  // typed character replaces) the *whole* value after every keystroke.
  React.useEffect(() => {
    if (editing) inputRef.current?.select()
  }, [editing])

  const link = typeof value === "string" ? parseWikilink(value) : null

  if (!editing) {
    // A `[[wikilink]]` value navigates on click, like the note's own outbound
    // links, rather than opening for edit — editing it as text belongs on the
    // note body, not this card.
    if (link) {
      return (
        <button
          type="button"
          onClick={() => onLinkClick?.(link.target)}
          className="rounded px-1 -mx-1 text-left text-entity underline-offset-2 hover:underline"
        >
          {link.label}
        </button>
      )
    }
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(String(value ?? ""))
          setEditing(true)
        }}
        className="rounded px-1 -mx-1 text-left text-muted-foreground transition-colors hover:bg-accent"
      >
        {String(value ?? "") || <span className="text-fg-muted">—</span>}
      </button>
    )
  }

  const commit = () => {
    onChange(draft)
    setEditing(false)
  }

  return (
    <input
      ref={inputRef}
      autoFocus
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit()
        if (e.key === "Escape") setEditing(false)
      }}
      className="-mx-1 w-full rounded bg-background px-1 text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    />
  )
}

/**
 * Editable frontmatter card — replaces stylo's native `---` block entirely
 * (it never sees the frontmatter text; the panel splits it out via
 * `splitFrontmatter` and feeds only the body to `<Stylo>`). List-valued
 * fields render as pills per damiro's reference mockup; everything else is a
 * click-to-edit scalar. Parsing/serializing goes through `yaml`, not a
 * hand-rolled parser, so an unusual note's frontmatter round-trips losslessly
 * instead of risking silent corruption.
 */
function FrontmatterCard({
  raw,
  onChange,
  onLinkClick,
  className,
}: {
  raw: string
  onChange: (raw: string) => void
  /** Fires when a `[[wikilink]]`-valued field is clicked. */
  onLinkClick?: (target: string) => void
  className?: string
}) {
  const data = React.useMemo(() => parseFrontmatter(raw), [raw])

  if (data === null) {
    // Not a flat mapping stylo/yaml can round-trip cleanly (a bare list, an
    // unparseable block, deep nesting) — leave it alone rather than risk
    // mangling it; the raw text is still there, just not in this card.
    return null
  }

  const setField = (key: string, value: FrontmatterData[string]) => {
    onChange(serializeFrontmatter({ ...data, [key]: value }))
  }

  const entries = Object.entries(data)
  if (entries.length === 0) return null

  return (
    <dl
      className={cn(
        // `mx-2` is the same thin gap the stage already uses between distinct
        // panels (`<ContentPanel>`'s and `<MarkdownPanel>`'s own `pe-2`), so
        // this reads as its own block inset from the panel edges rather than
        // full-bleed. `rounded-lg` follows from that — once the sides aren't
        // flush, square corners would look unfinished. The caller still
        // supplies the horizontal *content* gutter (`px-6 sm:px-8`, same as
        // the note body) inside that margin. `bg-background` marks it off
        // from the canvas as its own shaded section; `border-b` closes it off
        // below.
        // `items-center`, not `items-start` — a plain text value and a row of
        // pills (their own `py-0.5` chrome makes that row taller) don't share
        // a height, so aligning both to the row's *top* left the label sitting
        // above a scalar value's true center and above a pill row's actual
        // content by different amounts each time. Centering both against
        // whichever is taller needs no per-row-type padding to compensate.
        "mx-2 shrink-0 grid grid-cols-[max-content_1fr] items-center gap-x-4 gap-y-2 rounded-lg border-b border-border bg-background py-4 font-mono text-xs",
        className
      )}
    >
      {entries.map(([key, value]) => (
        <React.Fragment key={key}>
          <dt className="text-fg-muted uppercase">{key}</dt>
          <dd>
            {Array.isArray(value) ? (
              <PillRow
                values={value}
                onChange={(next) => setField(key, next)}
                onLinkClick={onLinkClick}
              />
            ) : (
              <ScalarField
                value={value}
                onChange={(next) => setField(key, next)}
                onLinkClick={onLinkClick}
              />
            )}
          </dd>
        </React.Fragment>
      ))}
    </dl>
  )
}

export { FrontmatterCard }
