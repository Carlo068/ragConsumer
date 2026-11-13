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
  const { t, tp } = useI18n()

  // "12 files · 10 ready", plus how many could not be read when there are any.
  function fileSummary() {
    if (collection.document_count === 0) return t("collections.noFiles")
    const parts = [
      tp("collections.fileCount", collection.document_count),
      tp("collections.readyCount", collection.ready_count),
    ]
    if (collection.failed_count > 0) parts.push(tp("collections.failedCount", collection.failed_count))
    return parts.join(" · ")
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border px-4 py-3">
      <div className="flex w-20 flex-col items-center gap-1" title={t("collections.aiSwitchTitle")}>
        <Switch
          checked={collection.ai_enabled}
          onCheckedChange={onToggleAi}
          aria-label={t("collections.aiSwitch", { name: collection.name })}
        />
        <span className="text-muted-foreground text-center text-[11px] leading-tight">
          {collection.ai_enabled ? t("collections.aiOn") : t("collections.aiOff")}
        </span>
      </div>
      <div className="flex-1">
        <Link to={`/collections/${collection.id}/upload`} className="font-medium hover:underline">
          {collection.name}
        </Link>
        <p className="text-muted-foreground text-xs">{fileSummary()}</p>
      </div>
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
