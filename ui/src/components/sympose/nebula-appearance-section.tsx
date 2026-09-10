import {
  ControlRow,
  ControlSection,
} from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type {
  NebulaInteraction,
  NebulaPreferences,
} from "@/lib/use-nebula-preferences"

/**
 * Settings → the Knowledge Nebula. Phase A exposes the one control the design
 * reference places here (UI_DESIGN_REFERENCE.md §6.4): the `Explore | Focus`
 * mode. `Explore` brings the vault graph forward, sharp and interactive;
 * `Focus` (the default) drops it to a dimmed ambient layer so the panels own
 * the screen. The `2D | 3D` renderer switch lives in the nebula's own control
 * dock, not here.
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
        Explore brings the vault graph forward and lets you orbit it. Focus dims
        it behind your panels.
      </p>
    </ControlSection>
  )
}

export { NebulaAppearanceSection }
