import { Link } from "react-router-dom"
import { Switch } from "@/components/ui/switch"
import type { Collection } from "@/models/collection"
import { useI18n } from "@/i18n/useI18n"

interface MatterAccessListProps {
  collections: Collection[]
  onToggle: (collectionId: string, enabled: boolean) => void
}

// Step 1: turn on the matters this person's AI may search.
export function MatterAccessList({ collections, onToggle }: MatterAccessListProps) {
  const { t } = useI18n()

  if (collections.length === 0) {
    return <p className="text-muted-foreground text-sm">{t("connect.step1Empty")}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col divide-y rounded-lg border">
        {collections.map((collection) => (
          <li key={collection.id} className="flex items-center gap-3 px-3 py-2 text-sm">
            <Switch
              checked={collection.ai_enabled}
              onCheckedChange={(enabled) => onToggle(collection.id, enabled)}
              aria-label={t("collections.aiSwitch", { name: collection.name })}
            />
            <span className="flex-1">{collection.name}</span>
            <span className="text-muted-foreground text-xs">
              {collection.ai_enabled ? t("collections.aiOn") : t("collections.aiOff")}
            </span>
          </li>
        ))}
      </ul>
      <Link to="/collections" className="text-sm underline">
        {t("connect.step1Manage")}
      </Link>
    </div>
  )
}
