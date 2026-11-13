import { Link } from "react-router-dom"
import { Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { PromptDialog } from "@/components/common/PromptDialog"
import { useI18n } from "@/i18n/useI18n"
import { canManageCollection, type Collection } from "@/models/collection"

interface CollectionRowProps {
  collection: Collection
  onToggleAi: (enabled: boolean) => void
  onRename: (name: string) => void
  onDelete: () => void
}

export function CollectionRow({
  collection,
  onToggleAi,
  onRename,
  onDelete,
}: CollectionRowProps) {
  const { t } = useI18n()
  return (
    <div className="flex items-center gap-3 rounded-lg border px-4 py-3">
      <Switch
        checked={collection.ai_enabled}
        onCheckedChange={onToggleAi}
        aria-label={t("collections.aiSwitch", { name: collection.name })}
        title={t("collections.aiSwitchTitle")}
      />
      <Link
        to={`/collections/${collection.id}/upload`}
        className="flex-1 font-medium hover:underline"
      >
        {collection.name}
      </Link>
      {!canManageCollection(collection.role) && (
        <span className="text-muted-foreground text-xs">{t(`roles.${collection.role}`)}</span>
      )}
      {canManageCollection(collection.role) && (
        <>
          <PromptDialog
            trigger={
              <Button variant="ghost" size="icon-sm" aria-label={t("collections.renameLabel")}>
                <Pencil />
              </Button>
            }
            title={t("collections.renameTitle", { name: collection.name })}
            initialValue={collection.name}
            confirmLabel={t("common.save")}
            onSubmit={onRename}
          />
          <ConfirmDialog
            trigger={
              <Button variant="ghost" size="icon-sm" aria-label={t("collections.deleteLabel")}>
                <Trash2 />
              </Button>
            }
            title={t("collections.deleteTitle", { name: collection.name })}
            description={t("collections.deleteDescription")}
            onConfirm={onDelete}
          />
        </>
      )}
    </div>
  )
}
