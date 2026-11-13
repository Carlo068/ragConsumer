import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { PromptDialog } from "@/components/common/PromptDialog"
import { useCollections } from "@/hooks/useCollections"
import { useI18n } from "@/i18n/useI18n"
import { CollectionRow } from "./components/CollectionRow"

export function CollectionsPage() {
  const { t } = useI18n()
  const {
    collections,
    loading,
    error,
    createCollection,
    renameCollection,
    deleteCollection,
    setAiAccess,
  } = useCollections()

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("collections.title")}</h1>
        <PromptDialog
          trigger={
            <Button>
              <Plus />
              {t("collections.new")}
            </Button>
          }
          title={t("collections.newTitle")}
          confirmLabel={t("collections.create")}
          onSubmit={createCollection}
        />
      </div>

      <p className="text-muted-foreground mb-4 text-sm">{t("collections.intro")}</p>

      {loading && <p>{t("common.loading")}</p>}
      {error && <p className="text-destructive">{error}</p>}
      {!loading && !error && collections.length === 0 && (
        <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-center text-sm">
          {t("collections.empty")}
        </p>
      )}

      <div className="flex flex-col gap-3">
        {collections.map((collection) => (
          <CollectionRow
            key={collection.id}
            collection={collection}
            onToggleAi={(enabled) => setAiAccess(collection.id, enabled)}
            onRename={(name) => renameCollection(collection.id, name)}
            onDelete={() => deleteCollection(collection.id)}
          />
        ))}
      </div>
    </div>
  )
}
