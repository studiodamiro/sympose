import {
  ControlRow,
  ControlSection,
} from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import {
  NebulaControls,
  NebulaSliderRow,
} from "@/components/sympose/nebula-controls"
import type {
  NebulaInteraction,
  NebulaPreferences,
} from "@/lib/use-nebula-preferences"

/**
 * Settings → the Knowledge Nebula. Phase A exposes the control the design
 * reference places here (UI_DESIGN_REFERENCE.md §6.4) — the `Explore | Focus`
 * mode — plus the Focus-scrim knobs (`blur`, `tint`) and the panel opacity
 * knob, which only make sense here (the dock is only on screen in Explore,
 * where you can't see what a Focus-only knob does).
 *
 * The dock's own knobs (Toggles / Display / Forces) are reused verbatim below
 * — `<NebulaControls>` itself, stripped of its floating-card chrome so it
 * reads as more sub-sections of this one rather than a second surface — so
 * every knob is reachable from Settings too, not only while already in
 * Explore looking at the dock. Every slider here (these three and the dock's)
 * shares one `NebulaSliderRow` with `layout="inline"` — label, value and
 * track on one `ControlRow` line, matching the toggles and segmented
 * controls around them instead of standing out as two-line rows; the dock
 * keeps the two-line `"stacked"` default, since its `w-64` floating card is
 * too narrow for an inline track.
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

      <NebulaSliderRow
        label="Focus blur"
        field="focusBlur"
        min={0}
        max={24}
        step={1}
        format={(v) => `${Math.round(v)}px`}
        layout="inline"
        prefs={prefs}
        setPref={setPref}
      />
      <NebulaSliderRow
        label="Focus tint"
        field="focusTint"
        min={0}
        max={1}
        step={0.05}
        format={(v) => `${Math.round(v * 100)}%`}
        hint="Blur softens the graph; tint lays a matte cover over it. Both zero leaves it fully visible."
        layout="inline"
        prefs={prefs}
        setPref={setPref}
      />

      <NebulaSliderRow
        label="Panel opacity"
        field="panelOpacity"
        min={0.4}
        max={1}
        step={0.05}
        format={(v) => `${Math.round(v * 100)}%`}
        hint="Let the nebula show through the vault and editor panels (not chat). Below 100% they turn translucent — limited by how much Focus tint already hides."
        layout="inline"
        prefs={prefs}
        setPref={setPref}
      />

      <ControlRow label="Dock in Explore">
        <SegmentedControl
          size="sm"
          aria-label="Show the control dock in Explore"
          value={prefs.dock ? "on" : "off"}
          onValueChange={(v) => setPref("dock", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        Every knob below is also the floating dock shown in Explore — turn it
        off there for an unobstructed view once you're tuning from here
        instead.
      </p>

      <NebulaControls
        prefs={prefs}
        setPref={setPref}
        layout="inline"
        className="w-full rounded-none border-0 bg-transparent p-0 shadow-none backdrop-blur-none"
      />
    </ControlSection>
  )
}

export { NebulaAppearanceSection }
