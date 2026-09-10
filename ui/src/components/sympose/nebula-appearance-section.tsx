import {
  ControlRow,
  ControlSection,
} from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type {
  NebulaInteraction,
  NebulaPreferences,
} from "@/lib/use-nebula-preferences"

/** A numeric knob as a native range input with a live readout. */
function SliderRow({
  label,
  field,
  min,
  max,
  step,
  format,
  hint,
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
  format: (v: number) => string
  hint?: string
  prefs: NebulaPreferences
  setPref: <K extends keyof NebulaPreferences>(
    key: K,
    value: NebulaPreferences[K]
  ) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums text-fg-muted">
          {format(prefs[field])}
        </span>
      </div>
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={prefs[field]}
        onChange={(e) => setPref(field, Number(e.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-border accent-primary"
      />
      {hint && <p className="text-xs text-fg-muted">{hint}</p>}
    </div>
  )
}

/**
 * Settings → the Knowledge Nebula. Phase A exposes the control the design
 * reference places here (UI_DESIGN_REFERENCE.md §6.4) — the `Explore | Focus`
 * mode — plus the two Focus-scrim knobs (`blur`, `tint`), which live here
 * rather than in the nebula's own dock because the dock is only on screen in
 * Explore, where you cannot see what the scrim does. The `2D | 3D` renderer
 * switch is in the dock with the other display knobs.
 *
 * Cookie-backed via `useNebulaPreferences`; the app shell threads `prefs` /
 * `setPref` down the same way it does the editor and notification preferences.
 */
function NebulaAppearanceSection({
  prefs,
  setPref,
}: {
  prefs: NebulaPreferences
  setPref: <K extends keyof NebulaPreferences>(
    key: K,
    value: NebulaPreferences[K]
  ) => void
}) {
  return (
    <ControlSection title="Knowledge Nebula" defaultOpen>
      <ControlRow label="Vault graph">
        <SegmentedControl
          size="sm"
          aria-label="Knowledge Nebula mode"
          value={prefs.interaction}
          onValueChange={(v) => setPref("interaction", v as NebulaInteraction)}
          options={[
            { value: "focus", label: "Focus" },
            { value: "explore", label: "Explore" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        Explore brings the vault graph forward and lets you orbit it. Focus
        hides it behind your panels — tuned below.
      </p>

      <SliderRow
        label="Focus blur"
        field="focusBlur"
        min={0}
        max={24}
        step={1}
        format={(v) => `${Math.round(v)}px`}
        prefs={prefs}
        setPref={setPref}
      />
      <SliderRow
        label="Focus tint"
        field="focusTint"
        min={0}
        max={1}
        step={0.05}
        format={(v) => `${Math.round(v * 100)}%`}
        hint="Blur softens the graph; tint lays a matte cover over it. Both zero leaves it fully visible."
        prefs={prefs}
        setPref={setPref}
      />

      <SliderRow
        label="Panel blur"
        field="panelBlur"
        min={0}
        max={24}
        step={1}
        format={(v) => `${Math.round(v)}px`}
        prefs={prefs}
        setPref={setPref}
      />
      <SliderRow
        label="Panel opacity"
        field="panelOpacity"
        min={0.4}
        max={1}
        step={0.05}
        format={(v) => `${Math.round(v * 100)}%`}
        hint="Let the nebula show through the vault, editor and chat panels. Below 100% the panels turn translucent; blur frosts what shows through."
        prefs={prefs}
        setPref={setPref}
      />
    </ControlSection>
  )
}

export { NebulaAppearanceSection }
