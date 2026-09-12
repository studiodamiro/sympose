import { cn } from "@/lib/utils"
import {
  ControlRow,
  ControlSection,
} from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type { NebulaPreferences } from "@/lib/use-nebula-preferences"

type SetPref = <K extends keyof NebulaPreferences>(
  key: K,
  value: NebulaPreferences[K]
) => void

/** A boolean knob as an On / Off segmented control. */
function ToggleRow({
  label,
  field,
  prefs,
  setPref,
}: {
  label: string
  field: {
    [K in keyof NebulaPreferences]: NebulaPreferences[K] extends boolean
      ? K
      : never
  }[keyof NebulaPreferences]
  prefs: NebulaPreferences
  setPref: SetPref
}) {
  return (
    <ControlRow label={label}>
      <SegmentedControl
        size="sm"
        aria-label={label}
        value={prefs[field] ? "on" : "off"}
        onValueChange={(v) => setPref(field, v === "on")}
        options={[
          { value: "on", label: "On" },
          { value: "off", label: "Off" },
        ]}
      />
    </ControlRow>
  )
}

/**
 * A numeric knob as a native range input with a live readout. Two layouts:
 *
 *   `"stacked"` (default) — label/value on their own row, a full-width
 *   track below. What the floating dock uses (`w-64`, narrow enough that an
 *   inline track would be cramped).
 *   `"inline"` — one `ControlRow` line, label and value folded into a
 *   single string with the track to its right, matching every other Settings
 *   row (toggles, segmented controls) instead of standing out as the only
 *   two-line control in the list.
 */
function SliderRow({
  label,
  field,
  min,
  max,
  step,
  format,
  hint,
  layout = "stacked",
  prefs,
  setPref,
}: {
  label: string
  field: {
    [K in keyof NebulaPreferences]: NebulaPreferences[K] extends number
      ? K
      : never
  }[keyof NebulaPreferences]
  min: number
  max: number
  step: number
  format?: (v: number) => string
  hint?: string
  layout?: "stacked" | "inline"
  prefs: NebulaPreferences
  setPref: SetPref
}) {
  const value = prefs[field]
  const readout = format ? format(value) : String(value)
  const track = (
    <input
      type="range"
      aria-label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => setPref(field, Number(e.target.value))}
      className={cn(
        "h-1.5 cursor-pointer appearance-none rounded-full bg-border accent-primary",
        layout === "inline" ? "w-32 sm:w-40" : "w-full"
      )}
    />
  )

  if (layout === "inline") {
    return (
      <div className="flex flex-col gap-1">
        <ControlRow label={`${label}, ${readout}`}>{track}</ControlRow>
        {hint && <p className="text-xs text-fg-muted">{hint}</p>}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="text-fg-muted tabular-nums">{readout}</span>
      </div>
      {track}
      {hint && <p className="text-xs text-fg-muted">{hint}</p>}
    </div>
  )
}

/**
 * The Knowledge Nebula control dock — the trimmed Obsidian-parity stack that
 * floats over the ambient layer in Explore mode (UI_DESIGN_REFERENCE.md §5,
 * §6.3). Re-skinned onto the app's semantic tokens and `ControlSection`
 * primitives rather than the standalone `/nebula` route's hand-rolled panel.
 *
 * Phase A exposes the subset agreed with the lead: Toggles (orphans, tags,
 * 2D/3D), Display (labels, node size, link thickness), Forces (all four). The
 * 3D segment is present but disabled — the WebGL renderer lands in Phase B.
 * Every other persisted knob keeps its default until wired here.
 */
function NebulaControls({
  prefs,
  setPref,
  className,
  layout = "stacked",
}: {
  prefs: NebulaPreferences
  setPref: SetPref
  className?: string
  /** Slider row layout — see `SliderRow`. `NebulaAppearanceSection` (Settings)
   *  passes `"inline"`; the floating dock keeps the default. */
  layout?: "stacked" | "inline"
}) {
  return (
    <div
      data-slot="nebula-controls"
      className={cn(
        "w-64 rounded-xl border border-border bg-card/95 px-3.5 shadow-lg backdrop-blur-md",
        className
      )}
    >
      <ControlSection title="Toggles" defaultOpen>
        <ToggleRow
          label="Orphans"
          field="orphans"
          prefs={prefs}
          setPref={setPref}
        />
        <ToggleRow label="Tags" field="tags" prefs={prefs} setPref={setPref} />
        <ToggleRow
          label="Legend"
          field="legend"
          prefs={prefs}
          setPref={setPref}
        />
        <ControlRow label="Renderer">
          <SegmentedControl
            size="sm"
            aria-label="Renderer"
            value={prefs.mode}
            disabledValues={["3d"]}
            onValueChange={(v) => setPref("mode", v)}
            options={[
              { value: "2d", label: "2D" },
              { value: "3d", label: "3D" },
            ]}
          />
        </ControlRow>
        <p className="text-xs text-fg-muted">
          3D renderer lands in a later build.
        </p>
      </ControlSection>

      <ControlSection title="Display" defaultOpen>
        <ToggleRow
          label="Labels"
          field="labels"
          prefs={prefs}
          setPref={setPref}
        />
        <SliderRow
          label="Node size"
          field="nodeRelSize"
          min={1}
          max={10}
          step={0.1}
          format={(v) => (v / 2.4).toFixed(2)}
          prefs={prefs}
          setPref={setPref}
          layout={layout}
        />
        <SliderRow
          label="Link thickness"
          field="linkWidth"
          min={0.1}
          max={5}
          step={0.1}
          format={(v) => v.toFixed(2)}
          prefs={prefs}
          setPref={setPref}
          layout={layout}
        />
      </ControlSection>

      <ControlSection title="Forces" defaultOpen>
        <SliderRow
          label="Center force"
          field="centerForce"
          min={0}
          max={1}
          step={0.05}
          format={(v) => v.toFixed(2)}
          prefs={prefs}
          setPref={setPref}
          layout={layout}
        />
        <SliderRow
          label="Repel force"
          field="repelForce"
          min={1}
          max={30}
          step={0.5}
          format={(v) => v.toFixed(2)}
          prefs={prefs}
          setPref={setPref}
          layout={layout}
        />
        <SliderRow
          label="Link force"
          field="linkForce"
          min={0.1}
          max={2}
          step={0.05}
          format={(v) => v.toFixed(2)}
          prefs={prefs}
          setPref={setPref}
          layout={layout}
        />
        <SliderRow
          label="Link distance"
          field="linkDistance"
          min={0}
          max={800}
          step={10}
          format={(v) => String(Math.round(v))}
          prefs={prefs}
          setPref={setPref}
          layout={layout}
        />
      </ControlSection>
    </div>
  )
}

export { NebulaControls, SliderRow as NebulaSliderRow }
