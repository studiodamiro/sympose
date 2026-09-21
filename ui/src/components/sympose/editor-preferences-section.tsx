import { StyloToolbarSettings } from "@damiro/stylo/toolbar-settings"
import type { ToolbarItem } from "@damiro/stylo"

import { ControlSection, ControlRow } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import { TOOLBAR_ICONS } from "@/components/sympose/markdown-panel"
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
 * never see each other's writes. `toolbarItems`/`onToolbarItemsChange` are
 * threaded the same way from the shell's `useToolbarItems()`.
 *
 * `<StyloToolbarSettings>` offers every built-in command, including the ones
 * `markdown-panel.tsx` deliberately left out of the shipped default
 * (`table`/`link`/`wikilink`/`hr`/`frontmatter`/`math`/`undo`/`redo`) — since
 * this is a personal tool, the customizer should let you put any of them back
 * rather than holding a subset in reserve. Its own "Reset to default" button
 * resets to stylo's upstream default set, not sympose's — an accepted quirk
 * of the upstream component, not overridable via props.
 *
 * Nested in its own collapsed-by-default `ControlSection` (two long columns
 * of buttons is a lot to scroll past for anyone who just wants Autosave).
 * The `data-slot="toolbar-settings"` wrapper carries no chrome of its own —
 * it's a CSS hook, not a card: unlike `<Stylo>` itself, this component never
 * sits inside a `.stylo`-classed element, so its `var(--stylo-bg)` /
 * `var(--stylo-border)` / etc. have no source at all here. `index.css` scopes
 * real values to that selector so the two columns it renders ("On the bar" /
 * "Available") pick up Sympose's palette for their own built-in card
 * treatment, instead of an outer card stacked on top of theirs.
 */
function EditorPreferencesSection({
  prefs,
  setPref,
  toolbarItems,
  onToolbarItemsChange,
}: {
  prefs: EditorPreferences
  setPref: <K extends keyof EditorPreferences>(
    field: K,
    value: EditorPreferences[K]
  ) => void
  toolbarItems: ToolbarItem[]
  onToolbarItemsChange: (next: ToolbarItem[]) => void
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
          <PrefToggle
            field="tableEditing"
            label="Table editing"
            value={prefs.tableEditing}
            onChange={setPref}
            options={[
              { value: "source", label: "Source" },
              { value: "cells", label: "Cells" },
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
      <PrefToggle
        field="hideExtension"
        label="File extensions"
        value={prefs.hideExtension}
        onChange={setPref}
        options={[
          { value: "on", label: "Hidden" },
          { value: "off", label: "Shown" },
        ]}
      />
      <ControlSection title="Toolbar buttons">
        {/* No card of its own here — stylo already renders "On the bar" /
            "Available" as two bordered, solid-fill boxes side by side
            (`._col_18hcd_17` in its own CSS module); a second wrapping card
            around both just doubled up the chrome. `data-slot` is still
            needed as a hook for the `--stylo-*` variable scope below. */}
        <div data-slot="toolbar-settings">
          <StyloToolbarSettings
            value={toolbarItems}
            onChange={onToolbarItemsChange}
            icons={TOOLBAR_ICONS}
          />
        </div>
      </ControlSection>
    </ControlSection>
  )
}

export { EditorPreferencesSection }
