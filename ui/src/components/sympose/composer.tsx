import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { SentIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Kbd, KbdGroup } from "@/components/ui/kbd"

/**
 * Chat composer (UI_DESIGN_REFERENCE.md §7) — a single flat auto-growing input,
 * `@` mention affordance, submit on ⌘/Ctrl-Enter. No formatting toolbar. The
 * `@` autocomplete menu itself is out of scope here; this is the input shell and
 * its states (idle / disabled / with hint).
 */
interface ComposerProps
  extends Omit<React.ComponentProps<"form">, "onSubmit"> {
  placeholder?: string
  disabled?: boolean
  /** Called with the trimmed message on ⌘/Ctrl-Enter or the send button. */
  onSend?: (message: string) => void
  hint?: React.ReactNode
}

function Composer({
  className,
  placeholder = "Ask @samantha, @grace, @anais…",
  disabled = false,
  onSend,
  hint,
  ...props
}: ComposerProps) {
  const [value, setValue] = React.useState("")
  const taRef = React.useRef<HTMLTextAreaElement>(null)

  const autosize = React.useCallback(() => {
    const el = taRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [])

  React.useEffect(autosize, [value, autosize])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend?.(trimmed)
    setValue("")
  }

  return (
    <form
      data-slot="composer"
      className={cn("flex flex-col gap-1.5", className)}
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      {...props}
    >
      <div
        className={cn(
          "flex items-end gap-2 rounded-md border border-border bg-background px-2 py-1.5 transition-colors focus-within:border-brand",
          disabled && "opacity-50"
        )}
      >
        <textarea
          ref={taRef}
          rows={1}
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              submit()
            }
          }}
          className={cn(
            "max-h-40 min-h-8 flex-1 resize-none bg-transparent py-1.5 text-sm outline-none placeholder:text-muted-foreground",
            "disabled:cursor-not-allowed"
          )}
        />
        <Button
          type="submit"
          size="icon"
          variant="ghost"
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="text-brand"
        >
          <HugeiconsIcon icon={SentIcon} />
        </Button>
      </div>
      <div className="flex items-center justify-between px-1">
        <span className="text-xs text-muted-foreground">{hint}</span>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <KbdGroup>
            <Kbd>⌘</Kbd>
            <Kbd>↵</Kbd>
          </KbdGroup>
          to send
        </span>
      </div>
    </form>
  )
}

export { Composer }
