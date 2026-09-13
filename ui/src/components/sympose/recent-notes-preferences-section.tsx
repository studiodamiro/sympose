import {
  ControlRow,
  ControlSection,
} from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"

const SHOWN_COUNT_OPTIONS = ["3", "5", "10"] as const

/**
 * Settings → Recent notes. Two knobs over the "Recent" group in the vault
 * panel (`use-recent-notes.ts`): whether it shows at all, and how many
 * recently opened notes show when it does — for jumping back to what you
 * were just working on. Cookie-backed, same convention as
 * `SearchPreferencesSection`.
 */
function RecentNotesPreferencesSection({
  enabled,
  setEnabled,
  shownCount,
  setShownCount,
}: {
  enabled: boolean
  setEnabled: (on: boolean) => void
  shownCount: number
  setShownCount: (n: number) => void
}) {
  return (
    <ControlSection title="Recent notes">
      <ControlRow label="Show recent notes">
        <SegmentedControl
          size="sm"
          aria-label="Show recent notes"
          value={enabled ? "on" : "off"}
          onValueChange={(v) => setEnabled(v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      {enabled && (
        <ControlRow label="Notes shown">
          <SegmentedControl
            size="sm"
            aria-label="Recent notes shown"
            value={String(shownCount)}
            onValueChange={(v) => setShownCount(Number(v))}
            options={SHOWN_COUNT_OPTIONS.map((n) => ({ value: n, label: n }))}
          />
        </ControlRow>
      )}
      <p className="text-xs text-fg-muted">
        When on, a "Recent" group under Pinned in the vault panel lists the
        last notes you opened, from anywhere in the vault.
      </p>
    </ControlSection>
  )
}

export { RecentNotesPreferencesSection }
