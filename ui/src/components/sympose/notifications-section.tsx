import { ControlSection, ControlRow } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  TOAST_POSITIONS,
  type NotificationPreferences,
  type ToastPosition,
} from "@/lib/use-notification-preferences"

const POSITION_LABELS: Record<ToastPosition, string> = {
  "top-left": "Top left",
  "top-center": "Top centre",
  "top-right": "Top right",
  "bottom-left": "Bottom left",
  "bottom-center": "Bottom centre",
  "bottom-right": "Bottom right",
}

/**
 * Settings > Notifications — where feedback toasts appear, whether they appear
 * at all, and how a delete asks first. Cookie-backed via
 * `useNotificationPreferences`; the app shell threads `prefs` / `setPref` down
 * the same way it does the editor ones. `position` governs both the feedback
 * toasts and the inline confirmation; permanent deletes always use the dialog.
 */
function NotificationsSection({
  prefs,
  setPref,
}: {
  prefs: NotificationPreferences
  setPref: <K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K]
  ) => void
}) {
  return (
    <ControlSection title="Notifications" defaultOpen>
      <ControlRow label="Feedback messages">
        <SegmentedControl
          size="sm"
          aria-label="Feedback messages"
          value={prefs.enabled}
          onValueChange={(v) => setPref("enabled", v)}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <ControlRow label="Delete confirmation">
        <SegmentedControl
          size="sm"
          aria-label="Delete confirmation"
          value={prefs.confirm}
          onValueChange={(v) => setPref("confirm", v)}
          options={[
            { value: "dialog", label: "Dialog" },
            { value: "inline", label: "Inline" },
            { value: "none", label: "None" },
          ]}
        />
      </ControlRow>
      <ControlRow label="Position">
        <Select
          value={prefs.position}
          onValueChange={(v) => setPref("position", v as ToastPosition)}
        >
          <SelectTrigger size="sm" className="w-40" aria-label="Position">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TOAST_POSITIONS.map((p) => (
              <SelectItem key={p} value={p}>
                {POSITION_LABELS[p]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </ControlRow>
    </ControlSection>
  )
}

export { NotificationsSection }
