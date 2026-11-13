import type { CollectionRole } from "@/models/collection"
import { useI18n } from "@/i18n/useI18n"

const VALUES: CollectionRole[] = ["viewer", "editor", "owner"]

interface RoleSelectProps {
  value: CollectionRole
  onChange: (role: CollectionRole) => void
  disabled?: boolean
  "aria-label": string
}

export function RoleSelect({ value, onChange, disabled, "aria-label": ariaLabel }: RoleSelectProps) {
  const { t } = useI18n()
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as CollectionRole)}
      className="border-input bg-background h-8 max-w-full rounded-lg border px-2 text-sm disabled:opacity-50 sm:max-w-xs"
    >
      {VALUES.map((role) => (
        <option key={role} value={role}>
          {t(`roles.${role}`)} — {t(`roles.${role}Hint`)}
        </option>
      ))}
    </select>
  )
}
