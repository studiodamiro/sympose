import {
  ControlRow,
  ControlSection,
} from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type { SearchPreferences } from "@/lib/use-search-preferences"

const PAGE_SIZE_OPTIONS = ["10", "25", "50"] as const

/**
 * Settings → Search. Two knobs over the vault search field's "beyond the
 * current folder" tier (`<VaultContentSearch>`): whether it runs at all, and
 * how many of its results show per page. Cookie-backed via
 * `useSearchPreferences`; the app shell threads `prefs` / `setPref` down the
 * same way it does the editor/notification/nebula preferences.
 */
function SearchPreferencesSection({
  prefs,
  setPref,
}: {
  prefs: SearchPreferences
  setPref: <K extends keyof SearchPreferences>(
    key: K,
    value: SearchPreferences[K]
  ) => void
}) {
  return (
    <ControlSection title="Search">
      <ControlRow label="Search beyond current folder">
        <SegmentedControl
          size="sm"
          aria-label="Search beyond the current folder"
          value={prefs.beyondFolder ? "on" : "off"}
          onValueChange={(v) => setPref("beyondFolder", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        When on, the vault search field also matches notes outside the folder
        you're browsing, listed separately below its own results.
      </p>

      <ControlRow label="Results per page">
        <SegmentedControl
          size="sm"
          aria-label="Search results per page"
          value={String(prefs.resultsPerPage)}
          onValueChange={(v) => setPref("resultsPerPage", Number(v))}
          options={PAGE_SIZE_OPTIONS.map((n) => ({ value: n, label: n }))}
        />
      </ControlRow>
    </ControlSection>
  )
}

export { SearchPreferencesSection }
