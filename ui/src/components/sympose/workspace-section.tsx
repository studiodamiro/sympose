import { ControlSection, ControlRow } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type { BrandMarkLabel } from "@/lib/use-brand-mark-preference"

/**
 * Settings > Workspace — chrome preferences around the brand mark /
 * workspace switcher (ADR 003). One knob today: what the wordmark next to
 * the switcher shows.
 */
function WorkspaceSection({
  brandMarkLabel,
  setBrandMarkLabel,
}: {
  brandMarkLabel: BrandMarkLabel
  setBrandMarkLabel: (value: BrandMarkLabel) => void
}) {
  return (
    <ControlSection title="Workspace" defaultOpen>
      <ControlRow label="Brand mark">
        <SegmentedControl
          size="sm"
          aria-label="Brand mark"
          value={brandMarkLabel}
          onValueChange={setBrandMarkLabel}
          options={[
            { value: "sympose", label: "Sympose" },
            { value: "vault", label: "Vault name" },
          ]}
        />
      </ControlRow>
    </ControlSection>
  )
}

export { WorkspaceSection }
