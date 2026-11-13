import type { CollectionRole } from "@/models/collection"

const OPTIONS: { value: CollectionRole; label: string; hint: string }[] = [
  { value: "viewer", label: "Viewer", hint: "can search and see files" },
  { value: "editor", label: "Editor", hint: "can also add and remove files" },
  { value: "owner", label: "Owner", hint: "can also manage the collection and its members" },
]

interface RoleSelectProps {
  value: CollectionRole
  onChange: (role: CollectionRole) => void
  disabled?: boolean
  "aria-label": string
}

export function RoleSelect({ value, onChange, disabled, "aria-label": ariaLabel }: RoleSelectProps) {
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as CollectionRole)}
      className="border-input bg-background h-8 rounded-lg border px-2 text-sm disabled:opacity-50"
    >
      {OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label} — {o.hint}
        </option>
      ))}
    </select>
  )
}
