import { ControlSection, ControlRow } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type { EditorPreferences } from "@/lib/use-editor-preferences"

/** A `SegmentedControl` bound to one `EditorPreferences` field. */
function PrefToggle<K extends keyof EditorPreferences>({
  field,
  label,
  value,
  onChange,
  options,
}: {
  field: K
  label: string
  value: EditorPreferences[K]
  onChange: (field: K, value: EditorPreferences[K]) => void
  options: { value: EditorPreferences[K]; label: string }[]
}) {
  return (
    <ControlRow label={label}>
      <SegmentedControl
        size="sm"
        aria-label={label}
        value={value}
        onValueChange={(next) => onChange(field, next)}
        options={options}
      />
    </ControlRow>
  )
}

/**
 * Settings > Markdown editor — the stylo-backed knobs worth exposing as user
 * preferences (see the stylo integration audit): everything else stylo takes
 * as config is either applied-at-mount plumbing (`codeLanguages`) or a prop
 * this app deliberately leaves unset (`toolbar.sticky` — the bounded panel
 * layout already keeps the toolbar pinned for free, so turning it on would
 * only add a standing per-frame watchdog for no benefit here).
 *
 * Takes `prefs`/`setPref` from the app shell's single `useEditorPreferences()`
 * call, the same way `activePersona` is threaded down — two independent hook
 * instances would each hold their own copy of the cookie‑seeded state and
 * never see each other's writes.
 */
function EditorPreferencesSection({
  prefs,
  setPref,
}: {
  prefs: EditorPreferences
  setPref: <K extends keyof EditorPreferences>(
    field: K,
    value: EditorPreferences[K]
  ) => void
}) {
  const inPlace = prefs.surface === "in-place"

  return (
    <ControlSection title="Markdown editor" defaultOpen>
      <PrefToggle
        field="surface"
        label="Editing surface"
        value={prefs.surface}
        onChange={setPref}
        options={[
          { value: "in-place", label: "Seamless" },
          { value: "source", label: "Plain text" },
        ]}
      />
      {inPlace && (
        <>
          <PrefToggle
            field="reveal"
            label="Formatting marks"
            value={prefs.reveal}
            onChange={setPref}
            options={[
              { value: "caret", label: "Near cursor" },
              { value: "never", label: "Always hidden" },
            ]}
          />
          <PrefToggle
            field="selectionUI"
            label="Selection controls"
            value={prefs.selectionUI}
            onChange={setPref}
            options={[
              { value: "menu", label: "Right-click menu" },
              { value: "bar", label: "Floating bar" },
            ]}
          />
        </>
      )}
      <PrefToggle
        field="focusOutline"
        label="Focus outline"
        value={prefs.focusOutline}
        onChange={setPref}
        options={[
          { value: "off", label: "Hidden" },
          { value: "on", label: "Shown" },
        ]}
      />
      <PrefToggle
        field="autosave"
        label="Autosave"
        value={prefs.autosave}
        onChange={setPref}
        options={[
          { value: "off", label: "Off" },
          { value: "on", label: "On" },
        ]}
      />
    </ControlSection>
  )
}

export { EditorPreferencesSection }
